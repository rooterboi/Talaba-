import time

from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy import select

from config import ADMIN_IDS
from database.base import SessionMaker
from database.models import User


class DbSessionMiddleware(BaseMiddleware):
    """Har update uchun: DB sessiya, `user` (ro'yxatdan o'tgan bo'lsa), `is_super`. Oxirida commit."""

    async def __call__(self, handler, event: Update, data: dict):
        tg = data.get("event_from_user")
        async with SessionMaker() as session:
            user = None
            if tg:
                user = (await session.execute(select(User).where(User.tg_id == tg.id))).scalar_one_or_none()
                if user and user.banned:
                    return
                if user and user.username != tg.username:
                    user.username = tg.username
            data.update(session=session, user=user, is_super=bool(tg and tg.id in ADMIN_IDS))
            try:
                res = await handler(event, data)
                await session.commit()
                return res
            except Exception:
                await session.rollback()
                raise


class ThrottleMiddleware(BaseMiddleware):
    """Spamdan himoya: bir foydalanuvchidan 0.4s ichida kelgan ortiqcha xabarlar tashlanadi."""

    def __init__(self, interval: float = 0.4):
        self.interval = interval
        self._last: dict[int, float] = {}

    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u:
            t = time.monotonic()
            if t - self._last.get(u.id, 0) < self.interval:
                return
            self._last[u.id] = t
            if len(self._last) > 50000:
                self._last.clear()
        return await handler(event, data)
