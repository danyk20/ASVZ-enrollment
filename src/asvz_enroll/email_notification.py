"""Sends one plain-text email through Brevo.

Brevo documents this call as "Send a transactional email" at https://developers.brevo.com.
"""

import httpx

from asvz_enroll.errors import EmailNotSentError
from asvz_enroll.settings import EmailSettings

BREVO_SEND_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT_SECONDS = 30


def send_email(settings: EmailSettings, subject: str, text: str) -> None:
    response = httpx.post(
        BREVO_SEND_EMAIL_URL,
        headers={"api-key": settings.brevo_api_key},
        json={
            "sender": {"name": "ASVZ enrolment", "email": settings.sender},
            "to": [{"email": settings.recipient}],
            "subject": subject,
            "textContent": text,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if response.is_error:
        raise EmailNotSentError(
            f"Brevo refused the email (HTTP {response.status_code}): {response.text[:300]}"
        )
