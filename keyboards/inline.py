from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ikb(rows) -> InlineKeyboardMarkup:
    """rows: [[(text, callback_data | https-url), ...], ...]"""
    out = []
    for r in rows:
        line = []
        for t, d in r:
            if d.startswith("http"):
                line.append(InlineKeyboardButton(text=t, url=d))
            else:
                line.append(InlineKeyboardButton(text=t, callback_data=d))
        out.append(line)
    return InlineKeyboardMarkup(inline_keyboard=out)


def role_kb():
    return ikb([[("🎓 Talaba", "reg:role:student")], [("👨‍🏫 O'qituvchi", "reg:role:teacher")]])


def opts_kb(prefix: str, options: list[str], new_label: str | None = None):
    rows = [[(o[:55], f"{prefix}:{i}")] for i, o in enumerate(options)]
    if new_label:
        rows.append([(new_label, f"{prefix}:new")])
    return ikb(rows)


def course_kb():
    return ikb([[(f"{i}-kurs", f"pk:course:{i}") for i in (1, 2, 3)],
                [(f"{i}-kurs", f"pk:course:{i}") for i in (4, 5, 6)]])


def schedule_menu_kb():
    return ikb([[("📍 Bugun", "sch:today"), ("➡️ Ertaga", "sch:tomorrow")],
                [("🗓 Haftalik", "sch:week")]])


def weekday_kb():
    names = ["Du", "Se", "Ch", "Pa", "Ju", "Sh"]
    return ikb([[(n, f"sw:{i}") for i, n in enumerate(names[:3])],
                [(n, f"sw:{i + 3}") for i, n in enumerate(names[3:])]])


def pair_kb():
    return ikb([[(f"{i}-juftlik", f"sp:{i}") for i in (1, 2, 3)],
                [(f"{i}-juftlik", f"sp:{i}") for i in (4, 5, 6)]])


def ltype_kb():
    return ikb([[("Ma'ruza", "st:Ma'ruza"), ("Amaliy", "st:Amaliy")],
                [("Laboratoriya", "st:Laboratoriya"), ("Seminar", "st:Seminar")]])


def week_kb():
    return ikb([[("Har hafta", "sk:0")], [("Faqat toq hafta", "sk:1"), ("Faqat juft hafta", "sk:2")]])


def ai_menu_kb():
    return ikb([[("📝 Konspekt qilish", "ai:summary")], [("❓ Savol-javob", "ai:chat")],
                [("🧪 Test yechish (+XP)", "ai:quiz")]])


def rating_kb():
    return ikb([[("👥 Guruhim", "rt:group"), ("🏛 OTMim", "rt:inst")], [("🌍 OTMlar reytingi", "rt:insts")]])


def manager_panel_kb(gid: int):
    return ikb([
        [("➕ Topshiriq", f"mg:asg:{gid}"), ("📊 Natijalar", f"mg:res:{gid}")],
        [("📢 E'lon", f"mg:ann:{gid}"), ("📅 Jadval", f"mg:sch:{gid}")],
        [("📚 Material yuklash", f"mg:lib:{gid}"), ("👥 A'zolar", f"mg:mem:{gid}")],
        [("📥 Anonim xabarlar", f"mg:anon:{gid}")]])


CATS = {"lecture": "📖 Ma'ruza", "slide": "🖥 Slayd", "test": "🧪 Test", "book": "📕 Kitob"}
