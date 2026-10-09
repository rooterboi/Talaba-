import os
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///aqlli_talaba.db")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
LESSON_REMIND_MIN = int(os.getenv("LESSON_REMIND_MIN", "15"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "30"))

# Gamifikatsiya
XP_ASSIGNMENT = 20       # o'z vaqtida topshirish
XP_EARLY_BONUS = 5       # muddatdan 24 soat oldin topshirsa
XP_LATE = 2              # kechikib topshirsa
XP_DAILY_BONUS = 2
XP_QUIZ_PER_CORRECT = 3
XP_QUIZ_DAILY_CAP = 15
ANON_DAILY_LIMIT = 5

# Juftliklar vaqti (o'zgartirish mumkin)
PAIR_TIMES = {
    1: (time(8, 30), time(9, 50)),
    2: (time(10, 0), time(11, 20)),
    3: (time(11, 30), time(12, 50)),
    4: (time(14, 0), time(15, 20)),
    5: (time(15, 30), time(16, 50)),
    6: (time(17, 0), time(18, 20)),
}
