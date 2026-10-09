from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, func, select

from config import XP_ASSIGNMENT, XP_EARLY_BONUS, XP_LATE
from database.models import Assignment, Group, Role, Submission, User
from handlers.filters import Registered
from keyboards.inline import ikb
from services.access import get_managed_group, group_member_tg_ids
from services.notify import send_many
from services.xp import add_xp
from states.states import AsgCreate, Grade, Submit
from utils.helpers import esc, extract_file, group_title, safe_edit, send_file
from utils.timeutil import fmt_dt, human_delta, now, parse_deadline
from datetime import timedelta

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())


# ======================= TALABA =======================
async def open_list(msg: Message, session, user):
    if user.role == Role.TEACHER:
        return await msg.answer("O'qituvchilar uchun: 🛠 Boshqaruv → Topshiriq.")
    if not user.group_id:
        return await msg.answer("Avval guruhga biriktiring (Profil).")
    n = now()
    rows = (await session.scalars(select(Assignment).where(
        Assignment.group_id == user.group_id, Assignment.deadline > n - timedelta(days=7))
        .order_by(Assignment.deadline).limit(20))).all()
    if not rows:
        return await msg.answer("📝 Hozircha topshiriq yo'q. 🎉")
    done = set((await session.scalars(select(Submission.assignment_id).where(Submission.student_id == user.id))).all())
    buttons = []
    for a in rows:
        mark = "✅" if a.id in done else ("⛔" if a.deadline < n else "⏳")
        buttons.append([(f"{mark} {a.subject[:20]} — {a.title[:25]}", f"as:{a.id}")])
    await msg.answer("📝 <b>Topshiriqlar</b>\n✅ topshirilgan • ⏳ kutilmoqda • ⛔ muddati o'tgan",
                     reply_markup=ikb(buttons))


@router.callback_query(F.data.startswith("as:"))
async def detail(cb: CallbackQuery, bot: Bot, session, user):
    a = await session.get(Assignment, int(cb.data.split(":")[1]))
    if not a or a.group_id != user.group_id:
        return await cb.answer("Topilmadi", show_alert=True)
    sub = await session.scalar(select(Submission).where(Submission.assignment_id == a.id, Submission.student_id == user.id))
    left = a.deadline - now()
    text = (f"📝 <b>{esc(a.title)}</b>\n📖 {esc(a.subject)}\n\n{esc(a.description)}\n\n"
            f"⏳ Muddat: <b>{fmt_dt(a.deadline)}</b> ({human_delta(left)})\n🎁 Mukofot: +{a.xp_reward} XP\n")
    if sub:
        text += f"\n✅ Topshirilgan: {fmt_dt(sub.submitted_at)}" + (" (kechikkan)" if sub.is_late else "")
        if sub.grade is not None:
            text += f"\n🏅 Baho: <b>{sub.grade}</b>/100"
    btn = "🔄 Qayta topshirish" if sub else "📤 Topshirish"
    await cb.message.answer(text, reply_markup=ikb([[(btn, f"sub:{a.id}")]]))
    if a.file_id:
        await send_file(bot, cb.message.chat.id, a.file_id, a.file_type, "📎 Topshiriq fayli")
    await cb.answer()


@router.callback_query(F.data.startswith("sub:"))
async def submit_start(cb: CallbackQuery, state: FSMContext, session, user):
    a = await session.get(Assignment, int(cb.data.split(":")[1]))
    if not a or a.group_id != user.group_id:
        return await cb.answer("Topilmadi", show_alert=True)
    await state.clear()
    await state.update_data(aid=a.id)
    await state.set_state(Submit.waiting)
    await cb.message.answer("📤 Bajargan ishingizni yuboring (PDF, Word, rasm, video yoki matn).\n/cancel — bekor qilish")
    await cb.answer()


@router.message(Submit.waiting, F.text | F.document | F.photo | F.video | F.audio)
async def submit_recv(msg: Message, bot: Bot, state: FSMContext, session, user):
    a = await session.get(Assignment, (await state.get_data())["aid"])
    if not a:
        await state.clear()
        return await msg.answer("Topshiriq topilmadi.")
    fid, ftype = extract_file(msg)
    text = msg.caption or (msg.text if not fid else None)
    if not fid and (not text or len(text) < 10):
        return await msg.answer("❌ Matn juda qisqa. Fayl yoki to'liqroq matn yuboring.")
    n = now()
    late = n > a.deadline
    sub = await session.scalar(select(Submission).where(Submission.assignment_id == a.id, Submission.student_id == user.id))
    if sub is None:
        sub = Submission(assignment_id=a.id, student_id=user.id, submitted_at=n, is_late=late)
        session.add(sub)
    sub.file_id, sub.file_type, sub.text, sub.submitted_at, sub.is_late = fid, ftype, text, n, late
    xp_msg = ""
    if not sub.xp_awarded:   # XP faqat birinchi topshirishda
        if late:
            xp = XP_LATE
        else:
            xp = a.xp_reward + (XP_EARLY_BONUS if a.deadline - n > timedelta(hours=24) else 0)
        sub.xp_awarded = xp
        await add_xp(session, user, xp, "assignment")
        xp_msg = f"\n🎁 <b>+{xp} XP</b>" + (" (kechikkani uchun kam)" if late else "")
    await state.clear()
    await msg.answer("✅ Topshiriq qabul qilindi!" + xp_msg)
    creator = await session.get(User, a.creator_id)
    if creator:
        await send_many(bot, [creator.tg_id], f"📥 <b>{esc(user.full_name)}</b> «{esc(a.title)}» topshiriqni topshirdi"
                        + (" (kechikib)" if late else "") + ".")


# ======================= SARDOR / O'QITUVCHI =======================
@router.callback_query(F.data.startswith("mg:asg:"))
async def create_start(cb: CallbackQuery, state: FSMContext, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await state.clear()
    await state.update_data(gid=g.id)
    await state.set_state(AsgCreate.subject)
    await cb.message.answer(f"➕ <b>{esc(group_title(g))}</b> uchun yangi topshiriq.\n\n📖 Fan nomini yozing:\n(/cancel)")
    await cb.answer()


@router.message(AsgCreate.subject, F.text)
async def c_subject(msg: Message, state: FSMContext):
    await state.update_data(subject=msg.text.strip()[:150])
    await state.set_state(AsgCreate.title)
    await msg.answer("📝 Topshiriq sarlavhasi:")


@router.message(AsgCreate.title, F.text)
async def c_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text.strip()[:200])
    await state.set_state(AsgCreate.desc)
    await msg.answer("📄 Tavsif / talablar (yoki «-»):")


@router.message(AsgCreate.desc, F.text)
async def c_desc(msg: Message, state: FSMContext):
    await state.update_data(desc="" if msg.text.strip() == "-" else msg.text.strip()[:3000])
    await state.set_state(AsgCreate.deadline)
    await msg.answer("⏳ Muddat (Toshkent vaqti): <code>DD.MM.YYYY HH:MM</code>\nMasalan: <code>25.12.2026 23:59</code>")


@router.message(AsgCreate.deadline, F.text)
async def c_deadline(msg: Message, state: FSMContext):
    dl = parse_deadline(msg.text)
    if not dl or dl <= now():
        return await msg.answer("❌ Format noto'g'ri yoki vaqt o'tib ketgan. Masalan: <code>25.12.2026 23:59</code>")
    await state.update_data(deadline=dl.isoformat())
    await state.set_state(AsgCreate.file)
    await msg.answer("📎 Topshiriq fayli bo'lsa yuboring (PDF/rasm...), bo'lmasa «-» yozing:")


@router.message(AsgCreate.file, F.text | F.document | F.photo | F.video)
async def c_file(msg: Message, bot: Bot, state: FSMContext, session, user):
    from datetime import datetime
    fid, ftype = extract_file(msg)
    if not fid and (msg.text or "").strip() != "-":
        return await msg.answer("Fayl yuboring yoki «-» yozing.")
    d = await state.get_data()
    a = Assignment(group_id=d["gid"], creator_id=user.id, subject=d["subject"], title=d["title"],
                   description=d["desc"], deadline=datetime.fromisoformat(d["deadline"]),
                   file_id=fid, file_type=ftype, xp_reward=XP_ASSIGNMENT)
    session.add(a)
    await session.flush()
    await state.clear()
    ids = await group_member_tg_ids(session, a.group_id, exclude_tg=msg.from_user.id)
    text = (f"🆕 <b>Yangi topshiriq!</b>\n\n📖 {esc(a.subject)}\n📝 {esc(a.title)}\n\n{esc(a.description, '')}\n\n"
            f"⏳ Muddat: <b>{fmt_dt(a.deadline)}</b>\n🎁 +{a.xp_reward} XP\n\n«📝 Topshiriqlar» bo'limidan topshiring.")
    sent = await send_many(bot, ids, text)
    await msg.answer(f"✅ Topshiriq yaratildi va {sent} ta foydalanuvchiga yuborildi.")


@router.callback_query(F.data.startswith("mg:res:"))
async def results_list(cb: CallbackQuery, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    rows = (await session.scalars(select(Assignment).where(Assignment.group_id == g.id)
                                  .order_by(Assignment.deadline.desc()).limit(15))).all()
    await cb.answer()
    if not rows:
        return await cb.message.answer("Topshiriqlar yo'q.")
    await cb.message.answer("📊 Topshiriqni tanlang:", reply_markup=ikb(
        [[(f"{a.title[:30]} • {a.deadline:%d.%m}", f"rs:{a.id}")] for a in rows]))


@router.callback_query(F.data.startswith("rs:"))
async def results_detail(cb: CallbackQuery, session, user, is_super):
    a = await session.get(Assignment, int(cb.data.split(":")[1]))
    if not a or not await get_managed_group(session, user, is_super, a.group_id):
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    subs = (await session.execute(select(Submission, User).join(User, User.id == Submission.student_id)
                                  .where(Submission.assignment_id == a.id).order_by(Submission.submitted_at))).all()
    done_ids = {u.id for _, u in subs}
    students = (await session.scalars(select(User).where(
        User.group_id == a.group_id, User.role.in_([Role.STUDENT, Role.LEADER, Role.DEPUTY])))).all()
    missing = [u.full_name for u in students if u.id not in done_ids]
    text = (f"📊 <b>{esc(a.title)}</b>\nTopshirgan: <b>{len(subs)}</b>/{len(students)}\n")
    if missing:
        text += "\n❌ <b>Topshirmaganlar:</b>\n" + "\n".join(f"• {esc(m)}" for m in missing[:40])
    rows = [[(f"{'🏅' if s.grade is not None else '📄'} {u.full_name[:28]}{' ⏰' if s.is_late else ''}", f"rv:{s.id}")]
            for s, u in subs[:40]]
    rows.append([("🗑 Topshiriqni o'chirish", f"rd:{a.id}")])
    await cb.message.answer(text, reply_markup=ikb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("rv:"))
async def view_sub(cb: CallbackQuery, bot: Bot, session, user, is_super):
    s = await session.get(Submission, int(cb.data.split(":")[1]))
    a = await session.get(Assignment, s.assignment_id) if s else None
    if not a or not await get_managed_group(session, user, is_super, a.group_id):
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    st = await session.get(User, s.student_id)
    cap = (f"👤 {esc(st.full_name)}\n📝 {esc(a.title)}\n🕐 {fmt_dt(s.submitted_at)}"
           f"{' (kechikkan)' if s.is_late else ''}\n🏅 Baho: {s.grade if s.grade is not None else '—'}")
    kb = ikb([[("🏅 Baho qo'yish (0-100)", f"gr:{s.id}")]])
    if s.file_id:
        await send_file(bot, cb.message.chat.id, s.file_id, s.file_type, cap)
        await cb.message.answer("👆", reply_markup=kb)
    else:
        await cb.message.answer(cap + f"\n\n{esc(s.text)}", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("gr:"))
async def grade_start(cb: CallbackQuery, state: FSMContext):
    await state.update_data(sid=int(cb.data.split(":")[1]))
    await state.set_state(Grade.value)
    await cb.message.answer("🏅 Bahoni yuboring (0 dan 100 gacha):")
    await cb.answer()


@router.message(Grade.value, F.text)
async def grade_save(msg: Message, bot: Bot, state: FSMContext, session, user, is_super):
    if not msg.text.strip().isdigit() or not 0 <= int(msg.text) <= 100:
        return await msg.answer("❌ 0 dan 100 gacha butun son yuboring.")
    s = await session.get(Submission, (await state.get_data())["sid"])
    a = await session.get(Assignment, s.assignment_id)
    if not await get_managed_group(session, user, is_super, a.group_id):
        await state.clear()
        return await msg.answer("Ruxsat yo'q.")
    grade = int(msg.text)
    s.grade = grade
    bonus = grade // 10
    st = await session.get(User, s.student_id)
    await add_xp(session, st, bonus - s.grade_bonus, "grade")
    s.grade_bonus = bonus
    await state.clear()
    await msg.answer("✅ Baho saqlandi.")
    await send_many(bot, [st.tg_id], f"🏅 «{esc(a.title)}» uchun bahoyingiz: <b>{grade}/100</b>\n🎁 Bonus: +{bonus} XP")


@router.callback_query(F.data.startswith("rd:"))
async def del_assignment(cb: CallbackQuery, session, user, is_super):
    a = await session.get(Assignment, int(cb.data.split(":")[1]))
    if not a or not await get_managed_group(session, user, is_super, a.group_id):
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await session.execute(delete(Submission).where(Submission.assignment_id == a.id))
    await session.delete(a)
    await cb.answer("O'chirildi")
    await cb.message.edit_text("🗑 Topshiriq o'chirildi.")
