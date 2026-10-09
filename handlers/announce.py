import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database.models import Announcement, User
from handlers.filters import Registered
from keyboards.inline import ikb
from services.access import get_managed_group, group_member_tg_ids
from states.states import Ann
from utils.helpers import esc, group_title
from utils.timeutil import fmt_dt

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())


async def open_list(msg: Message, session, user):
    if not user.group_id:
        return await msg.answer("Avval guruhga biriktiring.")
    rows = (await session.execute(select(Announcement, User.full_name).join(User, User.id == Announcement.author_id)
                                  .where(Announcement.group_id == user.group_id)
                                  .order_by(Announcement.id.desc()).limit(8))).all()
    if not rows:
        return await msg.answer("📢 E'lonlar hozircha yo'q.")
    text = "📢 <b>So'nggi e'lonlar</b>\n\n" + "\n\n".join(
        f"{'🚨 ' if a.important else '• '}<i>{fmt_dt(a.created_at)} — {esc(n)}</i>\n{esc(a.text[:400])}" for a, n in rows)
    await msg.answer(text[:4000])


@router.callback_query(F.data.startswith("mg:ann:"))
async def start(cb: CallbackQuery, state: FSMContext, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await state.clear()
    await state.update_data(gid=g.id)
    await state.set_state(Ann.content)
    await cb.message.answer(f"📢 <b>{esc(group_title(g))}</b> uchun e'lon matnini yuboring (matn yoki rasm/fayl izoh bilan):\n/cancel")
    await cb.answer()


@router.message(Ann.content, F.text | F.photo | F.document | F.video)
async def content(msg: Message, state: FSMContext):
    await state.update_data(mid=msg.message_id, text=msg.text or msg.caption or "", media=not msg.text)
    await state.set_state(Ann.important)
    await msg.answer("Bu e'lon MUHIMmi? (Muhim e'lon 🚨 belgisi bilan yuboriladi va chatga qadaladi)",
                     reply_markup=ikb([[("🚨 Ha, muhim", "ann:1"), ("📢 Oddiy", "ann:0")]]))


@router.callback_query(Ann.important, F.data.startswith("ann:"))
async def send(cb: CallbackQuery, bot: Bot, state: FSMContext, session, user, is_super):
    d = await state.get_data()
    g = await get_managed_group(session, user, is_super, d["gid"])
    await state.clear()
    await cb.answer()
    if not g:
        return await cb.message.edit_text("Ruxsat yo'q.")
    important = cb.data == "ann:1"
    session.add(Announcement(group_id=g.id, author_id=user.id, text=d["text"] or "(media)", important=important))
    ids = await group_member_tg_ids(session, g.id, exclude_tg=cb.from_user.id)
    head = ("🚨 <b>MUHIM E'LON</b>" if important else "📢 <b>E'lon</b>") + f" — {esc(g.name)}\n👤 {esc(user.full_name)}\n\n"
    await cb.message.edit_text("⏳ Yuborilmoqda...")
    sent = 0
    for uid in ids:
        try:
            if d["media"]:
                m = await bot.copy_message(uid, cb.message.chat.id, d["mid"], caption=(head + esc(d["text"]))[:1024])
            else:
                m = await bot.send_message(uid, head + esc(d["text"]))
            if important:
                try:
                    await bot.pin_chat_message(uid, m.message_id)
                except Exception:
                    pass
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.04)
    await cb.message.edit_text(f"✅ E'lon {sent}/{len(ids)} foydalanuvchiga yetkazildi.")
