from pathlib import Path

import pytest

from asvz_enroll.errors import MissingSettingsError
from asvz_enroll.settings import read_enrolment_request


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    file = tmp_path / ".env"
    file.write_text("ASVZ_USERNAME=env@example.org\nASVZ_PASSWORD=env-secret\nASVZ_LESSON_ID=111\n")
    return file


def test_env_file_supplies_everything_when_no_options_are_given(env_file: Path) -> None:
    request = read_enrolment_request(None, None, None, env_file)

    assert (request.username, request.password, request.lesson_id) == (
        "env@example.org",
        "env-secret",
        111,
    )


def test_options_win_over_env_file(env_file: Path) -> None:
    request = read_enrolment_request("cli@example.org", None, "222", env_file)

    assert (request.username, request.password, request.lesson_id) == (
        "cli@example.org",
        "env-secret",
        222,
    )


def test_all_missing_values_are_named_at_once(tmp_path: Path) -> None:
    with pytest.raises(MissingSettingsError) as error:
        read_enrolment_request("someone@example.org", None, None, tmp_path / "no-such-file")

    assert "ASVZ_PASSWORD" in str(error.value)
    assert "ASVZ_LESSON_ID" in str(error.value)
    assert "ASVZ_USERNAME" not in str(error.value)


def test_lesson_id_must_be_a_number(env_file: Path) -> None:
    with pytest.raises(MissingSettingsError, match="must be a number"):
        read_enrolment_request(None, None, "karate", env_file)


def test_password_is_not_shown_when_the_request_is_printed(env_file: Path) -> None:
    assert "env-secret" not in repr(read_enrolment_request(None, None, None, env_file))
