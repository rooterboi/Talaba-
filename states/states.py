from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    role = State(); name = State(); institution = State()


class Pick(StatesGroup):
    faculty = State(); new_faculty = State(); direction = State(); new_direction = State()
    course = State(); group = State(); new_group = State()


class SchAdd(StatesGroup):
    weekday = State(); pair = State(); subject = State(); teacher = State()
    room = State(); ltype = State(); week = State()


class AsgCreate(StatesGroup):
    subject = State(); title = State(); desc = State(); deadline = State(); file = State()


class Submit(StatesGroup):
    waiting = State()


class Grade(StatesGroup):
    value = State()


class LibUpload(StatesGroup):
    scope = State(); subject = State(); category = State(); title = State(); file = State()


class LibSearch(StatesGroup):
    query = State()


class AI(StatesGroup):
    summary = State(); chat = State(); quiz_topic = State(); quiz = State()


class Anon(StatesGroup):
    text = State()


class AnonReply(StatesGroup):
    text = State()


class Ann(StatesGroup):
    content = State(); important = State()


class LeaderCode(StatesGroup):
    code = State()


class AdminSt(StatesGroup):
    inst = State(); role_id = State(); role_val = State(); ban_id = State(); broadcast = State()
