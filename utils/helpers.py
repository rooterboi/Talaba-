import html
import secrets

from aiogram.types import Message


def esc(x, default="—") -> str:
    return html.escape(str(x)) if x not in (None, "") else default


def chunks(text: str, n: int = 3900):
    for i in range(0, len(text), n):
        yield text[i:i + n]


async def safe_edit(msg: Message, text: str, kb=None):
    try:
        await msg.edit_text(text, reply_markup=kb)
    except Exception:
        await msg.answer(text, reply_markup=kb)


def group_title(g) -> str:
    return f"{g.name} • {g.course}-kurs • {g.direction}"


def new_code() -> str:
    return secrets.token_hex(3).upper()


def extract_file(msg: Message):
    """(file_id, file_type) — document/photo/video/audio."""
    if msg.document:
        return msg.document.file_id, "document"
    if msg.photo:
        return msg.photo[-1].file_id, "photo"
    if msg.video:
        return msg.video.file_id, "video"
    if msg.audio:
        return msg.audio.file_id, "audio"
    return None, None


async def send_file(bot, chat_id: int, file_id: str, ftype: str, caption: str | None = None):
    fn = {"document": bot.send_document, "photo": bot.send_photo,
          "video": bot.send_video, "audio": bot.send_audio}.get(ftype, bot.send_document)
    return await fn(chat_id, file_id, caption=caption)
