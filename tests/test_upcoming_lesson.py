from datetime import datetime, timedelta

import pytest
import respx

from asvz_enroll.errors import NoUpcomingLessonError
from asvz_enroll.lesson_api import API_URL
from asvz_enroll.models import Lesson
from asvz_enroll.upcoming_lesson import find_upcoming_lesson, weeks_until_upcoming_lesson

LESSON_START = datetime.fromisoformat("2026-11-03T19:00:00+01:00")  # a Tuesday


@pytest.mark.parametrize(
    ("time_since_start", "expected_weeks"),
    [
        (timedelta(days=-2), 0),  # not started yet: keep this lesson
        (timedelta(minutes=1), 1),  # just started: next week
        (timedelta(days=6, hours=23), 1),
        (timedelta(days=7), 2),  # next week's lesson starts this very moment: too late
        (timedelta(days=10), 2),
        (timedelta(days=15), 3),
    ],
)
def test_weeks_until_upcoming_lesson(time_since_start: timedelta, expected_weeks: int) -> None:
    now = LESSON_START + time_since_start
    assert weeks_until_upcoming_lesson(LESSON_START, now) == expected_weeks


def _karate(lesson_id: int, starts: str, sport_name: str = "Shotokan Karate") -> Lesson:
    start = datetime.fromisoformat(starts)
    return Lesson(
        id=lesson_id,
        sport_name=sport_name,
        title="Training",
        starts=start,
        enrolment_opens=start - timedelta(days=3),
        enrolment_closes=start,
        places_total=20,
        places_taken=4,
    )


def _asvz_answer(lesson: Lesson) -> dict[str, object]:
    return {
        "data": {
            "id": lesson.id,
            "sportName": lesson.sport_name,
            "title": lesson.title,
            "starts": lesson.starts.isoformat(),
            "enrollmentFrom": lesson.enrolment_opens.isoformat(),
            "enrollmentUntil": lesson.enrolment_closes.isoformat(),
            "participantsMax": lesson.places_total,
            "participantCount": lesson.places_taken,
        }
    }


def test_a_lesson_that_has_not_started_is_kept_without_asking_asvz() -> None:
    lesson = _karate(781265, "2026-11-17T19:00:00+01:00")
    now = datetime.fromisoformat("2026-11-15T12:00:00+01:00")

    assert find_upcoming_lesson(lesson, now) is lesson


@respx.mock
def test_a_lesson_ten_days_ago_moves_two_ids_ahead() -> None:
    old_lesson = _karate(781263, "2026-11-03T19:00:00+01:00")
    upcoming = _karate(781265, "2026-11-17T19:00:00+01:00")
    respx.get(f"{API_URL}/Lessons/781265").respond(json=_asvz_answer(upcoming))
    now = old_lesson.starts + timedelta(days=10)

    assert find_upcoming_lesson(old_lesson, now) == upcoming


@respx.mock
def test_summer_and_winter_time_do_not_break_the_series_check() -> None:
    old_lesson = _karate(781260, "2026-10-13T19:00:00+02:00")  # summer time
    upcoming = _karate(781265, "2026-11-17T19:00:00+01:00")  # winter time
    respx.get(f"{API_URL}/Lessons/781265").respond(json=_asvz_answer(upcoming))
    now = datetime.fromisoformat("2026-11-15T12:00:00+01:00")

    assert find_upcoming_lesson(old_lesson, now) == upcoming


@respx.mock
def test_a_different_lesson_under_the_calculated_id_is_refused() -> None:
    old_lesson = _karate(781263, "2026-11-03T19:00:00+01:00")
    something_else = _karate(781265, "2026-11-17T19:00:00+01:00", sport_name="Yoga")
    respx.get(f"{API_URL}/Lessons/781265").respond(json=_asvz_answer(something_else))
    now = old_lesson.starts + timedelta(days=10)

    with pytest.raises(NoUpcomingLessonError, match="series has probably ended"):
        find_upcoming_lesson(old_lesson, now)
