"""The command line: read what to do, log in, enrol, say what happened."""

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime

import httpx

from asvz_enroll.errors import AsvzEnrollError, EnrolmentWindowError
from asvz_enroll.lesson_api import enrol, get_lesson, my_enrolment
from asvz_enroll.login import log_in
from asvz_enroll.models import Lesson
from asvz_enroll.settings import LESSON_ID_KEY, PASSWORD_KEY, USERNAME_KEY, read_enrolment_request

EXIT_OK = 0
EXIT_NETWORK_PROBLEM = 4


def main(arguments: Sequence[str] | None = None) -> int:
    options = _read_options(arguments)
    try:
        if options.check_login:
            print(check_login(options))
        else:
            print(enrol_in_lesson(options))
    except AsvzEnrollError as error:
        print(f"Error: {error}", file=sys.stderr)
        return error.exit_code
    except httpx.HTTPError as error:
        print(f"Network problem: {error}", file=sys.stderr)
        return EXIT_NETWORK_PROBLEM
    return EXIT_OK


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
