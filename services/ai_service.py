import json
import logging
import re

from config import ANTHROPIC_API_KEY, AI_MODEL

log = logging.getLogger(__name__)

SYSTEM = ("Sen O'zbekiston talabalari va o'qituvchilari uchun o'quv yordamchisan. "
          "Foydalanuvchi qaysi tilda yozsa, o'sha tilda (asosan o'zbek, lotin yozuvida) javob ber. "
          "Javoblar aniq, tuzilgan va qisqa bo'lsin. Bilmasang, uydirma qilma.")

_client = None


def ai_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


async def ask(messages: list[dict], system: str = SYSTEM, max_tokens: int = 1400) -> str:
    resp = await _get_client().messages.create(
        model=AI_MODEL, max_tokens=max_tokens, system=system, messages=messages)
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


async def summarize(text: str) -> str:
    prompt = ("Quyidagi matnni talaba uchun konspekt qil: 1) 2-3 gapli qisqa mazmun, 2) asosiy tushunchalar "
              "(punktlar bilan), 3) eslab qolish uchun 3 ta nazorat savoli.\n\nMATN:\n" + text[:12000])
    return await ask([{"role": "user", "content": prompt}], max_tokens=1600)


async def make_quiz(topic: str, n: int = 5) -> list[dict]:
    prompt = (f"'{topic}' mavzusi bo'yicha {n} ta test savoli tuz. FAQAT JSON qaytar, boshqa matn yozma. Format: "
              '[{"q":"savol","options":["A","B","C","D"],"answer":0}] — answer to\'g\'ri variant indeksi (0-3).')
    raw = await ask([{"role": "user", "content": prompt}], max_tokens=1800)
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in items:
        try:
            opts = [str(o)[:60] for o in it["options"]][:4]
            ans = int(it["answer"])
            if len(opts) == 4 and 0 <= ans < 4:
                out.append({"q": str(it["q"])[:300], "options": opts, "answer": ans})
        except (KeyError, ValueError, TypeError):
            continue
    return out[:n]
