from datetime import datetime, timedelta

import pytest

from asvz_enroll import cli
from asvz_enroll.cli import _require_reachable_enrolment
from asvz_enroll.enrolment_timing import safe_sending_time, wait_until
from asvz_enroll.errors import EnrolmentWindowError
from asvz_enroll.models import AccessToken, Enrolment, Lesson
from asvz_enroll.settings import EnrolmentRequest

OPENS = datetime.fromisoformat("2026-11-14T19:00:00+01:00")
TOKEN = AccessToken(value="test-token", expires_at=OPENS + timedelta(hours=12))

LESSON = Lesson(
    id=781265,
    sport_name="Shotokan Karate",
    title="Training",
    starts=OPENS + timedelta(days=3),
    enrolment_opens=OPENS,
    enrolment_closes=OPENS + timedelta(days=3),
    places_total=20,
    places_taken=4,
)


def test_request_is_sent_35_to_55_seconds_after_opening() -> None:
    delays = [(safe_sending_time(OPENS) - OPENS).total_seconds() for _ in range(1000)]

    assert all(35 <= delay <= 55 for delay in delays)
    assert max(delays) - min(delays) > 10  # really random, not one fixed delay


def test_wait_until_sleeps_for_the_time_that_is_left() -> None:
    slept: list[float] = []

    wait_until(OPENS + timedelta(seconds=47), clock=lambda: OPENS, sleep=slept.append)

    assert slept == [47.0]


def test_wait_until_returns_at_once_when_the_moment_has_passed() -> None:
    slept: list[float] = []

    wait_until(OPENS, clock=lambda: OPENS + timedelta(seconds=5), sleep=slept.append)

    assert slept == []


@pytest.mark.parametrize(
    "time_from_opening",
    [timedelta(seconds=-0.4), timedelta(minutes=-10), timedelta(0), timedelta(days=1)],
)
def test_a_run_shortly_before_or_during_the_window_is_accepted(
    time_from_opening: timedelta,
) -> None:
    _require_reachable_enrolment(LESSON, OPENS + time_from_opening)


def test_a_run_long_before_opening_says_how_early_it_was() -> None:
    with pytest.raises(EnrolmentWindowError) as error:
        _require_reachable_enrolment(LESSON, datetime.fromisoformat("2026-11-12T17:35:12+01:00"))

    assert "This attempt ran Thu 12 Nov 17:35:12, 2 days, 1:24:48 too early." in str(error.value)
    assert "at most 0:10:00 away" in str(error.value)


def test_a_run_after_the_window_says_how_late_it_was() -> None:
    with pytest.raises(EnrolmentWindowError, match="0:05:00 too late"):
        _require_reachable_enrolment(LESSON, LESSON.enrolment_closes + timedelta(minutes=5))


def test_enrolment_waits_for_the_safe_sending_time_then_enrols(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    opens_just_now = datetime.now().astimezone()
    lesson = Lesson(
        **{
            **LESSON.__dict__,
            "enrolment_opens": opens_just_now,
            "enrolment_closes": opens_just_now + timedelta(days=1),
        }
    )
    steps: list[str] = []
    waited_until: list[datetime] = []

    def log_in(*_: object) -> AccessToken:
        steps.append("log in")
        return TOKEN

    def my_enrolment(*_: object) -> None:
        steps.append("check")

    def wait_until(moment: datetime) -> None:
        steps.append("wait")
        waited_until.append(moment)

    def enrol(*_: object) -> Enrolment:
        steps.append("enrol")
        return Enrolment(place_number=7)

    for name, fake in [
        ("log_in", log_in),
        ("my_enrolment", my_enrolment),
        ("wait_until", wait_until),
        ("enrol", enrol),
    ]:
        monkeypatch.setattr(cli, name, fake)

    message = cli._enrol(
        EnrolmentRequest("me@example.org", "secret", 781265), lesson, opens_just_now
    )

    assert steps == ["log in", "check", "wait", "enrol"]
    assert 35 <= (waited_until[0] - opens_just_now).total_seconds() <= 55
    assert message.startswith("Enrolled: Shotokan Karate: Training")
    assert "in case this computer's clock is behind" in capsys.readouterr().out
