"""Everything that can go wrong, one exception each.

Every error carries the exit code the program ends with, so cli.py needs no table.
"""


class AsvzEnrollError(Exception):
    """Base class: any failure this app knows how to explain."""

    exit_code = 1


class MissingSettingsError(AsvzEnrollError):
    """Username, password or lesson id was given neither as an option nor in .env."""

    exit_code = 2


class LoginError(AsvzEnrollError):
    """The login did not end with an access token."""

    exit_code = 3


class WrongCredentialsError(LoginError):
    """SWITCH edu-ID asked for the username or password a second time."""


class UnexpectedLoginPageError(LoginError):
    """The login showed a page this app does not know how to answer."""


class LessonNotFoundError(AsvzEnrollError):
    """ASVZ has no lesson with this id."""


class EnrolmentWindowError(AsvzEnrollError):
    """The lesson exists but enrolment is not open right now."""


class EnrolmentRefusedError(AsvzEnrollError):
    """ASVZ answered the enrolment request with an error."""
