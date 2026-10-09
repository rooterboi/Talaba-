from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from database.models import Role

BTN_SCHEDULE = "📅 Dars jadvali"
BTN_ASSIGN = "📝 Topshiriqlar"
BTN_LIB = "📚 Kutubxona"
BTN_AI = "🤖 AI yordamchi"
BTN_RATING = "🏆 Reyting"
BTN_ANN = "📢 E'lonlar"
BTN_ANON = "🕵️ Anonim murojaat"
BTN_PROFILE = "👤 Profil"
BTN_MANAGE = "🛠 Boshqaruv"
BTN_ADMIN = "🛡 Admin panel"

ALL_BUTTONS = {BTN_SCHEDULE, BTN_ASSIGN, BTN_LIB, BTN_AI, BTN_RATING, BTN_ANN,
               BTN_ANON, BTN_PROFILE, BTN_MANAGE, BTN_ADMIN}


def _rows(*rows):
    return [[KeyboardButton(text=t) for t in r] for r in rows]


def main_menu(user, is_super: bool = False) -> ReplyKeyboardMarkup:
    if user.role == Role.TEACHER:
        rows = [[BTN_SCHEDULE, BTN_MANAGE], [BTN_LIB, BTN_AI], [BTN_PROFILE]]
    else:
        rows = [[BTN_SCHEDULE, BTN_ASSIGN], [BTN_LIB, BTN_AI], [BTN_RATING, BTN_ANN], [BTN_ANON, BTN_PROFILE]]
        if user.role in (Role.LEADER, Role.DEPUTY) or is_super:
            rows.append([BTN_MANAGE])
    if is_super:
        rows.append([BTN_ADMIN])
    return ReplyKeyboardMarkup(keyboard=_rows(*rows), resize_keyboard=True)
