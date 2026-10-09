import math
from datetime import date

from sqlalchemy import case, func, select

from config import XP_DAILY_BONUS
from database.models import Group, Institution, Role, User, XPLog
from utils.timeutil import now, today

TITLES = ["Yangi talaba", "Izlanuvchi", "Bilimdon", "Faol talaba", "Mutaxassis", "Ekspert", "Ustoz shogirdi", "Afsona"]
STUDENTS = User.role.in_([Role.STUDENT, Role.LEADER, Role.DEPUTY])


def level(xp: int) -> int:
    return int(math.sqrt(max(xp, 0) / 25)) + 1


def level_title(xp: int) -> str:
    return TITLES[min(level(xp) - 1, len(TITLES) - 1)]


async def add_xp(session, user: User, amount: int, reason: str):
    if amount == 0:
        return
    user.xp = max(0, (user.xp or 0) + amount)
    session.add(XPLog(user_id=user.id, amount=amount, reason=reason, created_at=now()))


async def xp_today(session, user_id: int, reason: str) -> int:
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    r = await session.scalar(select(func.coalesce(func.sum(XPLog.amount), 0)).where(
        XPLog.user_id == user_id, XPLog.reason == reason, XPLog.created_at >= start))
    return int(r or 0)


async def daily_bonus(session, user: User) -> int:
    if user.last_bonus == today():
        return 0
    user.last_bonus = today()
    if user.role != Role.TEACHER:
        await add_xp(session, user, XP_DAILY_BONUS, "daily")
        return XP_DAILY_BONUS
    return 0


async def top_users(session, *, group_id=None, institution_id=None, limit=10):
    q = select(User).where(STUDENTS, User.banned.is_(False))
    if group_id:
        q = q.where(User.group_id == group_id)
    if institution_id:
        q = q.where(User.institution_id == institution_id)
    return (await session.execute(q.order_by(User.xp.desc(), User.id).limit(limit))).scalars().all()


async def rank_of(session, user: User, *, group_id=None, institution_id=None) -> int:
    q = select(func.count(User.id)).where(STUDENTS, User.xp > user.xp)
    if group_id:
        q = q.where(User.group_id == group_id)
    if institution_id:
        q = q.where(User.institution_id == institution_id)
    return int(await session.scalar(q) or 0) + 1


async def institutions_ranking(session, limit=10):
    q = (select(Institution.name, func.coalesce(func.sum(User.xp), 0), func.count(User.id))
         .join(User, User.institution_id == Institution.id)
         .where(STUDENTS).group_by(Institution.id)
         .order_by(func.sum(User.xp).desc()).limit(limit))
    return (await session.execute(q)).all()
