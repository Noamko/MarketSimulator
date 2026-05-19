from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def is_market_open(now: datetime | None = None) -> bool:
    """US equities regular session: Mon-Fri, 09:30-16:00 America/New_York.

    Uses zoneinfo so DST transitions are handled automatically. Does not
    account for NYSE holidays (Christmas, Thanksgiving, etc.) — on those
    days the indicator will say "open" but the Finnhub WS will be silent.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    eastern = now.astimezone(NY)
    if eastern.weekday() >= 5:
        return False
    return time(9, 30) <= eastern.time() <= time(16, 0)
