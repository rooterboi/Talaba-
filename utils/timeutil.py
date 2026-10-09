from datetime import date, datetime, timedelta

from config import TZ

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


def now() -> datetime:
    """Toshkent vaqti (naive datetime) — bazada ham shu vaqt saqlanadi."""
    return datetime.now(TZ).replace(tzinfo=None)


def today() -> date:
    return now().date()


def week_parity(d: date) -> int:
    """1 = toq hafta, 2 = juft hafta (ISO hafta raqami bo'yicha)."""
    return 1 if d.isocalendar()[1] % 2 == 1 else 2


def parse_deadline(text: str) -> datetime | None:
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def human_delta(td: timedelta) -> str:
    s = int(td.total_seconds())
    if s <= 0:
        return "muddati o'tgan"
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = []
    if d:
        parts.append(f"{d} kun")
    if h:
        parts.append(f"{h} soat")
    if m and not d:
        parts.append(f"{m} daqiqa")
    return " ".join(parts) or "1 daqiqadan kam"
