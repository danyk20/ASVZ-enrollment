"""Decides who enrols in what: command-line options first, the .env file second."""

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from asvz_enroll.errors import MissingSettingsError

USERNAME_KEY = "ASVZ_USERNAME"
PASSWORD_KEY = "ASVZ_PASSWORD"
LESSON_ID_KEY = "ASVZ_LESSON_ID"

DEFAULT_ENV_FILE = Path(".env")


@dataclass(frozen=True)
class EnrolmentRequest:
    username: str
    password: str = field(repr=False)
    lesson_id: int


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
    )


def _as_lesson_id(text: str) -> int:
    if not text.isdigit():
        raise MissingSettingsError(
            f"The lesson id must be a number like 781265, not {text!r}. "
            "It is the last part of https://schalter.asvz.ch/tn/lessons/<number>."
        )
    return int(text)
