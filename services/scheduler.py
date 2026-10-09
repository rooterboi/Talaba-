"""APScheduler: dars va topshiriq eslatmalari."""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from config import LESSON_REMIND_MIN, TZ
from database.base import SessionMaker
from database.models import (Assignment, Group, ReminderLog, Role, Schedule, Submission,
                             TeacherGroup, User)
from services.notify import send_many
from utils.helpers import esc
from utils.timeutil import fmt_dt, human_delta, now, week_parity

log = logging.getLogger(__name__)


async def lesson_reminders(bot: Bot):
    n = now()
    today = n.date()
    parity = week_parity(today)
    async with SessionMaker() as s:
        rows = (await s.execute(select(Schedule).where(
            Schedule.weekday == today.weekday(), Schedule.week_type.in_([0, parity])))).scalars().all()
        for e in rows:
            mins = (datetime.combine(today, e.start_time) - n).total_seconds() / 60
            if not (0 < mins <= LESSON_REMIND_MIN):
                continue
            if await s.scalar(select(ReminderLog.id).where(ReminderLog.schedule_id == e.id, ReminderLog.day == today)):
                continue
            s.add(ReminderLog(schedule_id=e.id, day=today))
            await s.commit()
            group = await s.get(Group, e.group_id)
            ids = list((await s.scalars(select(User.tg_id).where(
                User.group_id == e.group_id, User.notify.is_(True), User.banned.is_(False)))).all())
            # shu fanni o'tadigan o'qituvchiga ham
            teachers = (await s.execute(select(User).join(TeacherGroup, TeacherGroup.teacher_id == User.id).where(
                TeacherGroup.group_id == e.group_id, User.notify.is_(True)))).scalars().all()
            for t in teachers:
                if t.full_name.split()[0].lower() in (e.teacher_name or "").lower():
                    ids.append(t.tg_id)
            text = (f"⏰ <b>{int(mins) + 1} daqiqadan so'ng dars boshlanadi!</b>\n\n"
                    f"📖 {esc(e.subject)} <i>({esc(e.lesson_type)})</i>\n"
                    f"🕐 {e.start_time:%H:%M}–{e.end_time:%H:%M}\n"
                    f"🚪 Xona: {esc(e.room)}\n👨‍🏫 {esc(e.teacher_name)}\n👥 {esc(group.name if group else '')}")
            await send_many(bot, set(ids), text)


async def assignment_reminders(bot: Bot):
    n = now()
    async with SessionMaker() as s:
        rows = (await s.execute(select(Assignment).where(
            Assignment.deadline > n, Assignment.deadline <= n + timedelta(hours=3),
            Assignment.reminded_1h.is_(False)))).scalars().all()
        for a in rows:
            left = a.deadline - n
            if left <= timedelta(hours=1):
                label = "1 soat"
                a.reminded_1h = a.reminded_3h = True
            elif not a.reminded_3h:
                label = "3 soat"
                a.reminded_3h = True
            else:
                continue
            await s.commit()
            submitted = select(Submission.student_id).where(Submission.assignment_id == a.id)
            ids = list((await s.scalars(select(User.tg_id).where(
                User.group_id == a.group_id, User.role.in_([Role.STUDENT, Role.LEADER, Role.DEPUTY]),
                User.notify.is_(True), User.banned.is_(False), User.id.not_in(submitted)))).all())
            text = (f"⚠️ <b>Topshiriq muddati {label}dan kam qoldi!</b>\n\n"
                    f"📖 {esc(a.subject)}\n📝 {esc(a.title)}\n"
                    f"⏳ Muddat: {fmt_dt(a.deadline)} ({human_delta(left)} qoldi)\n\n"
                    f"«📝 Topshiriqlar» bo'limidan topshiring.")
            await send_many(bot, ids, text)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    sch = AsyncIOScheduler(timezone=TZ)
    sch.add_job(lesson_reminders, "interval", minutes=1, args=[bot], max_instances=1, coalesce=True, id="lessons")
    sch.add_job(assignment_reminders, "interval", minutes=1, args=[bot], max_instances=1, coalesce=True, id="assign")
    return sch
