"""The command line: read what to do, log in, enrol, say what happened, email it."""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from asvz_enroll.email_notification import send_email
from asvz_enroll.enrolment_timing import (
    DEFAULT_LONGEST_WAIT_FOR_OPENING,
    safe_sending_time,
    wait_until,
)
from asvz_enroll.errors import AsvzEnrollError, EnrolmentWindowError
from asvz_enroll.lesson_api import enrol, get_lesson, lesson_page_url, my_enrolment
from asvz_enroll.login import log_in
from asvz_enroll.models import Lesson
from asvz_enroll.settings import (
    EARLY_START_MINUTES_KEY,
    LESSON_ID_KEY,
    PASSWORD_KEY,
    USERNAME_KEY,
    EnrolmentRequest,
    read_email_settings,
    read_enrolment_request,
)
from asvz_enroll.upcoming_lesson import find_upcoming_lesson

EXIT_OK = 0
EXIT_NETWORK_PROBLEM = 4

EXACT_TIME = "%a %d %b %H:%M:%S"

Failure = AsvzEnrollError | httpx.HTTPError
FAILURES = (AsvzEnrollError, httpx.HTTPError)


@dataclass(frozen=True)
class Outcome:
    """How a run ended: the text for the user, the exit code, and the lesson's web page."""

    message: str
    exit_code: int
    lesson_url: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == EXIT_OK


def main(arguments: Sequence[str] | None = None) -> int:
    options = _read_options(arguments)

    if options.check_login:
        outcome = check_login(options)
        _print(outcome)
    else:
        outcome = enrol_in_upcoming_lesson(options)
        _print(outcome)
        _email(outcome)

    return outcome.exit_code


def enrol_in_upcoming_lesson(options: argparse.Namespace) -> Outcome:
    now = datetime.now().astimezone()

    try:
        request = read_enrolment_request(options.username, options.password, options.lesson_id)
        lesson = find_upcoming_lesson(get_lesson(request.lesson_id), now)
    except FAILURES as failure:
        return _failed(failure)

    lesson_url = lesson_page_url(lesson.id)
    note = _note_if_moved(request.lesson_id, lesson)
    try:
        return Outcome(note + _enrol(request, lesson, now), EXIT_OK, lesson_url)
    except FAILURES as failure:
        return _failed(failure, note, lesson_url)


def check_login(options: argparse.Namespace) -> Outcome:
    """Log in without enrolling, to test the username and password."""
    try:
        request = read_enrolment_request(
            options.username, options.password, options.lesson_id or "0"
        )
        token = log_in(request.username, request.password)
    except FAILURES as failure:
        return _failed(failure)
    return Outcome(f"Login ok, token valid until {token.expires_at.astimezone():%H:%M}.", EXIT_OK)


def _enrol(request: EnrolmentRequest, lesson: Lesson, now: datetime) -> str:
    _require_reachable_enrolment(lesson, now, request.longest_wait_for_opening)
    sending_time = safe_sending_time(lesson.enrolment_opens)

    token = log_in(request.username, request.password)

    existing_enrolment = my_enrolment(lesson.id, token)
    if existing_enrolment:
        return f"Already enrolled: {lesson.describe()}, place {existing_enrolment.place_number}."

    if sending_time > datetime.now().astimezone():
        print(
            f"Enrolment opens {lesson.enrolment_opens:%H:%M:%S}; "
            f"waiting until {sending_time:%H:%M:%S} in case this computer's clock is behind.",
            flush=True,
        )
        wait_until(sending_time)

    enrolment = enrol(lesson.id, token)
    sent = datetime.now().astimezone()
    return (
        f"Enrolled: {lesson.describe()}, place {enrolment.place_number}.\n"
        f"Request sent {sent:%H:%M:%S} by this computer's clock, "
        f"{_describe_duration(sent - lesson.enrolment_opens)} after enrolment opened."
    )


def _require_reachable_enrolment(
    lesson: Lesson,
    now: datetime,
    longest_wait_for_opening: timedelta = DEFAULT_LONGEST_WAIT_FOR_OPENING,
) -> None:
    """Enrolment must be open, or open soon enough to wait for it."""
    if lesson.enrolment_opens - now > longest_wait_for_opening:
        raise EnrolmentWindowError(
            f"Enrolment for {lesson.describe()} opens {lesson.enrolment_opens:{EXACT_TIME}}. "
            f"This attempt ran {now:{EXACT_TIME}}, "
            f"{_describe_duration(lesson.enrolment_opens - now)} too early. "
            f"The app waits for the opening only if it is at most "
            f"{_describe_duration(longest_wait_for_opening)} away "
            f"(set {EARLY_START_MINUTES_KEY} in .env to change this)."
        )
    if now > lesson.enrolment_closes:
        raise EnrolmentWindowError(
            f"Enrolment for {lesson.describe()} closed {lesson.enrolment_closes:{EXACT_TIME}}. "
            f"This attempt ran {now:{EXACT_TIME}}, "
            f"{_describe_duration(now - lesson.enrolment_closes)} too late."
        )


def _describe_duration(duration: timedelta) -> str:
    """'0.4 seconds' for a near miss, otherwise days and h:mm:ss like '2 days, 1:24:48'."""
    if duration < timedelta(minutes=1):
        return f"{duration.total_seconds():.1f} seconds"
    return str(timedelta(seconds=round(duration.total_seconds())))


def _note_if_moved(requested_lesson_id: int, lesson: Lesson) -> str:
    if lesson.id == requested_lesson_id:
        return ""
    return f"Lesson {requested_lesson_id} is over; using the upcoming lesson {lesson.id}.\n"


def _failed(failure: Failure, note: str = "", lesson_url: str | None = None) -> Outcome:
    if isinstance(failure, AsvzEnrollError):
        return Outcome(f"{note}Error: {failure}", failure.exit_code, lesson_url)
    return Outcome(f"{note}Network problem: {failure}", EXIT_NETWORK_PROBLEM, lesson_url)


def _print(outcome: Outcome) -> None:
    print(outcome.message, file=sys.stdout if outcome.succeeded else sys.stderr)


def _email(outcome: Outcome) -> None:
    """Email the outcome if the .env file names a recipient. A failed email is only a warning:
    it must not change whether the enrolment itself counts as succeeded."""
    try:
        email_settings = read_email_settings()
        if email_settings is None:
            return
        subject = "ASVZ enrolment succeeded" if outcome.succeeded else "ASVZ enrolment failed"
        send_email(email_settings, subject, _email_text(outcome))
        print(f"Email sent to {email_settings.recipient}.")
    except FAILURES as failure:
        print(f"Warning: no email was sent. {failure}", file=sys.stderr)


def _email_text(outcome: Outcome) -> str:
    if outcome.lesson_url is None:
        return outcome.message
    return (
        f"{outcome.message}\n\n"
        f"View the lesson, enrol or cancel your enrolment:\n{outcome.lesson_url}"
    )


def _read_options(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="asvz-enroll",
        description="Enrol in an ASVZ lesson right now.",
        epilog="Any option you leave out is read from the .env file in the current folder. "
        "If the lesson is already over, its next weekly occurrence is used instead.",
    )
    parser.add_argument("-u", "--username", help=f"SWITCH edu-ID email ({USERNAME_KEY})")
    parser.add_argument("-p", "--password", help=f"SWITCH edu-ID password ({PASSWORD_KEY})")
    parser.add_argument(
        "-l",
        "--lesson-id",
        help=f"number at the end of schalter.asvz.ch/tn/lessons/<number> ({LESSON_ID_KEY})",
    )
    parser.add_argument(
        "--check-login", action="store_true", help="only test the login, do not enrol"
    )
    return parser.parse_args(arguments)
