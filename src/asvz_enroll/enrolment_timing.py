"""When to send the enrolment request.

Many computer clocks are a few seconds, sometimes half a minute, off. A request sent at the
opening second by such a clock can reach ASVZ before enrolment opens and is then refused.
So the app sends it a random 35 to 55 seconds after the opening time, measured on this
computer's clock. That covers clocks that are up to 35 seconds behind.
"""

import random
import time
from collections.abc import Callable
from datetime import datetime, timedelta

SHORTEST_DELAY_AFTER_OPENING = timedelta(seconds=35)
LONGEST_DELAY_AFTER_OPENING = timedelta(seconds=55)

# The app waits for the opening only if it is this close; a run started earlier is taken
# for a mistake. Users can change it in .env (ASVZ_EARLY_START_MINUTES, see settings.py).
DEFAULT_LONGEST_WAIT_FOR_OPENING = timedelta(minutes=10)


def safe_sending_time(enrolment_opens: datetime) -> datetime:
    """The opening time plus a random delay between the shortest and the longest."""
    delay = random.uniform(
        SHORTEST_DELAY_AFTER_OPENING.total_seconds(),
        LONGEST_DELAY_AFTER_OPENING.total_seconds(),
    )
    return enrolment_opens + timedelta(seconds=delay)


def wait_until(
    moment: datetime,
    clock: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Return at `moment` by this computer's clock; at once if it has already passed."""
    remaining = (moment - clock()).total_seconds()
    if remaining > 0:
        sleep(remaining)
