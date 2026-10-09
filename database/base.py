from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"timeout": 30} if "sqlite" in DATABASE_URL else {})
SessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    from database import models  # noqa: F401  (jadvallarni ro'yxatdan o'tkazish)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in DATABASE_URL:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")


async def seed():
    from sqlalchemy import select
    from database.models import Institution
    async with SessionMaker() as s:
        if (await s.execute(select(Institution.id).limit(1))).first():
            return
        for n in ["Toshkent axborot texnologiyalari universiteti (TATU)",
                  "O'zbekiston Milliy universiteti (O'zMU)",
                  "Samarqand davlat universiteti (SamDU)",
                  "Boshqa OTM / kollej / litsey"]:
            s.add(Institution(name=n))
        await s.commit()
