import json
from pathlib import Path

import pytest
import respx

from asvz_enroll import cli
from asvz_enroll.email_notification import BREVO_SEND_EMAIL_URL, send_email
from asvz_enroll.errors import EmailNotSentError, MissingSettingsError
from asvz_enroll.settings import EmailSettings, read_email_settings

SETTINGS = EmailSettings(
    recipient="me@example.org", sender="robot@example.org", brevo_api_key="key-123"
)


def test_no_recipient_means_no_email(tmp_path: Path) -> None:
    assert read_email_settings(tmp_path / "no-such-file") is None


def test_recipient_without_brevo_settings_is_an_error(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ASVZ_EMAIL_RECIPIENT=me@example.org\n")

    with pytest.raises(MissingSettingsError, match="BREVO_API_KEY"):
        read_email_settings(env_file)


def test_api_key_is_not_shown_when_settings_are_printed() -> None:
    assert "key-123" not in repr(SETTINGS)


@respx.mock
def test_send_email_asks_brevo_to_send_it() -> None:
    route = respx.post(BREVO_SEND_EMAIL_URL).respond(201, json={"messageId": "<1@brevo>"})

    send_email(SETTINGS, "ASVZ enrolment succeeded", "Enrolled: Karate, place 4.")

    sent = route.calls.last.request
    assert sent.headers["api-key"] == "key-123"
    assert json.loads(sent.content) == {
        "sender": {"name": "ASVZ enrolment", "email": "robot@example.org"},
        "to": [{"email": "me@example.org"}],
        "subject": "ASVZ enrolment succeeded",
        "textContent": "Enrolled: Karate, place 4.",
    }


@respx.mock
def test_refused_email_shows_what_brevo_said() -> None:
    respx.post(BREVO_SEND_EMAIL_URL).respond(401, text="Key not found")

    with pytest.raises(EmailNotSentError, match="401.*Key not found"):
        send_email(SETTINGS, "subject", "text")


@respx.mock
def test_failed_enrolment_is_emailed_and_keeps_its_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".env").write_text(
        "ASVZ_EMAIL_RECIPIENT=me@example.org\n"
        "BREVO_API_KEY=key-123\n"
        "BREVO_SENDER_EMAIL=robot@example.org\n"
    )
    monkeypatch.chdir(tmp_path)
    route = respx.post(BREVO_SEND_EMAIL_URL).respond(201, json={})

    exit_code = cli.main([])  # no username, password or lesson id anywhere

    assert exit_code == 2
    email = json.loads(route.calls.last.request.content)
    assert email["subject"] == "ASVZ enrolment failed"
    assert "ASVZ_USERNAME" in email["textContent"]
    assert "Email sent to me@example.org." in capsys.readouterr().out


@respx.mock
def test_email_links_to_the_lesson_page_so_the_enrolment_can_be_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text(
        "ASVZ_USERNAME=me@example.org\nASVZ_PASSWORD=secret\nASVZ_LESSON_ID=1\n"
        "ASVZ_EMAIL_RECIPIENT=me@example.org\n"
        "BREVO_API_KEY=key-123\n"
        "BREVO_SENDER_EMAIL=robot@example.org\n"
    )
    monkeypatch.chdir(tmp_path)
    respx.get("https://schalter.asvz.ch/tn-api/api/Lessons/1").respond(404)
    route = respx.post(BREVO_SEND_EMAIL_URL).respond(201, json={})

    exit_code = cli.main([])

    assert exit_code == 1
    text = json.loads(route.calls.last.request.content)["textContent"]
    assert text.startswith("Error: ASVZ has no lesson with id 1.")
    assert text.endswith("https://schalter.asvz.ch/tn/lessons/1")
    assert "secret" not in text
