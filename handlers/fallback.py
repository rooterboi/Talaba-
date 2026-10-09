from aiogram import Router
from aiogram.types import CallbackQuery, Message

router = Router()


@router.message()
async def unknown(msg: Message, user):
    if user is None:
        return await msg.answer("👋 Avval ro'yxatdan o'ting: /start")
    await msg.answer("🤔 Tushunmadim. Menyudan foydalaning yoki /start ni bosing.")


@router.callback_query()
async def stale(cb: CallbackQuery):
    await cb.answer("Bu tugma eskirgan. /start ni bosing.", show_alert=True)
