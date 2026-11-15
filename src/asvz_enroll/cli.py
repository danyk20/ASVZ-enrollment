"""The command line: read what to do, log in, enrol, say what happened, email it."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

import httpx

from asvz_enroll.email_notification import send_email
from asvz_enroll.errors import AsvzEnrollError, EnrolmentWindowError, MissingSettingsError
from asvz_enroll.lesson_api import enrol, get_lesson, lesson_page_url, my_enrolment
from asvz_enroll.login import log_in
from asvz_enroll.models import Lesson
from asvz_enroll.settings import (
    LESSON_ID_KEY,
    PASSWORD_KEY,
    USERNAME_KEY,
    read_email_settings,
    read_enrolment_request,
)

EXIT_OK = 0
EXIT_NETWORK_PROBLEM = 4


@dataclass(frozen=True)
class Outcome:
    """How a run ended: the sentence for the user and the program's exit code."""

    message: str
    exit_code: int

    @property
    def succeeded(self) -> bool:
        return self.exit_code == EXIT_OK


def main(arguments: Sequence[str] | None = None) -> int:
    options = _read_options(arguments)

    if options.check_login:
        outcome = _attempt(check_login, options)
        _print(outcome)
    else:
        outcome = _attempt(enrol_in_lesson, options)
        _print(outcome)
        _email(outcome, _lesson_page_url(options))

    return outcome.exit_code


def enrol_in_lesson(options: argparse.Namespace) -> str:
    request = read_enrolment_request(options.username, options.password, options.lesson_id)

    lesson = get_lesson(request.lesson_id)
    _require_open_enrolment(lesson)

    token = log_in(request.username, request.password)

    existing_enrolment = my_enrolment(lesson.id, token)
    if existing_enrolment:
        return f"Already enrolled: {lesson.describe()}, place {existing_enrolment.place_number}."

    enrolment = enrol(lesson.id, token)
    return f"Enrolled: {lesson.describe()}, place {enrolment.place_number}."


def check_login(options: argparse.Namespace) -> str:
    """Log in without enrolling, to test the username and password."""
    request = read_enrolment_request(options.username, options.password, options.lesson_id or "0")
    token = log_in(request.username, request.password)
    return f"Login ok, token valid until {token.expires_at.astimezone():%H:%M}."


def _attempt(action: Callable[[argparse.Namespace], str], options: argparse.Namespace) -> Outcome:
    """Run the action and turn whatever happens, success or failure, into an Outcome."""
    try:
        return Outcome(action(options), EXIT_OK)
    except AsvzEnrollError as error:
        return Outcome(f"Error: {error}", error.exit_code)
    except httpx.HTTPError as error:
        return Outcome(f"Network problem: {error}", EXIT_NETWORK_PROBLEM)


def _print(outcome: Outcome) -> None:
    print(outcome.message, file=sys.stdout if outcome.succeeded else sys.stderr)


def _email(outcome: Outcome, lesson_url: str | None) -> None:
    """Email the outcome if the .env file names a recipient. A failed email is only a warning:
    it must not change whether the enrolment itself counts as succeeded."""
    try:
        email_settings = read_email_settings()
        if email_settings is None:
            return
        subject = "ASVZ enrolment succeeded" if outcome.succeeded else "ASVZ enrolment failed"
        send_email(email_settings, subject, _email_text(outcome, lesson_url))
        print(f"Email sent to {email_settings.recipient}.")
    except (AsvzEnrollError, httpx.HTTPError) as error:
        print(f"Warning: no email was sent. {error}", file=sys.stderr)


def _email_text(outcome: Outcome, lesson_url: str | None) -> str:
    if lesson_url is None:
        return outcome.message
    return f"{outcome.message}\n\nView the lesson, enrol or cancel your enrolment:\n{lesson_url}"


def _lesson_page_url(options: argparse.Namespace) -> str | None:
    """The lesson's web page, or None if the settings are too incomplete to know the lesson."""
    try:
        request = read_enrolment_request(options.username, options.password, options.lesson_id)
    except MissingSettingsError:
        return None
    return lesson_page_url(request.lesson_id)


def _require_open_enrolment(lesson: Lesson) -> None:
    now = datetime.now().astimezone()
    if now < lesson.enrolment_opens:
        raise EnrolmentWindowError(
            f"Enrolment for {lesson.describe()} opens {lesson.enrolment_opens:%a %d %b %H:%M}."
        )
    if not lesson.enrolment_is_open(now):
        raise EnrolmentWindowError(
            f"Enrolment for {lesson.describe()} closed {lesson.enrolment_closes:%a %d %b %H:%M}."
        )


def _read_options(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="asvz-enroll",
        description="Enrol in an ASVZ lesson right now.",
        epilog="Any option you leave out is read from the .env file in the current folder.",
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
