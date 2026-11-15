"""The ASVZ lesson API (see "API calls" in traffic-notes.md)."""

from datetime import datetime

import httpx

from asvz_enroll.errors import EnrolmentRefusedError, LessonNotFoundError
from asvz_enroll.models import AccessToken, Enrolment, Lesson

API_URL = "https://schalter.asvz.ch/tn-api/api"
LESSON_PAGES_URL = "https://schalter.asvz.ch/tn/lessons"
TIMEOUT_SECONDS = 30

# Values of "status" in an enrolment record. Seen so far: 4 "definitiv", 6 "abgemeldet".
ENROLMENT_STATUS_CANCELLED = 6


def lesson_page_url(lesson_id: int) -> str:
    """The web page where a person can view the lesson and cancel the enrolment."""
    return f"{LESSON_PAGES_URL}/{lesson_id}"


def get_lesson(lesson_id: int) -> Lesson:
    """Lesson details are public, so this needs no login."""
    response = httpx.get(f"{API_URL}/Lessons/{lesson_id}", timeout=TIMEOUT_SECONDS)
    if response.status_code == httpx.codes.NOT_FOUND:
        raise LessonNotFoundError(f"ASVZ has no lesson with id {lesson_id}.")
    response.raise_for_status()

    data = response.json()["data"]
    return Lesson(
        id=data["id"],
        sport_name=data["sportName"],
        title=data["title"],
        starts=datetime.fromisoformat(data["starts"]),
        enrolment_opens=datetime.fromisoformat(data["enrollmentFrom"]),
        enrolment_closes=datetime.fromisoformat(data["enrollmentUntil"]),
        places_total=data["participantsMax"],
        places_taken=data["participantCount"],
    )


def my_enrolment(lesson_id: int, token: AccessToken) -> Enrolment | None:
    """The enrolment I currently hold for this lesson, or None.

    ASVZ keeps a cancelled enrolment on record (status "6 - abgemeldet", place 0),
    so a record alone does not mean I hold a place.
    """
    response = httpx.get(
        f"{API_URL}/Lessons/{lesson_id}/MyEnrollment",
        headers=_authorisation(token),
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code == httpx.codes.NOT_FOUND:
        return None
    response.raise_for_status()

    record = response.json()["data"]
    if record["status"] == ENROLMENT_STATUS_CANCELLED:
        return None
    return Enrolment(place_number=record["placeNumber"])


def enrol(lesson_id: int, token: AccessToken) -> Enrolment:
    response = httpx.post(
        f"{API_URL}/Lessons/{lesson_id}/Enrollment",
        json={},  # the API wants an empty JSON object, not an empty body
        headers=_authorisation(token),
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != httpx.codes.CREATED:
        raise EnrolmentRefusedError(
            f"ASVZ refused the enrolment (HTTP {response.status_code}): {response.text[:500]}"
        )
    return Enrolment(place_number=response.json()["data"]["placeNumber"])


def _authorisation(token: AccessToken) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.value}"}
