"""Ziua si ora se calculeaza mereu in ora Romaniei, indiferent de fusul serverului."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Bucharest")


def now() -> datetime:
    return datetime.now(TZ).replace(microsecond=0)


def local(dt: datetime) -> datetime:
    """Ora din baza de date, afisata in ora Romaniei."""
    if dt.tzinfo is None:  # SQLite intoarce ore fara fus; le salvam in ora Romaniei
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def today() -> date:
    return now().date()
