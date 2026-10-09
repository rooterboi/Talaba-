from datetime import timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select

from config import PAIR_TIMES
from database.models import Group, Role, Schedule
from handlers.filters import Registered
from keyboards.inline import (ikb, ltype_kb, pair_kb, schedule_menu_kb, week_kb, weekday_kb)
from services.access import get_managed_group, teacher_group_ids
from states.states import SchAdd
from utils.helpers import esc, group_title, safe_edit
from utils.timeutil import SHORT, WEEKDAYS, today, week_parity

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())

NUM = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}


async def open_menu(msg: Message):
    await msg.answer("📅 <b>Dars jadvali</b>\nQaysi kun uchun ko'rsatay?", reply_markup=schedule_menu_kb())


async def entries_for(session, user, d):
    q = (select(Schedule, Group.name).join(Group, Group.id == Schedule.group_id)
         .where(Schedule.weekday == d.weekday(), Schedule.week_type.in_([0, week_parity(d)]))
         .order_by(Schedule.pair_no))
    if user.role == Role.TEACHER:
        gids = await teacher_group_ids(session, user)
        if not gids:
            return [], True
        q = q.where(Schedule.group_id.in_(gids), Schedule.teacher_name.ilike(f"%{user.full_name.split()[0]}%"))
    else:
        if not user.group_id:
            return [], False
        q = q.where(Schedule.group_id == user.group_id)
    return (await session.execute(q)).all(), user.role == Role.TEACHER


def fmt_day(d, rows, show_group) -> str:
    p = "toq" if week_parity(d) == 1 else "juft"
    out = f"📅 <b>{WEEKDAYS[d.weekday()]}</b>, {d:%d.%m.%Y} <i>({p} hafta)</i>\n\n"
    if not rows:
        return out + "🎉 Dars yo'q!"
    for e, gname in rows:
        out += (f"{NUM.get(e.pair_no, e.pair_no)} <b>{e.start_time:%H:%M}–{e.end_time:%H:%M}</b>\n"
                f"   📖 {esc(e.subject)} <i>({esc(e.lesson_type)})</i>\n")
        if e.teacher_name:
            out += f"   👨‍🏫 {esc(e.teacher_name)}\n"
        if e.room:
            out += f"   🚪 {esc(e.room)}\n"
        if show_group:
            out += f"   👥 {esc(gname)}\n"
        out += "\n"
    return out


@router.callback_query(F.data.in_({"sch:today", "sch:tomorrow", "sch:week"}))
async def show(cb: CallbackQuery, session, user):
    t = today()
    if cb.data == "sch:week":
        monday = t - timedelta(days=t.weekday())
        text = ""
        for i in range(6):
            d = monday + timedelta(days=i)
            rows, sg = await entries_for(session, user, d)
            text += fmt_day(d, rows, sg) + "\n──────────\n"
    else:
        d = t if cb.data == "sch:today" else t + timedelta(days=1)
        rows, sg = await entries_for(session, user, d)
        text = fmt_day(d, rows, sg)
    await safe_edit(cb.message, text[:4000], schedule_menu_kb())
    await cb.answer()


# ======================= JADVAL TAHRIRLASH (sardor/o'qituvchi) =======================
@router.callback_query(F.data.startswith("mg:sch:"))
async def sch_menu(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await cb.message.answer(f"📅 <b>{esc(group_title(g))}</b> jadvali", reply_markup=ikb([
        [("➕ Dars qo'shish", f"sa:{g.id}")], [("🗑 Dars o'chirish", f"sl:{g.id}")]]))
    await cb.answer()


@router.callback_query(F.data.startswith("sa:"))
async def add_start(cb: CallbackQuery, state: FSMContext, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[1]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await state.clear()
    await state.update_data(gid=g.id)
    await state.set_state(SchAdd.weekday)
    await cb.message.answer("Hafta kunini tanlang:", reply_markup=weekday_kb())
    await cb.answer()


@router.callback_query(SchAdd.weekday, F.data.startswith("sw:"))
async def a_weekday(cb: CallbackQuery, state: FSMContext):
    await state.update_data(weekday=int(cb.data.split(":")[1]))
    await state.set_state(SchAdd.pair)
    await cb.message.edit_text("Nechanchi juftlik?", reply_markup=pair_kb())
    await cb.answer()


@router.callback_query(SchAdd.pair, F.data.startswith("sp:"))
async def a_pair(cb: CallbackQuery, state: FSMContext):
    await state.update_data(pair=int(cb.data.split(":")[1]))
    await state.set_state(SchAdd.subject)
    await cb.message.edit_text("📖 Fan nomini yozing:")
    await cb.answer()


@router.message(SchAdd.subject, F.text)
async def a_subject(msg: Message, state: FSMContext):
    await state.update_data(subject=msg.text.strip()[:150])
    await state.set_state(SchAdd.teacher)
    await msg.answer("👨‍🏫 O'qituvchi F.I.Sh. (yoki «-»):")


@router.message(SchAdd.teacher, F.text)
async def a_teacher(msg: Message, state: FSMContext):
    await state.update_data(teacher="" if msg.text.strip() == "-" else msg.text.strip()[:100])
    await state.set_state(SchAdd.room)
    await msg.answer("🚪 Xona (masalan: 305) yoki «-»:")


@router.message(SchAdd.room, F.text)
async def a_room(msg: Message, state: FSMContext):
    await state.update_data(room="" if msg.text.strip() == "-" else msg.text.strip()[:50])
    await state.set_state(SchAdd.ltype)
    await msg.answer("Dars turi:", reply_markup=ltype_kb())


@router.callback_query(SchAdd.ltype, F.data.startswith("st:"))
async def a_ltype(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ltype=cb.data.split(":", 1)[1])
    await state.set_state(SchAdd.week)
    await cb.message.edit_text("Qaysi haftalarda o'tiladi?", reply_markup=week_kb())
    await cb.answer()


@router.callback_query(SchAdd.week, F.data.startswith("sk:"))
async def a_week(cb: CallbackQuery, state: FSMContext, session):
    d = await state.get_data()
    st, en = PAIR_TIMES[d["pair"]]
    session.add(Schedule(group_id=d["gid"], weekday=d["weekday"], pair_no=d["pair"], start_time=st, end_time=en,
                         subject=d["subject"], teacher_name=d["teacher"], room=d["room"],
                         lesson_type=d["ltype"], week_type=int(cb.data.split(":")[1])))
    await state.clear()
    await cb.message.edit_text(
        f"✅ Saqlandi: {WEEKDAYS[d['weekday']]}, {d['pair']}-juftlik ({st:%H:%M}–{en:%H:%M}) — {esc(d['subject'])}",
        reply_markup=ikb([[("➕ Yana qo'shish", f"sa:{d['gid']}")]]))
    await cb.answer()


@router.callback_query(F.data.startswith("sl:"))
async def del_list(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[1]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    rows = (await session.scalars(select(Schedule).where(Schedule.group_id == g.id)
                                  .order_by(Schedule.weekday, Schedule.pair_no).limit(60))).all()
    await cb.answer()
    if not rows:
        return await cb.message.answer("Jadval bo'sh.")
    await cb.message.answer("🗑 O'chirish uchun darsni tanlang:", reply_markup=ikb(
        [[(f"{SHORT[e.weekday]} {e.pair_no}-juft • {e.subject[:30]}", f"sx:{e.id}")] for e in rows]))


@router.callback_query(F.data.startswith("sx:"))
async def del_do(cb: CallbackQuery, session, user, is_super):
    e = await session.get(Schedule, int(cb.data.split(":")[1]))
    if not e or not await get_managed_group(session, user, is_super, e.group_id):
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await session.delete(e)
    await cb.answer("🗑 O'chirildi")
    await cb.message.edit_text("🗑 Dars o'chirildi.")
