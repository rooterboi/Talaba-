"""Boshqaruv paneli: sardor / o'rinbosar / o'qituvchi / super admin uchun."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from database.models import Role, User
from handlers.filters import IsManager, Registered
from keyboards.inline import ikb, manager_panel_kb
from services.access import get_managed_group, managed_groups
from utils.helpers import esc, group_title, new_code

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())


async def open_panel(msg: Message, session, user, is_super):
    if not (is_super or user.role in Role.MANAGERS):
        return await msg.answer("⛔ Bu bo'lim faqat sardor, o'rinbosar va o'qituvchilar uchun.")
    groups = await managed_groups(session, user, is_super)
    if not groups:
        return await msg.answer("Sizga biriktirilgan guruh yo'q. Profil → «Guruh qo'shish».")
    if len(groups) == 1:
        return await msg.answer(f"🛠 <b>{esc(group_title(groups[0]))}</b>", reply_markup=manager_panel_kb(groups[0].id))
    await msg.answer("🛠 Guruhni tanlang:", reply_markup=ikb([[(group_title(g)[:60], f"mgsel:{g.id}")] for g in groups]))


@router.callback_query(F.data.startswith("mgsel:"))
async def select_group(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[1]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await cb.message.edit_text(f"🛠 <b>{esc(group_title(g))}</b>", reply_markup=manager_panel_kb(g.id))
    await cb.answer()


@router.callback_query(F.data.startswith("mg:mem:"))
async def members(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    users = (await session.scalars(select(User).where(User.group_id == g.id).order_by(User.xp.desc()).limit(60))).all()
    lines = [f"{'⭐' if u.role == Role.LEADER else '🔰' if u.role == Role.DEPUTY else '•'} {esc(u.full_name)} — {u.xp} XP"
             for u in users]
    rows = [[(f"{'⬇️ Oddiy qilish' if u.role == Role.DEPUTY else '🔰 O‘rinbosar qilish'}: {u.full_name[:20]}", f"dep:{g.id}:{u.id}")]
            for u in users if u.role in (Role.STUDENT, Role.DEPUTY)][:25]
    rows.append([("♻️ Sardor kodini yangilash", f"rot:{g.id}")])
    text = (f"👥 <b>{esc(group_title(g))}</b> — {len(users)} a'zo\n🔑 Sardor kodi: <code>{g.leader_code}</code>\n\n" + "\n".join(lines))
    await cb.message.answer(text[:4000], reply_markup=ikb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("dep:"))
async def toggle_deputy(cb: CallbackQuery, session, user, is_super):
    _, gid, uid = cb.data.split(":")
    g = await get_managed_group(session, user, is_super, int(gid))
    u = await session.get(User, int(uid))
    if not g or not u or u.group_id != g.id or u.role not in (Role.STUDENT, Role.DEPUTY):
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    u.role = Role.STUDENT if u.role == Role.DEPUTY else Role.DEPUTY
    await cb.answer(f"{u.full_name}: {Role.LABELS[u.role]}", show_alert=True)


@router.callback_query(F.data.startswith("rot:"))
async def rotate_code(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[1]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    from database.models import Group
    code = new_code()
    while await session.scalar(select(Group.id).where(Group.leader_code == code)):
        code = new_code()
    g.leader_code = code
    await cb.message.answer(f"♻️ Yangi sardor kodi: <code>{code}</code>")
    await cb.answer()
