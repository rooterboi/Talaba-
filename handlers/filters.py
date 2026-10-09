from aiogram.filters import BaseFilter

from database.models import Role


class Registered(BaseFilter):
    async def __call__(self, event, user=None) -> bool:
        return user is not None


class IsSuper(BaseFilter):
    async def __call__(self, event, is_super: bool = False) -> bool:
        return is_super


class IsManager(BaseFilter):
    async def __call__(self, event, user=None, is_super: bool = False) -> bool:
        return bool(is_super or (user and user.role in Role.MANAGERS))
