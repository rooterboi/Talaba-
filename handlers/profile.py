from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select

from database.models import Group, Role, TeacherGroup
from handlers.filters import Registered
from handlers.registration import start_picker
from keyboards.inline import ikb
from keyboards.reply import main_menu
from services.xp import level, level_title, rank_of
from states.states import LeaderCode
from utils.helpers import esc, group_title, safe_edit

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())


def profile_kb(user):
    rows = [[(f"🔔 Eslatmalar: {'✅' if user.notify else '⛔'}", "pf:notify")]]
    if user.role == Role.TEACHER:
        rows.append([("👥 Guruhlarim", "pf:groups"), ("➕ Guruh qo'shish", "tg:add")])
    else:
        rows.append([("🔑 Sardor kodini kiritish", "pf:code"), ("🔁 Guruhni o'zgartirish", "pf:change")])
    return ikb(rows)


async def profile_text(session, user, is_super):
    role = Role.LABELS.get(user.role, user.role) + (" • 🛡 Super admin" if is_super else "")
    text = (f"👤 <b>{esc(user.full_name)}</b>\n🎭 {role}\n🏛 {esc(user.institution.name if user.institution else None)}\n")
    if user.group:
        text += f"👥 {esc(group_title(user.group))}\n"
    if user.role != Role.TEACHER:
        place = await rank_of(session, user, group_id=user.group_id) if user.group_id else "—"
        text += (f"\n⭐ XP: <b>{user.xp}</b>\n🏅 Daraja: <b>{level(user.xp)}</b> — {level_title(user.xp)}\n"
                 f"🏆 Guruhdagi o'rin: <b>{place}</b>")
    return text


async def open_profile(msg: Message, session, user, is_super):
    await msg.answer(await profile_text(session, user, is_super), reply_markup=profile_kb(user))


@router.callback_query(F.data == "pf:notify")
async def toggle_notify(cb: CallbackQuery, session, user, is_super):
    user.notify = not user.notify
    await safe_edit(cb.message, await profile_text(session, user, is_super), profile_kb(user))
    await cb.answer("Saqlandi")


@router.callback_query(F.data == "pf:code")
async def ask_code(cb: CallbackQuery, state: FSMContext):
    await state.set_state(LeaderCode.code)
    await cb.message.answer("🔑 Guruh sardori kodini yuboring:\n(/cancel — bekor qilish)")
    await cb.answer()


@router.message(LeaderCode.code, F.text)
async def check_code(msg: Message, state: FSMContext, session, user, is_super):
    g = await session.scalar(select(Group).where(Group.leader_code == msg.text.strip().upper()))
    if not g:
        return await msg.answer("❌ Kod noto'g'ri. Qayta yuboring yoki /cancel.")
    user.group_id, user.institution_id, user.role = g.id, g.institution_id, Role.LEADER
    await state.clear()
    await msg.answer(f"🎉 Siz <b>{esc(group_title(g))}</b> guruhi sardori bo'ldingiz!\n"
                     f"Endi «🛠 Boshqaruv» bo'limi ochildi.", reply_markup=main_menu(user, is_super))


@router.callback_query(F.data == "pf:change")
async def change_group(cb: CallbackQuery, state: FSMContext, session, user):
    await state.clear()
    await cb.answer()
    await start_picker(cb.message, state, session, user.institution_id, "change")


@router.callback_query(F.data == "tg:add")
async def teacher_add(cb: CallbackQuery, state: FSMContext, session, user):
    if user is None or user.role != Role.TEACHER:
        return await cb.answer("Faqat o'qituvchilar uchun", show_alert=True)
    await state.clear()
    await cb.answer()
    await start_picker(cb.message, state, session, user.institution_id, "teacher_add")


@router.callback_query(F.data == "pf:groups")
async def teacher_groups(cb: CallbackQuery, session, user):
    groups = (await session.scalars(select(Group).join(TeacherGroup, TeacherGroup.group_id == Group.id)
                                    .where(TeacherGroup.teacher_id == user.id))).all()
    await cb.answer()
    if not groups:
        return await cb.message.answer("Hozircha guruh yo'q. «➕ Guruh qo'shish» ni bosing.")
    rows = [[(f"🗑 {g.name} ({g.course}-kurs)", f"tg:del:{g.id}")] for g in groups]
    await cb.message.answer("👥 <b>Guruhlaringiz</b> (o'chirish uchun bosing):", reply_markup=ikb(rows))


@router.callback_query(F.data.startswith("tg:del:"))
async def teacher_del(cb: CallbackQuery, session, user):
    await session.execute(delete(TeacherGroup).where(
        TeacherGroup.teacher_id == user.id, TeacherGroup.group_id == int(cb.data.split(":")[2])))
    await cb.answer("O'chirildi")
    await cb.message.delete()
