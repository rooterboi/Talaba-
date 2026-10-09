from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, or_, select

from database.models import Group, LibFile, Role
from handlers.filters import Registered
from keyboards.inline import CATS, ikb
from services.access import get_managed_group, teacher_group_ids
from states.states import LibSearch, LibUpload
from utils.helpers import esc, extract_file, group_title, send_file

router = Router()
router.message.filter(Registered())
router.callback_query.filter(Registered())


async def scope(session, user):
    gids = await teacher_group_ids(session, user) if user.role == Role.TEACHER else ([user.group_id] if user.group_id else [])
    return or_(LibFile.group_id.in_(gids) if gids else False,
               and_(LibFile.group_id.is_(None), LibFile.institution_id == user.institution_id))


async def open_menu(msg: Message, state: FSMContext, session, user):
    subs = sorted((await session.scalars(select(LibFile.subject).where(await scope(session, user)).distinct())).all())
    await state.update_data(lib_subjects=subs)
    rows = [[(f"📘 {s[:45]}", f"lb:s:{i}")] for i, s in enumerate(subs[:50])]
    rows.append([("🔎 Qidirish", "lb:search")])
    await msg.answer("📚 <b>Raqamli kutubxona</b>\n" + ("Fanni tanlang:" if subs else "Hozircha material yo'q."),
                     reply_markup=ikb(rows))


@router.callback_query(F.data.startswith("lb:s:"))
async def pick_subject(cb: CallbackQuery, state: FSMContext):
    subs = (await state.get_data()).get("lib_subjects", [])
    i = int(cb.data.split(":")[2])
    if i >= len(subs):
        return await cb.answer("Ro'yxat eskirgan, qayta oching", show_alert=True)
    await state.update_data(lib_subject=subs[i])
    rows = [[(label, f"lb:c:{k}")] for k, label in CATS.items()]
    await cb.message.answer(f"📘 <b>{esc(subs[i])}</b>\nBo'limni tanlang:", reply_markup=ikb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("lb:c:"))
async def pick_cat(cb: CallbackQuery, state: FSMContext, session, user):
    subject = (await state.get_data()).get("lib_subject")
    if not subject:
        return await cb.answer("Qayta oching", show_alert=True)
    cat = cb.data.split(":")[2]
    files = (await session.scalars(select(LibFile).where(
        await scope(session, user), LibFile.subject == subject, LibFile.category == cat)
        .order_by(LibFile.id.desc()).limit(40))).all()
    await cb.answer()
    if not files:
        return await cb.message.answer("Bu bo'limda hozircha material yo'q.")
    await cb.message.answer(f"{CATS[cat]} — <b>{esc(subject)}</b>", reply_markup=ikb(
        [[(f"{f.title[:45]} ({f.downloads}⬇️)", f"lb:f:{f.id}")] for f in files]))


@router.callback_query(F.data.startswith("lb:f:"))
async def send_lib(cb: CallbackQuery, bot: Bot, session, user):
    f = await session.get(LibFile, int(cb.data.split(":")[2]))
    if not f:
        return await cb.answer("Topilmadi", show_alert=True)
    f.downloads += 1
    await send_file(bot, cb.message.chat.id, f.file_id, f.file_type, f"📚 {esc(f.title)}\n📘 {esc(f.subject)}")
    await cb.answer("📥")


@router.callback_query(F.data == "lb:search")
async def search_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(LibSearch.query)
    await cb.message.answer("🔎 Fan yoki material nomini yozing:")
    await cb.answer()


@router.message(LibSearch.query, F.text)
async def search_do(msg: Message, state: FSMContext, session, user):
    await state.clear()
    like = f"%{msg.text.strip()}%"
    files = (await session.scalars(select(LibFile).where(
        await scope(session, user), or_(LibFile.title.ilike(like), LibFile.subject.ilike(like)))
        .order_by(LibFile.downloads.desc()).limit(30))).all()
    if not files:
        return await msg.answer("😔 Hech narsa topilmadi.")
    await msg.answer("🔎 Natijalar:", reply_markup=ikb([[(f"{f.title[:40]} • {f.subject[:15]}", f"lb:f:{f.id}")] for f in files]))


# ======================= YUKLASH (sardor / o'qituvchi) =======================
@router.callback_query(F.data.startswith("mg:lib:"))
async def up_start(cb: CallbackQuery, state: FSMContext, session, user, is_super):
    g = await get_managed_group(session, user, is_super, int(cb.data.split(":")[2]))
    if not g:
        return await cb.answer("Ruxsat yo'q", show_alert=True)
    await state.clear()
    await state.update_data(gid=g.id)
    await state.set_state(LibUpload.scope)
    rows = [[("👥 Faqat shu guruh uchun", "lu:g")]]
    if user.role == Role.TEACHER or is_super:
        rows.append([("🏛 Butun OTM uchun", "lu:i")])
    await cb.message.answer(f"📚 Material kimlar uchun? ({esc(group_title(g))})", reply_markup=ikb(rows))
    await cb.answer()


@router.callback_query(LibUpload.scope, F.data.in_({"lu:g", "lu:i"}))
async def up_scope(cb: CallbackQuery, state: FSMContext):
    await state.update_data(whole=cb.data == "lu:i")
    await state.set_state(LibUpload.subject)
    await cb.message.edit_text("📘 Fan nomini yozing:")
    await cb.answer()


@router.message(LibUpload.subject, F.text)
async def up_subject(msg: Message, state: FSMContext):
    await state.update_data(subject=msg.text.strip()[:150])
    await state.set_state(LibUpload.category)
    await msg.answer("Turini tanlang:", reply_markup=ikb([[(l, f"lu:c:{k}")] for k, l in CATS.items()]))


@router.callback_query(LibUpload.category, F.data.startswith("lu:c:"))
async def up_cat(cb: CallbackQuery, state: FSMContext):
    await state.update_data(category=cb.data.split(":")[2])
    await state.set_state(LibUpload.title)
    await cb.message.edit_text("🏷 Material nomini yozing:")
    await cb.answer()


@router.message(LibUpload.title, F.text)
async def up_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text.strip()[:200])
    await state.set_state(LibUpload.file)
    await msg.answer("📎 Faylni yuboring (PDF, PPT, DOC, rasm, video...):")


@router.message(LibUpload.file, F.document | F.photo | F.video | F.audio)
async def up_file(msg: Message, state: FSMContext, session, user, is_super):
    fid, ftype = extract_file(msg)
    d = await state.get_data()
    g = await get_managed_group(session, user, is_super, d["gid"])
    if not g:
        await state.clear()
        return await msg.answer("Ruxsat yo'q.")
    session.add(LibFile(institution_id=g.institution_id, group_id=None if d["whole"] else g.id,
                        subject=d["subject"], category=d["category"], title=d["title"],
                        file_id=fid, file_type=ftype, uploader_id=user.id))
    await state.clear()
    await msg.answer("✅ Material kutubxonaga qo'shildi!")

