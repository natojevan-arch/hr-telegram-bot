import os
import json
import logging
from typing import List, Dict, Any

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


# -------------------------
# ЛОГИ
# -------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hr_bot")


# -------------------------
# НАЛАШТУВАННЯ
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Не задано BOT_TOKEN у змінних середовища (Render -> Environment).")

ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID", "0").strip()
CONFIG_FILE = "config.json"  # якщо ENV=0 (на Render краще все одно задати ENV)


def load_admin_chat_id() -> int:
    try:
        env_id = int(ADMIN_CHAT_ID_ENV)
    except ValueError:
        env_id = 0
    if env_id:
        return env_id

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return int(data.get("admin_chat_id", 0))
        except Exception:
            return 0

    return 0


def save_admin_chat_id(admin_chat_id: int) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"admin_chat_id": admin_chat_id}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# -------------------------
# FSM СТАНИ
# -------------------------
class Form(StatesGroup):
    age = State()
    consent = State()
    role = State()
    name = State()
    contact = State()
    experience = State()
    qa = State()          # питання 1..5 з кнопками
    portfolio = State()   # фото/посилання
    schedule = State()
    start_ready = State()


# -------------------------
# БОТ / DP / ROUTER
# -------------------------
router = Router()
bot = Bot(BOT_TOKEN)  # без parse_mode — щоб не було помилок форматування
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


async def safe_answer(message: Message, text: str, **kwargs):
    try:
        await message.answer(text, **kwargs)
    except Exception as e:
        log.exception("Помилка відправки повідомлення: %s", e)


def kb_from_options(options: List[str], cols: int = 2) -> ReplyKeyboardMarkup:
    """Робить клавіатуру з варіантів (по 2 кнопки в ряд)"""
    rows = []
    row = []
    for opt in options:
        row.append(KeyboardButton(text=opt))
        if len(row) >= cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


# -------------------------
# КЛАВІАТУРИ (сталі)
# -------------------------
YES_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Погоджуюсь")]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

ROLE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✂️ Перукар")],
        [KeyboardButton(text="💅 Манікюр/педикюр")],
        [KeyboardButton(text="👁️ Брови/вії")],
        [KeyboardButton(text="🧾 Адміністратор")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

EXP_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Без досвіду (стажер)")],
        [KeyboardButton(text="0–6 міс"), KeyboardButton(text="6–24 міс")],
        [KeyboardButton(text="2–5 років"), KeyboardButton(text="5+ років")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

SCHEDULE_KB = kb_from_options(["Повний день", "Зміни", "3–4 дні", "Інше (вписати)"], cols=2)
READY_KB = kb_from_options(["Одразу", "1 тиж", "2 тиж", "Інше (вписати)"], cols=2)


# -------------------------
# ПИТАННЯ З КНОПКАМИ
# Кожен пункт: {"q": "...", "options": [...], "other": True/False}
# Якщо other=True -> додається кнопка "Інше (вписати)"
# -------------------------

def with_other(opts: List[str]) -> List[str]:
    return opts + ["Інше (вписати)"]


QUESTIONS_PRO: Dict[str, List[Dict[str, Any]]] = {
    "✂️ Перукар": [
        {"q": "Що ви робите найкраще? (оберіть 1 основне)", "options": with_other(["Стрижки", "Укладки", "Фарбування", "Чоловічі стрижки", "Жіночі стрижки"])},
        {"q": "Ваш рівень зараз:", "options": with_other(["Початковий", "Впевнений", "Профі/топ"])},
        {"q": "Що уточнюєте перед стрижкою/послугою?", "options": with_other(["Довжина/форма", "Побажання клієнта", "Стан волосся", "Домашній догляд", "Все разом"])},
        {"q": "Як дієте, якщо клієнт запізнився 10–15 хв?", "options": with_other(["Скорочую послугу", "Переношу запис", "Домовляюсь і працюю швидше", "За правилами салону"])},
        {"q": "Готові працювати за стандартами сервісу і чистоти?", "options": ["Так", "Ні", "Потрібно обговорити"]},
    ],
    "💅 Манікюр/педикюр": [
        {"q": "Який напрям вам ближчий?", "options": with_other(["Манікюр", "Педикюр", "І те, і те"])},
        {"q": "Яка техніка у вас основна?", "options": with_other(["Апаратний", "Комбінований", "Класичний"])},
        {"q": "Стерильність/гігієна:", "options": with_other(["Знаю і дотримуюсь", "Знаю частково", "Потрібно навчити з нуля"])},
        {"q": "Ваш рівень зараз:", "options": with_other(["Початковий", "Впевнений", "Профі/топ"])},
        {"q": "Готові працювати за стандартами сервісу і чистоти?", "options": ["Так", "Ні", "Потрібно обговорити"]},
    ],
    "👁️ Брови/вії": [
        {"q": "Що робите?", "options": with_other(["Брови", "Вії", "Брови і вії"])},
        {"q": "Ламінування:", "options": with_other(["Так, роблю", "Ні, але хочу навчитися", "Ні, не планую"])},
        {"q": "Фарбування:", "options": with_other(["Так", "Ні", "Хочу навчитися"])},
        {"q": "Ваш рівень зараз:", "options": with_other(["Початковий", "Впевнений", "Профі/топ"])},
        {"q": "Готові працювати за стандартами сервісу і чистоти?", "options": ["Так", "Ні", "Потрібно обговорити"]},
    ],
    "🧾 Адміністратор": [
        {"q": "Досвід роботи з клієнтами:", "options": with_other(["Є (салон/сфера послуг)", "Є (інша сфера)", "Немає, але хочу навчитися"])},
        {"q": "Робота з записом:", "options": with_other(["Вмію вести записи", "Вмію частково", "Потрібно навчити"])},
        {"q": "Комунікація:", "options": with_other(["Впевнено спілкуюсь", "Нормально", "Хвилююсь, але вчитимусь"])},
        {"q": "Стрес/конфлікти:", "options": with_other(["Спокійно вирішую", "Потрібні скрипти", "Поки важко"])},
        {"q": "Готові до дисципліни і стандартів сервісу?", "options": ["Так", "Ні", "Потрібно обговорити"]},
    ],
}

QUESTIONS_TRAINEE: Dict[str, List[Dict[str, Any]]] = {
    "✂️ Перукар": [
        {"q": "Ви хочете вчитись з нуля чи вже були курси?", "options": with_other(["З нуля", "Були курси", "Є мінімальна практика"])},
        {"q": "Готові пройти навчання/курси?", "options": ["Так", "Ні", "Потрібно обговорити"]},
        {"q": "Скільки часу готові виділяти на навчання щотижня?", "options": with_other(["2–4 години", "5–8 годин", "9+ годин"])},
        {"q": "Що для вас важливо в роботі?", "options": with_other(["Якість", "Швидкість", "Сервіс", "Дисципліна", "Все разом"])},
        {"q": "Коли готові стартувати стажування?", "options": with_other(["Одразу", "1 тиж", "2 тиж"])},
    ],
    "💅 Манікюр/педикюр": [
        {"q": "Ви хочете вчитись з нуля чи вже були курси?", "options": with_other(["З нуля", "Були курси", "Є мінімальна практика"])},
        {"q": "Готові пройти навчання/курси?", "options": ["Так", "Ні", "Потрібно обговорити"]},
        {"q": "Що цікавіше?", "options": with_other(["Манікюр", "Педикюр", "І те, і те"])},
        {"q": "Готові вчити гігієну/стерильність за стандартом?", "options": ["Так", "Ні", "Потрібно обговорити"]},
        {"q": "Коли готові стартувати стажування?", "options": with_other(["Одразу", "1 тиж", "2 тиж"])},
    ],
    "👁️ Брови/вії": [
        {"q": "Ви хочете вчитись з нуля чи вже були курси?", "options": with_other(["З нуля", "Були курси", "Є мінімальна практика"])},
        {"q": "Що цікавіше?", "options": with_other(["Брови", "Вії", "Брови і вії"])},
        {"q": "Готові пройти навчання/курси?", "options": ["Так", "Ні", "Потрібно обговорити"]},
        {"q": "Готові працювати акуратно і за правилами безпеки?", "options": ["Так", "Ні", "Потрібно обговорити"]},
        {"q": "Коли готові стартувати стажування?", "options": with_other(["Одразу", "1 тиж", "2 тиж"])},
    ],
    "🧾 Адміністратор": [
        {"q": "Досвід роботи з людьми:", "options": with_other(["Є (сфера послуг)", "Є (інша сфера)", "Немає, але хочу навчитися"])},
        {"q": "Готові вчитись: запис, повідомлення, дисципліна?", "options": ["Так", "Ні", "Потрібно обговорити"]},
        {"q": "Чи впевнено користуєтесь телефоном/компʼютером?", "options": ["Так", "Ні", "Потрібно пояснити"]},
        {"q": "Комунікація:", "options": with_other(["Впевнено", "Нормально", "Хвилююсь, але вчитимусь"])},
        {"q": "Коли готові стартувати стажування?", "options": with_other(["Одразу", "1 тиж", "2 тиж"])},
    ],
}


# -------------------------
# КОМАНДИ
# -------------------------
@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await safe_answer(message, f"Ваш chat_id: {message.chat.id}\nВаш user_id: {message.from_user.id}")


@router.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    admin_chat_id = message.chat.id
    save_admin_chat_id(admin_chat_id)
    await safe_answer(message, f"Адміністратор встановлений. ADMIN_CHAT_ID = {admin_chat_id}")
    try:
        await bot.send_message(admin_chat_id, "Тест: адмін-чат підключено ✅")
    except Exception as e:
        await safe_answer(message, f"Не зміг надіслати тест адміну: {e}")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await safe_answer(message, "Скасовано. Щоб почати знову — /start", reply_markup=ReplyKeyboardRemove())


# -------------------------
# START -> ВІК
# -------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await safe_answer(message, "Вітаю! Скільки вам років? (вкажіть цифрами)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.age)


@router.message(Form.age, F.text)
async def handle_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    try:
        age = int(text)
    except ValueError:
        await safe_answer(message, "Будь ласка, напишіть вік цифрами (наприклад: 22).")
        return

    if age < 18:
        await safe_answer(message, "Дякую! Ми розглядаємо кандидатів лише 18+.")
        await state.clear()
        return

    await state.update_data(age=age)

    await safe_answer(
        message,
        "Працюємо конфіденційно. Деталі (бренд/локація) — після відбору.\n"
        "Щоб продовжити, натисніть або напишіть: Погоджуюсь ✅",
        reply_markup=YES_KB,
    )
    await state.set_state(Form.consent)


@router.message(Form.consent, F.text)
async def handle_consent(message: Message, state: FSMContext):
    txt = (message.text or "").strip().lower()
    if "погодж" not in txt:
        await safe_answer(message, "Щоб продовжити, натисніть або напишіть: Погоджуюсь ✅", reply_markup=YES_KB)
        return

    await safe_answer(message, "Оберіть позицію:", reply_markup=ROLE_KB)
    await state.set_state(Form.role)


@router.message(Form.role, F.text)
async def handle_role(message: Message, state: FSMContext):
    role = (message.text or "").strip()
    if role not in ROLE_KB.model_dump()["keyboard"][0][0].keys() and role not in ["✂️ Перукар", "💅 Манікюр/педикюр", "👁️ Брови/вії", "🧾 Адміністратор"]:
        # страховка
        if role not in ["✂️ Перукар", "💅 Манікюр/педикюр", "👁️ Брови/вії", "🧾 Адміністратор"]:
            await safe_answer(message, "Оберіть позицію кнопкою нижче:", reply_markup=ROLE_KB)
            return

    if role not in ["✂️ Перукар", "💅 Манікюр/педикюр", "👁️ Брови/вії", "🧾 Адміністратор"]:
        await safe_answer(message, "Оберіть позицію кнопкою нижче:", reply_markup=ROLE_KB)
        return

    await state.update_data(role=role)
    await safe_answer(message, "Ваше ім’я або псевдонім:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.name)


@router.message(Form.name, F.text)
async def handle_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await safe_answer(message, "Напишіть ім’я (або псевдонім) ще раз.")
        return
    await state.update_data(name=name)
    await safe_answer(message, "Контакт (номер телефону або Telegram-нік):")
    await state.set_state(Form.contact)


@router.message(Form.contact, F.text)
async def handle_contact(message: Message, state: FSMContext):
    contact = (message.text or "").strip()
    if len(contact) < 3:
        await safe_answer(message, "Напишіть контакт ще раз (телефон або Telegram-нік).")
        return

    await state.update_data(contact=contact)

    await safe_answer(
        message,
        "Досвід роботи: оберіть варіант кнопкою нижче (або напишіть текстом).",
        reply_markup=EXP_KB
    )
    await state.set_state(Form.experience)


@router.message(Form.experience, F.text)
async def handle_experience(message: Message, state: FSMContext):
    exp_raw = (message.text or "").strip()

    # приймаємо навіть "0"
    exp_map = {
        "0": "0–6 міс",
        "0-6": "0–6 міс",
        "0–6": "0–6 міс",
        "0 6": "0–6 міс",
        "6-24": "6–24 міс",
        "6–24": "6–24 міс",
    }
    exp = exp_map.get(exp_raw.lower(), exp_raw)

    if len(exp) < 1:
        await safe_answer(message, "Оберіть досвід кнопкою або напишіть текстом.")
        return

    role = (await state.get_data()).get("role")
    exp_low = exp.lower()
    is_trainee = ("без досвіду" in exp_low) or ("стаж" in exp_low)

    qlist = (QUESTIONS_TRAINEE if is_trainee else QUESTIONS_PRO).get(role, [])

    await state.update_data(
        experience=exp,
        is_trainee=is_trainee,
        qlist=qlist,
        q_index=0,
        answers=[],
        waiting_other=False
    )

    await safe_answer(message, "Дякую! Переходимо до коротких питань.", reply_markup=ReplyKeyboardRemove())

    if not qlist:
        await safe_answer(message, "Фото робіт (якщо є) або посилання. Якщо немає — напишіть: немає. Коли завершите — напишіть: далі")
        await state.set_state(Form.portfolio)
        return

    # Питання 1
    q0 = qlist[0]
    await safe_answer(message, f"Питання 1/{len(qlist)}:\n{q0['q']}", reply_markup=kb_from_options(q0["options"]))
    await state.set_state(Form.qa)


@router.message(Form.qa, F.text)
async def handle_qa(message: Message, state: FSMContext):
    data = await state.get_data()
    qlist: List[Dict[str, Any]] = data.get("qlist", [])
    q_index: int = data.get("q_index", 0)
    answers: List[str] = data.get("answers", [])
    waiting_other: bool = data.get("waiting_other", False)

    text = (message.text or "").strip()

    if not qlist or q_index >= len(qlist):
        # страховка
        await safe_answer(message, "Йдемо далі.")
        await state.set_state(Form.portfolio)
        return

    # якщо до цього натиснули "Інше (вписати)" — тепер чекаємо довільний текст
    if waiting_other:
        if len(text) < 2:
            await safe_answer(message, "Напишіть, будь ласка, відповідь текстом одним повідомленням.")
            return
        answers.append(text)
        await state.update_data(answers=answers, waiting_other=False)
    else:
        # якщо натиснули "Інше (вписати)"
        if text == "Інше (вписати)":
            await state.update_data(waiting_other=True)
            await safe_answer(message, "Напишіть вашу відповідь текстом одним повідомленням:", reply_markup=ReplyKeyboardRemove())
            return

        # звичайна відповідь кнопкою
        answers.append(text)
        await state.update_data(answers=answers)

    # наступне питання
    q_index += 1
    await state.update_data(q_index=q_index)

    if q_index < len(qlist):
        qn = qlist[q_index]
        await safe_answer(message, f"Питання {q_index+1}/{len(qlist)}:\n{qn['q']}", reply_markup=kb_from_options(qn["options"]))
        return

    # кінець питань -> портфоліо
    await safe_answer(
        message,
        "Дякую! Тепер портфоліо.\n"
        "Надішліть 1–10 фото робіт (можна кількома повідомленнями) або посилання.\n"
        "Якщо немає — напишіть: немає\n"
        "Коли завершите — напишіть: далі",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.update_data(portfolio_photos=[], portfolio_links=[])
    await state.set_state(Form.portfolio)


@router.message(Form.portfolio, F.photo)
async def handle_portfolio_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: List[str] = data.get("portfolio_photos", [])

    if len(photos) < 10:
        photos.append(message.photo[-1].file_id)
        await state.update_data(portfolio_photos=photos)

    await safe_answer(message, f"Фото додано ({len(photos)}/10). Надішліть ще або напишіть: далі")


@router.message(Form.portfolio, F.text)
async def handle_portfolio_text(message: Message, state: FSMContext):
    txt = (message.text or "").strip()

    if txt.lower() == "немає":
        await state.update_data(portfolio_photos=[], portfolio_links=[])
        await safe_answer(message, "Ок. Який графік вам підходить?", reply_markup=SCHEDULE_KB)
        await state.set_state(Form.schedule)
        return

    if txt.lower() == "далі":
        await safe_answer(message, "Який графік вам підходить?", reply_markup=SCHEDULE_KB)
        await state.set_state(Form.schedule)
        return

    # інакше це посилання/текст
    data = await state.get_data()
    links: List[str] = data.get("portfolio_links", [])
    links.append(txt)
    await state.update_data(portfolio_links=links)
    await safe_answer(message, "Додано. Можна ще або напишіть: далі")


@router.message(Form.schedule, F.text)
async def handle_schedule(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if txt == "Інше (вписати)":
        await safe_answer(message, "Напишіть ваш графік одним повідомленням:", reply_markup=ReplyKeyboardRemove())
        await state.update_data(waiting_schedule_other=True)
        return

    data = await state.get_data()
    if data.get("waiting_schedule_other"):
        if len(txt) < 2:
            await safe_answer(message, "Напишіть графік ще раз (коротко).")
            return
        await state.update_data(waiting_schedule_other=False, schedule=txt)
    else:
        await state.update_data(schedule=txt)

    await safe_answer(message, "Коли готові вийти/почати?", reply_markup=READY_KB)
    await state.set_state(Form.start_ready)


@router.message(Form.start_ready, F.text)
async def handle_start_ready(message: Message, state: FSMContext):
    txt = (message.text or "").strip()

    if txt == "Інше (вписати)":
        await safe_answer(message, "Напишіть, коли готові почати (дата/період):", reply_markup=ReplyKeyboardRemove())
        await state.update_data(waiting_ready_other=True)
        return

    data = await state.get_data()
    if data.get("waiting_ready_other"):
        if len(txt) < 2:
            await safe_answer(message, "Напишіть ще раз (коротко).")
            return
        await state.update_data(waiting_ready_other=False, start_ready=txt)
    else:
        await state.update_data(start_ready=txt)

    data = await state.get_data()
    admin_chat_id = load_admin_chat_id()

    role = data.get("role", "—")
    name = data.get("name", "—")
    age = data.get("age", "—")
    contact = data.get("contact", "—")
    experience = data.get("experience", "—")
    schedule = data.get("schedule", "—")
    start_ready = data.get("start_ready", "—")
    qlist = data.get("qlist", [])
    answers = data.get("answers", [])
    links = data.get("portfolio_links", [])
    photos = data.get("portfolio_photos", [])

    username = message.from_user.username or "—"
    user_id = message.from_user.id

    qa_lines = []
    for i, q in enumerate(qlist):
        qtext = q.get("q", "—")
        atext = answers[i] if i < len(answers) else "—"
        qa_lines.append(f"{i+1}) {qtext}\nВідповідь: {atext}")

    links_text = "\n".join(links) if links else "—"

    summary = (
        "Нова анкета\n"
        "--------------------\n"
        f"Роль: {role}\n"
        f"Ім’я: {name}\n"
        f"Вік: {age}\n"
        f"Контакт: {contact}\n"
        f"Telegram: @{username}\n"
        f"user_id: {user_id}\n"
        f"Досвід: {experience}\n"
        "--------------------\n"
        "Відповіді:\n"
        + ("\n\n".join(qa_lines) if qa_lines else "—")
        + "\n--------------------\n"
        f"Портфоліо (посилання/текст): {links_text}\n"
        f"Фото робіт: {len(photos)}\n"
        f"Графік: {schedule}\n"
        f"Готовність старту: {start_ready}\n"
        "--------------------"
    )

    await safe_answer(message, "Дякую! Анкету прийнято ✅", reply_markup=ReplyKeyboardRemove())

    if admin_chat_id == 0:
        await safe_answer(message, "Адміністратор не налаштований. Напишіть /setadmin у чаті з ботом.")
        await state.clear()
        return

    try:
        await bot.send_message(admin_chat_id, summary)

        if len(photos) == 1:
            await bot.send_photo(admin_chat_id, photos[0])
        elif len(photos) >= 2:
            media = [InputMediaPhoto(media=pid) for pid in photos[:10]]
            await bot.send_media_group(admin_chat_id, media)

    except Exception as e:
        log.exception("Помилка відправки адміну: %s", e)
        await safe_answer(message, f"Не вдалося надіслати адміну. Спробуйте /setadmin. Помилка: {e}")
    finally:
        await state.clear()


@router.errors()
async def on_error(event, exception):
    log.exception("Unhandled error: %s", exception)
    return True


async def main():
    log.info("Bot started polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
