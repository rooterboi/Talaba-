from datetime import date, datetime, time

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
                        Time, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Role:
    STUDENT = "student"
    TEACHER = "teacher"
    LEADER = "leader"      # Sardor
    DEPUTY = "deputy"      # Sardor o'rinbosari
    LABELS = {"student": "🎓 Talaba", "teacher": "👨‍🏫 O'qituvchi",
              "leader": "⭐ Guruh sardori", "deputy": "🔰 Sardor o'rinbosari"}
    MANAGERS = (TEACHER, LEADER, DEPUTY)


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("institution_id", "faculty", "direction", "course", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    faculty: Mapped[str] = mapped_column(String(150))
    direction: Mapped[str] = mapped_column(String(150))
    course: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(50))
    leader_code: Mapped[str] = mapped_column(String(12), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    institution: Mapped[Institution] = relationship(lazy="joined")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default=Role.STUDENT)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True, index=True)
    xp: Mapped[int] = mapped_column(Integer, default=0, index=True)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    last_bonus: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    group: Mapped[Group | None] = relationship(lazy="joined")
    institution: Mapped[Institution | None] = relationship(lazy="joined")


class TeacherGroup(Base):
    __tablename__ = "teacher_groups"
    __table_args__ = (UniqueConstraint("teacher_id", "group_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)           # 0=Dushanba
    pair_no: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    subject: Mapped[str] = mapped_column(String(150))
    teacher_name: Mapped[str] = mapped_column(String(100), default="")
    room: Mapped[str] = mapped_column(String(50), default="")
    lesson_type: Mapped[str] = mapped_column(String(30), default="Ma'ruza")
    week_type: Mapped[int] = mapped_column(Integer, default=0)  # 0 har hafta, 1 toq, 2 juft


class ReminderLog(Base):
    __tablename__ = "reminder_log"
    __table_args__ = (UniqueConstraint("schedule_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(Integer)
    day: Mapped[date] = mapped_column(Date)


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[datetime] = mapped_column(DateTime, index=True)
    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20)
    reminded_3h: Mapped[bool] = mapped_column(Boolean, default=False)
    reminded_1h: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_bonus: Mapped[int] = mapped_column(Integer, default=0)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)


class LibFile(Base):
    __tablename__ = "files"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(150), index=True)
    category: Mapped[str] = mapped_column(String(16))   # lecture/slide/test/book
    title: Mapped[str] = mapped_column(String(200))
    file_id: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    important: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnonMessage(Base):
    __tablename__ = "anon_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))   # faqat suiiste'molni oldini olish uchun; hech kimga ko'rsatilmaydi
    target: Mapped[str] = mapped_column(String(10))                  # leader | teacher
    text: Mapped[str] = mapped_column(Text)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class XPLog(Base):
    __tablename__ = "xp_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)
