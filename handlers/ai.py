import io
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (CallbackQuery, ChosenInlineResult, InlineKeyboardButton, InlineKeyboardMarkup,
                           InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message)
from sqlalchemy import select

from config import AI_DAILY_LIMIT, XP_QUIZ_DAILY_CAP, XP_QUIZ_PER_CORRECT
from database.models import AIUsage
from handlers.filters import Registered
from keyboards.inline import ai_menu_kb, ikb
from services import ai_service
from services.xp import add_xp, xp_today
from states.states import AI
from utils.helpers import chunks, esc
from utils.timeutil import today

log = logging.getLogger(__name__)
router = Router()

OFF = "🤖 AI yordamchi hozircha sozlanmagan (ANTHROPIC_API_KEY kiritilmagan)."
LIMIT = f"⚠️ Kunlik AI limiti ({AI_DAILY_LIMIT} ta so'rov) tugadi. Ertaga qayta urinib ko'ring."
EXIT_KB = ikb([[("❌ Chiqish", "ai:exit")]])


async def use_quota(session, user) -> bool:
    row = await session.scalar(select(AIUsage).where(AIUsage.user_id == user.id, AIUsage.day == today()))
    if row is None:
        row = AIUsage(user_id=user.id, day=today(), count=0)
        session.add(row)
    if row.count >= AI_DAILY_LIMIT:
        return False
    row.count += 1
    return True


async def reply_long(msg: Message, text: str):
    for part in chunks(text or "Javob bo'sh qaytdi."):
        await msg.answer(part, parse_mode=None)


async def open_menu(msg: Message):
    await msg.answer("🤖 <b>AI o'quv yordamchi</b>\n\nNima qilamiz?", reply_markup=ai_menu_kb())


@router.callback_query(F.data.startswith("ai:"), Registered())
async def ai_menu_cb(cb: CallbackQuery, state: FSMContext):
    act = cb.data.split(":")[1]
    await cb.answer()
    if act == "exit":
        await state.clear()
        return await cb.message.answer("✅ AI rejimidan chiqdingiz.")
    if not ai_service.ai_enabled():
        return await cb.message.answer(OFF)
    if act == "summary":
        await state.set_state(AI.summary)
        await cb.message.answer("📝 Konspekt qilinadigan matnni yuboring (yoki .txt / .pdf fayl, 5 MB gacha):", reply_markup=EXIT_KB)
    elif act == "chat":
        await state.set_state(AI.chat)
        await state.update_data(history=[])
        await cb.message.answer("❓ Savolingizni yozing. Suhbat davom etadi — tugatish uchun «Chiqish».", reply_markup=EXIT_KB)
    elif act == "quiz":
        await state.set_state(AI.quiz_topic)
        await cb.message.answer("🧪 Test mavzusini yozing (masalan: <i>Python ro'yxatlar</i>):", reply_markup=EXIT_KB)


@router.message(AI.summary, Registered(), F.text | F.document)
async def do_summary(msg: Message, bot: Bot, state: FSMContext, session, user):
    text = msg.text
    if msg.document:
        d = msg.document
        if d.file_size and d.file_size > 5 * 1024 * 1024:
            return await msg.answer("❌ Fayl 5 MB dan katta.")
        buf = io.BytesIO()
        await bot.download(d, destination=buf)
        name = (d.file_name or "").lower()
        try:
            if name.endswith(".pdf"):
                from pypdf import PdfReader
                text = "\n".join((p.extract_text() or "") for p in PdfReader(buf).pages[:40])
            elif name.endswith(".txt"):
                text = buf.getvalue().decode("utf-8", errors="ignore")
            else:
                return await msg.answer("❌ Faqat .txt yoki .pdf qabul qilinadi.")
        except Exception:
            return await msg.answer("❌ Faylni o'qib bo'lmadi.")
    if not text or len(text.strip()) < 80:
        return await msg.answer("❌ Matn juda qisqa (kamida 80 belgi).")
    if not await use_quota(session, user):
        return await msg.answer(LIMIT)
    await bot.send_chat_action(msg.chat.id, "typing")
    try:
        await reply_long(msg, await ai_service.summarize(text))
    except Exception:
        log.exception("AI summarize")
        await msg.answer("⚠️ AI xizmatida xatolik. Birozdan so'ng urinib ko'ring.")


@router.message(AI.chat, Registered(), F.text)
async def do_chat(msg: Message, bot: Bot, state: FSMContext, session, user):
    if not await use_quota(session, user):
        return await msg.answer(LIMIT)
    hist = (await state.get_data()).get("history", [])
    hist.append({"role": "user", "content": msg.text[:4000]})
    await bot.send_chat_action(msg.chat.id, "typing")
    try:
        ans = await ai_service.ask(hist[-8:])
    except Exception:
        log.exception("AI chat")
        hist.pop()
        return await msg.answer("⚠️ AI xizmatida xatolik. Birozdan so'ng urinib ko'ring.")
    hist.append({"role": "assistant", "content": ans})
    await state.update_data(history=hist[-8:])
    await reply_long(msg, ans)


# ---------------- Test (XP) ----------------
@router.message(AI.quiz_topic, Registered(), F.text)
async def quiz_topic(msg: Message, bot: Bot, state: FSMContext, session, user):
    if not await use_quota(session, user):
        return await msg.answer(LIMIT)
    await msg.answer("⏳ Test tayyorlanmoqda...")
    try:
        quiz = await ai_service.make_quiz(msg.text.strip()[:120])
    except Exception:
        log.exception("AI quiz")
        quiz = []
    if not quiz:
        return await msg.answer("⚠️ Test yaratib bo'lmadi. Boshqa mavzu yozing.")
    await state.set_state(AI.quiz)
    await state.update_data(quiz=quiz, qi=0, score=0)
    await send_question(msg, quiz, 0)


async def send_question(msg: Message, quiz, i):
    q = quiz[i]
    text = f"❓ <b>{i + 1}/{len(quiz)}</b>\n{esc(q['q'])}\n\n" + "\n".join(f"{'ABCD'[k]}) {esc(o)}" for k, o in enumerate(q["options"]))
    await msg.answer(text, reply_markup=ikb([[(c, f"qz:{i}:{k}") for k, c in enumerate("ABCD")]]))


@router.callback_query(AI.quiz, F.data.startswith("qz:"), Registered())
async def quiz_answer(cb: CallbackQuery, state: FSMContext, session, user):
    _, i, k = cb.data.split(":")
    d = await state.get_data()
    quiz, qi, score = d["quiz"], d["qi"], d["score"]
    if int(i) != qi:
        return await cb.answer("Bu savol allaqachon javoblangan")
    right = quiz[qi]["answer"]
    ok = int(k) == right
    score += ok
    await cb.message.edit_text(cb.message.html_text + f"\n\n{'✅ To‘g‘ri!' if ok else '❌ Xato. To‘g‘ri javob: ' + 'ABCD'[right]}")
    qi += 1
    if qi < len(quiz):
        await state.update_data(qi=qi, score=score)
        await cb.answer()
        return await send_question(cb.message, quiz, qi)
    earned = min(score * XP_QUIZ_PER_CORRECT, max(0, XP_QUIZ_DAILY_CAP - await xp_today(session, user.id, "quiz")))
    await add_xp(session, user, earned, "quiz")
    await state.clear()
    await cb.message.answer(f"🏁 Natija: <b>{score}/{len(quiz)}</b>\n🎁 +{earned} XP"
                            + ("" if earned else "\n(Bugungi test XP limiti tugagan)"))
    await cb.answer()


# ---------------- Inline rejim: @bot savol ----------------
@router.inline_query()
async def inline_q(q: InlineQuery, bot: Bot, user):
    text = (q.query or "").strip()
    if user is None or not ai_service.ai_enabled():
        r = InlineQueryResultArticle(id="x", title="Avval botda ro'yxatdan o'ting" if user is None else "AI o'chiq",
                                     input_message_content=InputTextMessageContent(message_text="🎓 Aqlli Talaba bot"))
        return await q.answer([r], cache_time=5, is_personal=True)
    if len(text) < 4:
        return await q.answer([], cache_time=1, is_personal=True)
    me = await bot.me()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🤖 Aqlli Talaba", url=f"https://t.me/{me.username}")]])
    r = InlineQueryResultArticle(
        id="ai", title="🤖 AI dan so'rash", description=text[:80],
        input_message_content=InputTextMessageContent(message_text=f"❓ {text}\n\n⏳ Javob tayyorlanmoqda...", parse_mode=None),
        reply_markup=kb)
    await q.answer([r], cache_time=1, is_personal=True)


@router.chosen_inline_result()
async def inline_chosen(c: ChosenInlineResult, bot: Bot, session, user):
    if not c.inline_message_id or user is None or not ai_service.ai_enabled():
        return
    if not await use_quota(session, user):
        return await bot.edit_message_text(LIMIT, inline_message_id=c.inline_message_id, parse_mode=None)
    try:
        ans = await ai_service.ask([{"role": "user", "content": c.query[:1500]}], max_tokens=700)
        await bot.edit_message_text(f"❓ {c.query}\n\n🤖 {ans}"[:4000], inline_message_id=c.inline_message_id, parse_mode=None)
    except Exception:
        log.exception("inline AI")
        await bot.edit_message_text("⚠️ AI xatolik berdi.", inline_message_id=c.inline_message_id, parse_mode=None)
