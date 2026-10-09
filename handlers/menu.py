"""Asosiy menyu tugmalari. Har bosilganda joriy FSM bekor qilinadi, so'ng bo'lim ochiladi."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers import (admin, ai, announce, anon, assignments, library, manager, profile, rating, schedule)
from handlers.filters import Registered
from keyboards.reply import (BTN_ADMIN, BTN_AI, BTN_ANN, BTN_ANON, BTN_ASSIGN, BTN_LIB, BTN_MANAGE,
                             BTN_PROFILE, BTN_RATING, BTN_SCHEDULE, main_menu)

router = Router()
router.message.filter(Registered())


@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext, user, is_super):
    await state.clear()
    await msg.answer("❌ Bekor qilindi.", reply_markup=main_menu(user, is_super))


@router.message(Command("help"))
async def help_(msg: Message):
    await msg.answer("ℹ️ Menyudan kerakli bo'limni tanlang.\n/cancel — joriy amalni bekor qilish\n"
                     "/start — bosh menyu\n/admin — admin panel (adminlar uchun)")


@router.message(F.text == BTN_SCHEDULE)
async def m_schedule(msg: Message, state: FSMContext):
    await state.clear(); await schedule.open_menu(msg)


@router.message(F.text == BTN_ASSIGN)
async def m_assign(msg: Message, state: FSMContext, session, user):
    await state.clear(); await assignments.open_list(msg, session, user)


@router.message(F.text == BTN_LIB)
async def m_lib(msg: Message, state: FSMContext, session, user):
    await state.clear(); await library.open_menu(msg, state, session, user)


@router.message(F.text == BTN_AI)
async def m_ai(msg: Message, state: FSMContext):
    await state.clear(); await ai.open_menu(msg)


@router.message(F.text == BTN_RATING)
async def m_rating(msg: Message, state: FSMContext):
    await state.clear(); await rating.open_menu(msg)


@router.message(F.text == BTN_ANN)
async def m_ann(msg: Message, state: FSMContext, session, user):
    await state.clear(); await announce.open_list(msg, session, user)


@router.message(F.text == BTN_ANON)
async def m_anon(msg: Message, state: FSMContext, user):
    await state.clear(); await anon.open_menu(msg, user)


@router.message(F.text == BTN_PROFILE)
async def m_profile(msg: Message, state: FSMContext, session, user, is_super):
    await state.clear(); await profile.open_profile(msg, session, user, is_super)


@router.message(F.text == BTN_MANAGE)
async def m_manage(msg: Message, state: FSMContext, session, user, is_super):
    await state.clear(); await manager.open_panel(msg, session, user, is_super)


@router.message(F.text == BTN_ADMIN)
@router.message(Command("admin"))
async def m_admin(msg: Message, state: FSMContext, is_super):
    await state.clear()
    if is_super:
        await admin.open_panel(msg)
