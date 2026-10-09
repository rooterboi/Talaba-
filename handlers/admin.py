"""Tizim admini (Super Admin) paneli."""
import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from database.models import (Assignment, Group, Institution, LibFile, Role, Submission, User)
from handlers.filters import IsSuper
from keyboards.inline import ikb
from states.states import AdminSt
from utils.helpers import chunks, esc, group_title

router = Router()
router.message.filter(IsSuper())
router.callback_query.filter(IsSuper())

PANEL = ikb([[("📊 Statistika", "ad:stats"), ("🏛 OTM qo'shish", "ad:inst")],
             [("📋 Guruhlar va kodlar", "ad:groups"), ("🎭 Rol berish", "ad:role")],
             [("🚫 Ban / Unban", "ad:ban"), ("📣 Umumiy xabar", "ad:bc")]])


async def open_panel(msg: Message):
    await msg.answer("🛡 <b>Super Admin paneli</b>", reply_markup=PANEL)


@router.callback_query(F.data == "ad:stats")
async def stats(cb: CallbackQuery, session):
    c = lambda m: session.scalar(select(func.count(m.id)))
    text = (f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: {await c(User)}\n"
            f"🏛 OTMlar: {await c(Institution)}\n👨‍👩‍👧 Guruhlar: {await c(Group)}\n"
            f"📝 Topshiriqlar: {await c(Assignment)}\n📤 Topshirilganlar: {await c(Submission)}\n"
            f"📚 Materiallar: {await c(LibFile)}")
    await cb.message.answer(text)
    await cb.answer()


@router.callback_query(F.data == "ad:inst")
async def inst_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSt.inst)
    await cb.message.answer("🏛 Yangi OTM / kollej / litsey nomini yozing:")
    await cb.answer()


@router.message(AdminSt.inst, F.text)
async def inst_save(msg: Message, state: FSMContext, session):
    name = msg.text.strip()[:200]
    if await session.scalar(select(Institution.id).where(Institution.name == name)):
        return await msg.answer("Bu nom allaqachon mavjud.")
    session.add(Institution(name=name))
    await state.clear()
    await msg.answer(f"✅ Qo'shildi: {esc(name)}")


@router.callback_query(F.data == "ad:groups")
async def groups(cb: CallbackQuery, session):
    rows = (await session.scalars(select(Group).order_by(Group.id.desc()).limit(80))).all()
    text = "\n".join(f"#{g.id} {esc(g.institution.name[:25])} | {esc(group_title(g))} | <code>{g.leader_code}</code>" for g in rows)
    for part in chunks(text or "Guruhlar yo'q.", 3800):
        await cb.message.answer(part)
    await cb.answer()


@router.callback_query(F.data == "ad:role")
async def role_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSt.role_id)
    await cb.message.answer("🎭 Foydalanuvchi Telegram ID sini yuboring:")
    await cb.answer()


@router.message(AdminSt.role_id, F.text)
async def role_id(msg: Message, state: FSMContext, session):
    if not msg.text.strip().isdigit():
        return await msg.answer("❌ Faqat raqam.")
    u = await session.scalar(select(User).where(User.tg_id == int(msg.text)))
    if not u:
        return await msg.answer("❌ Foydalanuvchi topilmadi (u avval /start qilgan bo'lishi kerak).")
    await state.update_data(uid=u.id)
    await state.set_state(AdminSt.role_val)
    await msg.answer(f"{esc(u.full_name)} uchun rol:", reply_markup=ikb(
        [[(l, f"ar:{k}")] for k, l in Role.LABELS.items()]))


@router.callback_query(AdminSt.role_val, F.data.startswith("ar:"))
async def role_set(cb: CallbackQuery, state: FSMContext, session):
    u = await session.get(User, (await state.get_data())["uid"])
    u.role = cb.data.split(":")[1]
    await state.clear()
    await cb.message.edit_text(f"✅ {esc(u.full_name)} → {Role.LABELS[u.role]}")
    await cb.answer()


@router.callback_query(F.data == "ad:ban")
async def ban_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSt.ban_id)
    await cb.message.answer("🚫 Ban/Unban qilinadigan foydalanuvchi Telegram ID si:")
    await cb.answer()


@router.message(AdminSt.ban_id, F.text)
async def ban_do(msg: Message, state: FSMContext, session):
    u = await session.scalar(select(User).where(User.tg_id == int(msg.text))) if msg.text.strip().isdigit() else None
    if not u:
        return await msg.answer("❌ Topilmadi.")
    u.banned = not u.banned
    await state.clear()
    await msg.answer(f"{'🚫 Bloklandi' if u.banned else '✅ Blokdan chiqarildi'}: {esc(u.full_name)}")


@router.callback_query(F.data == "ad:bc")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSt.broadcast)
    await cb.message.answer("📣 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring:")
    await cb.answer()


@router.message(AdminSt.broadcast)
async def bc_go(msg: Message, bot: Bot, state: FSMContext, session):
    await state.clear()
    ids = list((await session.scalars(select(User.tg_id).where(User.banned.is_(False)))).all())
    await msg.answer(f"📣 {len(ids)} ta foydalanuvchiga yuborilmoqda...")
    ok = 0
    for uid in ids:
        try:
            await bot.copy_message(uid, msg.chat.id, msg.message_id)
            ok += 1
        except Exception:
            pass
        await asyncio.sleep(0.04)
    await msg.answer(f"✅ Yetkazildi: {ok}/{len(ids)}")
