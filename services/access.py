from sqlalchemy import select

from database.models import Group, Role, TeacherGroup, User


async def teacher_group_ids(session, user: User) -> list[int]:
    return list((await session.scalars(select(TeacherGroup.group_id).where(TeacherGroup.teacher_id == user.id))).all())


async def managed_groups(session, user: User, is_super: bool) -> list[Group]:
    if is_super:
        return list((await session.scalars(select(Group).order_by(Group.id.desc()).limit(30))).all())
    if user.role == Role.TEACHER:
        q = select(Group).join(TeacherGroup, TeacherGroup.group_id == Group.id).where(TeacherGroup.teacher_id == user.id)
        return list((await session.scalars(q)).all())
    if user.role in (Role.LEADER, Role.DEPUTY) and user.group_id:
        return [user.group]
    return []


async def get_managed_group(session, user: User, is_super: bool, gid: int) -> Group | None:
    for g in await managed_groups(session, user, is_super):
        if g.id == gid:
            return g
    return None


async def group_member_tg_ids(session, group_id: int, only_notify=False, exclude_tg: int | None = None) -> list[int]:
    q = select(User.tg_id).where(User.group_id == group_id, User.banned.is_(False))
    if only_notify:
        q = q.where(User.notify.is_(True))
    ids = list((await session.scalars(q)).all())
    return [i for i in ids if i != exclude_tg]
