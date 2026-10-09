from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from config import ANON_DAILY_LIMIT
from database.models import AnonMessage, Role, TeacherGroup, User
from handlers.filters import Registered
from keyboards.inline import ikb
from services.access import get_managed_group
from services.notify import send_many
from states.states import Anon, AnonReply
from utils.helpers import esc
from utils.timeutil import fmt_dt, now

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())


async def open_menu(msg: Message, user):
    if user.role == Role.TEACHER:
        return await msg.answer("Anonim xabarlarni 🛠 Boshqaruv → «Anonim xabarlar» orqali ko'rasiz.")
    await msg.answer("🕵️ <b>Anonim murojaat</b>\nShaxsingiz hech kimga ko'rsatilmaydi. Kimga yuboramiz?",
                     reply_markup=ikb([[("⭐ Guruh sardoriga", "an:t:leader")], [("👨‍🏫 O'qituvchilarga", "an:t:teacher")]]))


async def recipients(session, group_id: int, target: str) -> list[User]:
    if target == "leader":
        q = select(User).where(User.group_id == group_id, User.role.in_([Role.LEADER, Role.DEPUTY]))
    else:
        q = select(User).join(TeacherGroup, TeacherGroup.teacher_id == User.id).where(TeacherGroup.group_id == group_id)
    return list((await session.scalars(q)).all())


@router.callback_query(F.data.startswith("an:t:"))
async def pick_target(cb: CallbackQuery, state: FSMContext, session, user):
    target = cb.data.split(":")[2]
    if not user.group_id:
        return await cb.answer("Avval guruhga biriktiring", show_alert=True)
    if not await recipients(session, user.group_id, target):
        return await cb.answer("Guruhingizda hozircha bunday qabul qiluvchi yo'q.", show_alert=True)
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    cnt = await session.scalar(select(func.count(AnonMessage.id)).where(
        AnonMessage.sender_id == user.id, AnonMessage.created_at >= start))
    if cnt >= ANON_DAILY_LIMIT:
        return await cb.answer(f"Kunlik limit: {ANON_DAILY_LIMIT} ta", show_alert=True)
    await state.set_state(Anon.text)
    await state.update_data(target=target)
    await cb.message.answer("✍️ Xabaringizni yozing (/cancel — bekor qilish):")
    await cb.answer()


@router.message(Anon.text, F.text)
async def send_anon(msg: Message, bot: Bot, state: FSMContext, session, user):
    if len(msg.text) < 5:
        return await msg.answer("❌ Xabar juda qisqa.")
    target = (await state.get_data())["target"]
    m = AnonMessage(group_id=user.group_id, sender_id=user.id, target=target, text=msg.text[:3000], created_at=now())
    session.add(m)
    await session.flush()
    await state.clear()
    rec = await recipients(session, user.group_id, target)
    await send_many(bot, [r.tg_id for r in rec], f"🕵️ <b>Anonim murojaat</b> ({esc(user.group.name)})\n\n{esc(m.text)}",
                    reply_markup=ikb([[("↩️ Javob berish", f"anr:{m.id}")]]))
    await msg.answer("✅ Murojaatingiz anonim yuborildi.")


@router.callback_query(F.data.startswith("anr:"))
async def reply_start(cb: CallbackQuery, state: FSMContext, session, user, is_super):
    m = await session.get(AnonMessage, int(cb.data.split(":")[1]))
    if not m or not await get_managed_group(session, user, is_super, m.group_id):
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await state.set_state(AnonReply.text)
    await state.update_data(mid=m.id)
    await cb.message.answer("↩️ Javobingizni yozing (yuboruvchiga anonim yetkaziladi):")
    await cb.answer()


@router.message(AnonReply.text, F.text)
async def reply_send(msg: Message, bot: Bot, state: FSMContext, session):
    m = await session.get(AnonMessage, (await state.get_data())["mid"])
    sender = await session.get(User, m.sender_id)
    m.reply = msg.text[:3000]
    await state.clear()
    await send_many(bot, [sender.tg_id], f"📨 <b>Anonim murojaatingizga javob:</b>\n\n«{esc(m.text[:200])}»\n\n💬 {esc(m.reply)}")
    await msg.answer("✅ Javob yuborildi.")


@router.callback_query(F.data.startswith("mg:anon:"))
async def inbox(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    target = "teacher" if user.role == Role.TEACHER else "leader"
    q = select(AnonMessage).where(AnonMessage.group_id == g.id)
    if not is_super:
        q = q.where(AnonMessage.target == target)
    rows = (await session.scalars(q.order_by(AnonMessage.id.desc()).limit(10))).all()
    await cb.answer()
    if not rows:
        return await cb.message.answer("📥 Anonim xabarlar yo'q.")
    for m in rows:
        await cb.message.answer(f"🕵️ {fmt_dt(m.created_at)}\n\n{esc(m.text)}" + (f"\n\n↩️ Javob: {esc(m.reply)}" if m.reply else ""),
                                reply_markup=None if m.reply else ikb([[("↩️ Javob berish", f"anr:{m.id}")]]))
