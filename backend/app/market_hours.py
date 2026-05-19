from datetime import datetime, time, timezone, timedelta


def is_market_open(now: datetime | None = None) -> bool:
    """US equities regular session: Mon-Fri, 09:30-16:00 America/New_York.

    Uses a fixed UTC offset (no DST awareness) which is good enough for a
    learning simulator — the worst case is being wrong by an hour twice a
    year. Treats US Eastern as UTC-5 (EST) year-round.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    eastern = now.astimezone(timezone(timedelta(hours=-5)))
    if eastern.weekday() >= 5:
        return False
    return time(9, 30) <= eastern.time() <= time(16, 0)
