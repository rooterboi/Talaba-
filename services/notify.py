import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

log = logging.getLogger(__name__)


async def send_many(bot: Bot, tg_ids, text: str, *, reply_markup=None, pin: bool = False) -> int:
    """Ommaviy xabar (flood-limitga mos). Yetkazilganlar sonini qaytaradi."""
    ok = 0
    for uid in tg_ids:
        for attempt in range(2):
            try:
                m = await bot.send_message(uid, text, reply_markup=reply_markup)
                if pin:
                    try:
                        await bot.pin_chat_message(uid, m.message_id, disable_notification=False)
                    except Exception:
                        pass
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                break
            except Exception as e:
                log.debug("send_many %s: %s", uid, e)
                break
        await asyncio.sleep(0.04)
    return ok
