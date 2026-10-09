from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.models import Role
from handlers.filters import Registered
from keyboards.inline import rating_kb
from services.xp import institutions_ranking, level, rank_of, top_users
from utils.helpers import esc, safe_edit

router = Router()
router.callback_query.filter(Registered())

MEDALS = ["🥇", "🥈", "🥉"]


async def open_menu(msg: Message):
    await msg.answer("🏆 <b>Reyting</b>\nQaysi reytingni ko'rasiz?", reply_markup=rating_kb())


def fmt(users) -> str:
    return "\n".join(f"{MEDALS[i] if i < 3 else f'{i + 1}.'} {esc(u.full_name)} — <b>{u.xp}</b> XP • {level(u.xp)}-daraja"
                     for i, u in enumerate(users)) or "Hozircha ma'lumot yo'q."


@router.callback_query(F.data.startswith("rt:"))
async def show(cb: CallbackQuery, session, user):
    kind = cb.data.split(":")[1]
    if user.role == Role.TEACHER:
        return await cb.answer("Reyting talabalar uchun", show_alert=True)
    if kind == "group":
        top = await top_users(session, group_id=user.group_id)
        place = await rank_of(session, user, group_id=user.group_id)
        text = f"👥 <b>Guruh reytingi</b>\n\n{fmt(top)}\n\n📍 Sizning o'rningiz: <b>{place}</b> ({user.xp} XP)"
    elif kind == "inst":
        top = await top_users(session, institution_id=user.institution_id)
        place = await rank_of(session, user, institution_id=user.institution_id)
        text = f"🏛 <b>OTM reytingi</b>\n\n{fmt(top)}\n\n📍 Sizning o'rningiz: <b>{place}</b>"
    else:
        rows = await institutions_ranking(session)
        body = "\n".join(f"{MEDALS[i] if i < 3 else f'{i + 1}.'} {esc(n)} — <b>{xp}</b> XP ({c} talaba)"
                         for i, (n, xp, c) in enumerate(rows)) or "Hozircha ma'lumot yo'q."
        text = f"🌍 <b>OTMlar o'rtasidagi reyting</b>\n\n{body}"
    await safe_edit(cb.message, text, rating_kb())
    await cb.answer()
