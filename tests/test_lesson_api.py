from datetime import UTC, datetime

import httpx
import pytest
import respx

from asvz_enroll.errors import EnrolmentRefusedError, LessonNotFoundError
from asvz_enroll.lesson_api import API_URL, enrol, get_lesson, my_enrolment
from asvz_enroll.models import AccessToken

TOKEN = AccessToken(value="test-token", expires_at=datetime(2030, 1, 1, tzinfo=UTC))

# Shape copied from the real answer recorded in traffic-notes.md.
LESSON_ANSWER = {
    "data": {
        "id": 781265,
        "sportName": "Shotokan Karate",
        "title": "Training",
        "starts": "2026-11-17T19:00:00+01:00",
        "enrollmentFrom": "2026-11-14T19:00:00+01:00",
        "enrollmentUntil": "2026-11-17T19:00:00+01:00",
        "participantsMax": 20,
        "participantCount": 4,
    }
}


@respx.mock
def test_get_lesson_reads_the_fields_we_need() -> None:
    respx.get(f"{API_URL}/Lessons/781265").respond(json=LESSON_ANSWER)

    lesson = get_lesson(781265)

    assert lesson.describe() == "Shotokan Karate: Training, Tue 17 Nov 2026 19:00"
    assert lesson.enrolment_is_open(datetime.fromisoformat("2026-11-15T12:00:00+01:00"))
    assert not lesson.enrolment_is_open(datetime.fromisoformat("2026-11-14T18:59:00+01:00"))


@respx.mock
def test_unknown_lesson() -> None:
    respx.get(f"{API_URL}/Lessons/1").respond(404)

    with pytest.raises(LessonNotFoundError):
        get_lesson(1)


@respx.mock
def test_enrol_sends_token_and_empty_json_object() -> None:
    route = respx.post(f"{API_URL}/Lessons/781265/Enrollment").respond(
        201, json={"data": {"placeNumber": 4, "statusId": 4}}
    )

    enrolment = enrol(781265, TOKEN)

    assert enrolment.place_number == 4
    sent: httpx.Request = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer test-token"
    assert sent.content == b"{}"


@respx.mock
def test_refused_enrolment_shows_what_asvz_said() -> None:
    respx.post(f"{API_URL}/Lessons/781265/Enrollment").respond(422, text="lesson is full")

    with pytest.raises(EnrolmentRefusedError, match="422.*lesson is full"):
        enrol(781265, TOKEN)


@respx.mock
def test_my_enrolment_is_none_when_not_enrolled() -> None:
    respx.get(f"{API_URL}/Lessons/781265/MyEnrollment").respond(404)

    assert my_enrolment(781265, TOKEN) is None


@respx.mock
def test_my_enrolment_reads_an_active_enrolment() -> None:
    respx.get(f"{API_URL}/Lessons/781265/MyEnrollment").respond(
        json={"data": {"status": 4, "statusInfo": "4 - definitiv", "placeNumber": 19}}
    )

    enrolment = my_enrolment(781265, TOKEN)

    assert enrolment is not None
    assert enrolment.place_number == 19


@respx.mock
def test_a_cancelled_enrolment_does_not_count_as_enrolled() -> None:
    # Real answer after cancelling on the lesson page.
    respx.get(f"{API_URL}/Lessons/781265/MyEnrollment").respond(
        json={"data": {"status": 6, "statusInfo": "6 - abgemeldet", "placeNumber": 0}}
    )

    assert my_enrolment(781265, TOKEN) is None
