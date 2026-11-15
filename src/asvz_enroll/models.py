"""The few things this app talks about: a token, a lesson, an enrolment."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AccessToken:
    """Proof of login that the ASVZ API accepts for 12 hours."""

    value: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class Lesson:
    id: int
    sport_name: str
    title: str
    starts: datetime
    enrolment_opens: datetime
    enrolment_closes: datetime
    places_total: int
    places_taken: int

    def enrolment_is_open(self, now: datetime) -> bool:
        return self.enrolment_opens <= now <= self.enrolment_closes

    def is_in_same_weekly_slot_as(self, other: "Lesson") -> bool:
        """Same sport and title, on the same weekday at the same time of day."""
        return (
            self.sport_name == other.sport_name
            and self.title == other.title
            and self.starts.weekday() == other.starts.weekday()
            and self.starts.time() == other.starts.time()
        )

    def describe(self) -> str:
        return f"{self.sport_name}: {self.title}, {self.starts:%a %d %b %Y %H:%M}"


@dataclass(frozen=True)
class Enrolment:
    place_number: int
