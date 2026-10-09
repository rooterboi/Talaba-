"""Ro'yxatdan o'tish (FSM) va guruh tanlash (qayta ishlatiladigan 'picker')."""
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database.models import Group, Institution, Role, TeacherGroup, User
from keyboards.inline import course_kb, ikb, opts_kb, role_kb
from keyboards.reply import main_menu
from services.xp import daily_bonus
from states.states import Pick, Reg
from utils.helpers import esc, group_title, new_code

router = Router()

WELCOME = ("🎓 <b>Aqlli Talaba</b> — o'quv jarayoningiz uchun yagona yordamchi!\n\n"
           "📅 Dars jadvali • 📝 Topshiriqlar • 📚 Kutubxona • 🤖 AI • 🏆 Reyting\n\n"
           "Boshlash uchun rolingizni tanlang:")


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext, session, user, is_super):
    await state.clear()
    if user:
        bonus = await daily_bonus(session, user)
        text = f"👋 Xush kelibsiz, <b>{esc(user.full_name)}</b>!"
        if bonus:
            text += f"\n🎁 Kunlik bonus: <b>+{bonus} XP</b>"
        return await msg.answer(text, reply_markup=main_menu(user, is_super))
    await state.set_state(Reg.role)
    await msg.answer(WELCOME, reply_markup=role_kb())


@router.callback_query(Reg.role, F.data.startswith("reg:role:"))
async def pick_role(cb: CallbackQuery, state: FSMContext):
    await state.update_data(role=cb.data.split(":")[2])
    await state.set_state(Reg.name)
    await cb.message.edit_text("✍️ Ism va familiyangizni yozing (masalan: <i>Aliyev Vali</i>):")
    await cb.answer()


@router.message(Reg.name, F.text)
async def get_name(msg: Message, state: FSMContext, session):
    name = " ".join(msg.text.split())
    if len(name.split()) < 2 or not 5 <= len(name) <= 80:
        return await msg.answer("❌ Iltimos, ism va familiyani to'liq yozing.")
    insts = (await session.scalars(select(Institution).order_by(Institution.name))).all()
    if not insts:
        await state.clear()
        return await msg.answer("⚠️ Hozircha OTM ro'yxati bo'sh. Admin bilan bog'laning.")
    await state.update_data(full_name=name)
    await state.set_state(Reg.institution)
    await msg.answer("🏛 OTM / kollej / litseyingizni tanlang:",
                     reply_markup=ikb([[(i.name[:60], f"reg:inst:{i.id}")] for i in insts]))


@router.callback_query(Reg.institution, F.data.startswith("reg:inst:"))
async def pick_inst(cb: CallbackQuery, state: FSMContext, session, is_super):
    iid = int(cb.data.split(":")[2])
    d = await state.get_data()
    if d.get("role") == Role.TEACHER:
        u = User(tg_id=cb.from_user.id, full_name=d["full_name"], username=cb.from_user.username,
                 role=Role.TEACHER, institution_id=iid)
        session.add(u)
        await session.flush()
        await state.clear()
        await cb.message.edit_text("✅ O'qituvchi sifatida ro'yxatdan o'tdingiz!")
        await cb.message.answer("Dars beradigan guruhlaringizni qo'shing 👇",
                                reply_markup=ikb([[("➕ Guruh qo'shish", "tg:add")]]))
        await cb.message.answer("Asosiy menyu 👇", reply_markup=main_menu(u, is_super))
    else:
        await cb.message.delete()
        await start_picker(cb.message, state, session, iid, "reg")
    await cb.answer()


# ======================= GURUH TANLASH (picker) =======================
async def start_picker(target: Message, state: FSMContext, session, inst_id: int, purpose: str):
    """purpose: reg | teacher_add | change"""
    await state.update_data(inst=inst_id, purpose=purpose)
    await ask_faculty(target, state, session)


async def _lost(target: Message, state: FSMContext):
    await state.clear()
    await target.answer("⚠️ Sessiya tugagan. /start ni bosing.")


async def _distinct(session, col, *conds):
    return sorted((await session.scalars(select(col).where(*conds).distinct())).all())


async def ask_faculty(target, state, session):
    d = await state.get_data()
    if "inst" not in d:
        return await _lost(target, state)
    opts = await _distinct(session, Group.faculty, Group.institution_id == d["inst"])
    if not opts:
        await state.set_state(Pick.new_faculty)
        return await target.answer("✍️ Fakultet nomini yozing:")
    await state.update_data(opts=opts)
    await state.set_state(Pick.faculty)
    await target.answer("🏛 Fakultetni tanlang:", reply_markup=opts_kb("pk:fac", opts, "➕ Boshqa fakultet"))


async def ask_direction(target, state, session):
    d = await state.get_data()
    opts = await _distinct(session, Group.direction, Group.institution_id == d["inst"], Group.faculty == d["faculty"])
    if not opts:
        await state.set_state(Pick.new_direction)
        return await target.answer("✍️ Yo'nalish nomini yozing:")
    await state.update_data(opts=opts)
    await state.set_state(Pick.direction)
    await target.answer("📚 Yo'nalishni tanlang:", reply_markup=opts_kb("pk:dir", opts, "➕ Boshqa yo'nalish"))


async def ask_course(target, state):
    await state.set_state(Pick.course)
    await target.answer("🔢 Kursni tanlang:", reply_markup=course_kb())


async def ask_group(target, state, session):
    d = await state.get_data()
    groups = (await session.scalars(select(Group).where(
        Group.institution_id == d["inst"], Group.faculty == d["faculty"],
        Group.direction == d["direction"], Group.course == d["course"]).order_by(Group.name))).all()
    if not groups:
        await state.set_state(Pick.new_group)
        return await target.answer("✍️ Guruh nomini yozing (masalan: <b>101-21</b>):")
    await state.set_state(Pick.group)
    rows = [[(g.name, f"pk:grp:{g.id}")] for g in groups] + [[("➕ Yangi guruh", "pk:grp:new")]]
    await target.answer("👥 Guruhingizni tanlang:", reply_markup=ikb(rows))


@router.callback_query(Pick.faculty, F.data.startswith("pk:fac:"))
async def fac_cb(cb: CallbackQuery, state: FSMContext, session):
    v = cb.data.split(":")[2]
    await cb.answer()
    if v == "new":
        await state.set_state(Pick.new_faculty)
        return await cb.message.answer("✍️ Fakultet nomini yozing:")
    await state.update_data(faculty=(await state.get_data())["opts"][int(v)])
    await ask_direction(cb.message, state, session)


@router.message(Pick.new_faculty, F.text)
async def fac_txt(msg: Message, state: FSMContext, session):
    await state.update_data(faculty=msg.text.strip()[:150])
    await ask_direction(msg, state, session)


@router.callback_query(Pick.direction, F.data.startswith("pk:dir:"))
async def dir_cb(cb: CallbackQuery, state: FSMContext):
    v = cb.data.split(":")[2]
    await cb.answer()
    if v == "new":
        await state.set_state(Pick.new_direction)
        return await cb.message.answer("✍️ Yo'nalish nomini yozing:")
    await state.update_data(direction=(await state.get_data())["opts"][int(v)])
    await ask_course(cb.message, state)


@router.message(Pick.new_direction, F.text)
async def dir_txt(msg: Message, state: FSMContext):
    await state.update_data(direction=msg.text.strip()[:150])
    await ask_course(msg, state)


@router.callback_query(Pick.course, F.data.startswith("pk:course:"))
async def course_cb(cb: CallbackQuery, state: FSMContext, session):
    await state.update_data(course=int(cb.data.split(":")[2]))
    await cb.answer()
    await ask_group(cb.message, state, session)


@router.callback_query(Pick.group, F.data.startswith("pk:grp:"))
async def grp_cb(cb: CallbackQuery, state: FSMContext, session, user, is_super):
    v = cb.data.split(":")[2]
    await cb.answer()
    if v == "new":
        await state.set_state(Pick.new_group)
        return await cb.message.answer("✍️ Guruh nomini yozing (masalan: <b>101-21</b>):")
    g = await session.get(Group, int(v))
    d = await state.get_data()
    if not g or g.institution_id != d.get("inst"):
        return await cb.message.answer("❌ Guruh topilmadi.")
    await finish(cb.message, cb.from_user, state, session, g, user, is_super, False)


@router.message(Pick.new_group, F.text)
async def grp_new(msg: Message, state: FSMContext, session, user, is_super):
    d = await state.get_data()
    if "inst" not in d:
        return await _lost(msg, state)
    name = msg.text.strip().upper()[:50]
    g = await session.scalar(select(Group).where(
        Group.institution_id == d["inst"], Group.faculty == d["faculty"], Group.direction == d["direction"],
        Group.course == d["course"], Group.name == name))
    created = g is None
    if created:
        code = new_code()
        while await session.scalar(select(Group.id).where(Group.leader_code == code)):
            code = new_code()
        g = Group(institution_id=d["inst"], faculty=d["faculty"], direction=d["direction"],
                  course=d["course"], name=name, leader_code=code)
        session.add(g)
        await session.flush()
    await finish(msg, msg.from_user, state, session, g, user, is_super, created)


async def finish(target: Message, tg_user, state, session, group: Group, user, is_super, created: bool):
    d = await state.get_data()
    purpose = d.get("purpose")
    await state.clear()
    if purpose == "reg":
        u = User(tg_id=tg_user.id, full_name=d["full_name"], username=tg_user.username, role=Role.STUDENT,
                 institution_id=group.institution_id, group_id=group.id)
        session.add(u)
        await session.flush()
        await target.answer(f"🎉 Ro'yxatdan o'tdingiz!\n👥 Guruh: <b>{esc(group_title(group))}</b>",
                            reply_markup=main_menu(u, is_super))
    elif purpose == "teacher_add" and user:
        if not await session.scalar(select(TeacherGroup.id).where(
                TeacherGroup.teacher_id == user.id, TeacherGroup.group_id == group.id)):
            session.add(TeacherGroup(teacher_id=user.id, group_id=group.id))
        await target.answer(f"✅ <b>{esc(group_title(group))}</b> guruhi qo'shildi.")
    elif purpose == "change" and user:
        user.group_id, user.institution_id = group.id, group.institution_id
        if user.role in (Role.LEADER, Role.DEPUTY):
            user.role = Role.STUDENT
        await target.answer(f"✅ Guruhingiz o'zgartirildi: <b>{esc(group_title(group))}</b>")
    if created:
        await target.answer(
            f"🆕 Yangi guruh yaratildi.\n🔑 <b>Sardor kodi:</b> <code>{group.leader_code}</code>\n\n"
            f"Sardor bo'lish uchun: Profil → «🔑 Sardor kodini kiritish». "
            f"Kodni faqat ishonchli odamga bering!")
