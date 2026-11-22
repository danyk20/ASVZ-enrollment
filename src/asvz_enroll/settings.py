"""Decides who enrols in what: command-line options first, the .env file second."""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values

from asvz_enroll.enrolment_timing import DEFAULT_LONGEST_WAIT_FOR_OPENING
from asvz_enroll.errors import MissingSettingsError

USERNAME_KEY = "ASVZ_USERNAME"
PASSWORD_KEY = "ASVZ_PASSWORD"
LESSON_ID_KEY = "ASVZ_LESSON_ID"
EARLY_START_MINUTES_KEY = "ASVZ_EARLY_START_MINUTES"

EMAIL_RECIPIENT_KEY = "ASVZ_EMAIL_RECIPIENT"
BREVO_API_KEY_KEY = "BREVO_API_KEY"
BREVO_SENDER_KEY = "BREVO_SENDER_EMAIL"

DEFAULT_ENV_FILE = Path(".env")


@dataclass(frozen=True)
class EmailSettings:
    recipient: str
    sender: str
    brevo_api_key: str = field(repr=False)


def read_email_settings(env_file: Path = DEFAULT_ENV_FILE) -> EmailSettings | None:
    """Who gets the result by email, or None if the .env file names no recipient."""
    from_env_file = dotenv_values(env_file)
    recipient = from_env_file.get(EMAIL_RECIPIENT_KEY)
    if not recipient:
        return None

    api_key = from_env_file.get(BREVO_API_KEY_KEY)
    sender = from_env_file.get(BREVO_SENDER_KEY)
    if not api_key or not sender:
        raise MissingSettingsError(
            f"{EMAIL_RECIPIENT_KEY} is set, so {BREVO_API_KEY_KEY} and {BREVO_SENDER_KEY} "
            f"must be set in {env_file} too."
        )
    return EmailSettings(recipient=recipient, sender=sender, brevo_api_key=api_key)


@dataclass(frozen=True)
class EnrolmentRequest:
    username: str
    password: str = field(repr=False)
    lesson_id: int
    longest_wait_for_opening: timedelta = DEFAULT_LONGEST_WAIT_FOR_OPENING


def read_enrolment_request(
    username: str | None,
    password: str | None,
    lesson_id: str | None,
    env_file: Path = DEFAULT_ENV_FILE,
) -> EnrolmentRequest:
    """Combine the options given on the command line with the values in the .env file."""
    from_env_file = dotenv_values(env_file)
    chosen = {
        USERNAME_KEY: username or from_env_file.get(USERNAME_KEY),
        PASSWORD_KEY: password or from_env_file.get(PASSWORD_KEY),
        LESSON_ID_KEY: lesson_id or from_env_file.get(LESSON_ID_KEY),
    }

    missing = [key for key, value in chosen.items() if not value]
    if missing:
        raise MissingSettingsError(
            f"Missing: {', '.join(missing)}. Give it as an option or put it in {env_file}."
        )

    return EnrolmentRequest(
        username=str(chosen[USERNAME_KEY]),
        password=str(chosen[PASSWORD_KEY]),
        lesson_id=_as_lesson_id(str(chosen[LESSON_ID_KEY])),
        longest_wait_for_opening=_as_longest_wait(from_env_file.get(EARLY_START_MINUTES_KEY)),
    )


def _as_lesson_id(text: str) -> int:
    if not text.isdigit():
        raise MissingSettingsError(
            f"The lesson id must be a number like 781265, not {text!r}. "
            "It is the last part of https://schalter.asvz.ch/tn/lessons/<number>."
        )
    return int(text)


def _as_longest_wait(minutes: str | None) -> timedelta:
    """How long before enrolment opens the app may be started; the default if not set."""
    if not minutes:
        return DEFAULT_LONGEST_WAIT_FOR_OPENING
    if not minutes.isdigit():
        raise MissingSettingsError(
            f"{EARLY_START_MINUTES_KEY} must be a whole number of minutes like 10, not {minutes!r}."
        )
    return timedelta(minutes=int(minutes))
