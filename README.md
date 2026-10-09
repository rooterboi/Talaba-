# 🎓 Aqlli Talaba — o'quv jarayoni boti (aiogram 3 + SQLAlchemy async)

## Ishga tushirish
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN, ADMIN_IDS, (ixtiyoriy) ANTHROPIC_API_KEY
python main.py
```
BotFather'da: `/setinline` (inline rejim) va `/setinlinefeedback` → **Enabled (100%)** (inline AI javob uchun).

## Struktura
```
main.py                  – start: DB, middleware, routerlar, APScheduler, polling
config.py                – .env, XP qiymatlari, juftlik vaqtlari (PAIR_TIMES)
database/base.py         – async engine, SessionMaker, init_db, seed (OTM lar)
database/models.py       – users, groups, teacher_groups, schedules, assignments,
                           submissions, files, announcements, anon_messages, xp_log, ai_usage
middlewares/db.py        – sessiya + user + is_super + commit; ThrottleMiddleware
handlers/registration.py – FSM ro'yxatdan o'tish + qayta ishlatiladigan guruh tanlash (picker)
handlers/menu.py         – menyu tugmalari (FSM ni bekor qiladi), /cancel, /help
handlers/profile.py      – profil, sardor kodi, guruh almashtirish, o'qituvchi guruhlari
handlers/schedule.py     – Bugun/Ertaga/Haftalik + jadval qo'shish/o'chirish
handlers/assignments.py  – topshiriq yaratish, topshirish, natijalar, baholash, XP
handlers/library.py      – fan→bo'lim→fayl, qidiruv, material yuklash (file_id)
handlers/ai.py           – konspekt, savol-javob, test (+XP), inline rejim
handlers/rating.py       – guruh / OTM / OTMlar reytingi
handlers/anon.py         – anonim murojaat va anonim javob
handlers/announce.py     – "push" e'lonlar (muhim → pin)
handlers/manager.py      – boshqaruv paneli, a'zolar, o'rinbosar, kod yangilash
handlers/admin.py        – Super Admin: statistika, OTM, rol, ban, rassilka
services/                – xp, access (ruxsatlar), notify, ai_service, scheduler
```

## Rollar
* **Talaba** — ro'yxatdan o'tganda. **O'qituvchi** — ro'yxatdan o'tganda tanlanadi, so'ng guruhlarini qo'shadi.
* **Sardor** — guruh yaratilganda ko'rsatiladigan *sardor kodi* orqali (Profil → 🔑).
  **O'rinbosar** — sardor/o'qituvchi «👥 A'zolar» dan tayinlaydi.
* **Super Admin** — `.env` dagi `ADMIN_IDS` (barcha guruhlarni boshqara oladi + /admin).

## Eslatmalar (APScheduler, har daqiqa)
* Dars boshlanishiga `LESSON_REMIND_MIN` (15) daqiqa qolganda guruhga va shu fanni o'tadigan o'qituvchiga.
* Topshiriq muddatiga 3 soat va 1 soat qolganda — faqat topshirmaganlarga.
* Toq/juft hafta ISO hafta raqami bo'yicha aniqlanadi. Vaqt: `TIMEZONE` (Asia/Tashkent).

## XP tizimi (config.py)
Topshiriq +20 (24 soat oldin +5, kechiksa +2) • baho/10 bonus • kunlik kirish +2 •
AI test: to'g'ri javob +3 (kuniga ≤15).

## Production uchun tavsiyalar
* `MemoryStorage` → `RedisStorage`; SQLite → PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`).
* Alembic migratsiyalari qo'shing (hozir `create_all`).
* Anonim xabarlarda `sender_id` faqat suiiste'molni oldini olish uchun saqlanadi va hech kimga ko'rsatilmaydi.
* AI modeli `AI_MODEL` orqali almashtiriladi; kunlik limit `AI_DAILY_LIMIT`.
