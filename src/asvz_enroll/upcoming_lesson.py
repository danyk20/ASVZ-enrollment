"""Turns the id of a past lesson into the next upcoming lesson of the same weekly series.

ASVZ numbers the lessons of a weekly series consecutively: next week's lesson has this
week's id plus one (checked on real data, see traffic-notes.md). So the upcoming lesson is
found with one calculation instead of a search.
"""

import math
from datetime import datetime, timedelta

from asvz_enroll.errors import NoUpcomingLessonError
from asvz_enroll.lesson_api import get_lesson
from asvz_enroll.models import Lesson

ONE_WEEK = timedelta(weeks=1)


def weeks_until_upcoming_lesson(lesson_start: datetime, now: datetime) -> int:
    """How many weeks after this lesson the first one that has not started yet takes place.

    A lesson that started 10 days ago: the one a week later is past too (3 days ago),
    the one two weeks later is 4 days ahead, so the answer is 2.
    """
    if lesson_start > now:
        return 0
    return math.floor((now - lesson_start) / ONE_WEEK) + 1


def find_upcoming_lesson(lesson: Lesson, now: datetime) -> Lesson:
    """The lesson itself if it has not started yet, otherwise its next occurrence."""
    weeks_ahead = weeks_until_upcoming_lesson(lesson.starts, now)
    if weeks_ahead == 0:
        return lesson

    upcoming = get_lesson(lesson.id + weeks_ahead)
    if not upcoming.is_in_same_weekly_slot_as(lesson) or upcoming.starts <= now:
        raise NoUpcomingLessonError(
            f"Lesson {lesson.id} ({lesson.describe()}) is over, and lesson {upcoming.id} "
            f"({upcoming.describe()}) is not its next occurrence. "
            "The series has probably ended; look up the new lesson id on asvz.ch."
        )
    return upcoming
