import os
import json
from typing import List, Optional

from aiogram import Bot, Dispatcher, F, Router
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


# =========================
# НАЛАШТУВАННЯ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Не задано BOT_TOKEN у змінних середовища.")

# Якщо ADMIN_CHAT_ID не задано або 0 — можна встановити через /setadmin
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID", "0").strip()

CONFIG_FILE = "config.json"  # локальний файл для збереження admin_chat_id (допоміжно)


def load_admin_chat_id() -> int:
    """Повертає admin_chat_id: спочатку ENV, інакше з config.json, інакше 0."""
    # 1) ENV
    try:
        env_id = int(ADMIN_CHAT_ID_ENV)
    except ValueError:
        env_id = 0
    if env_id:
        return env_id

    # 2) config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            val = int(data.get("admin_chat_id", 0))
            return val
        except Exception:
            return 0

    return 0


def save_admin_chat_id(admin_chat_id: int) -> None:
    """Зберігає admin_chat_id у config.json (на випадок якщо ENV=0)."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"admin_chat_id": admin_chat_id}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =========================
# FSM СТАНИ
# =========================

class Form(StatesGroup):
    age = State()
    consent = State()
    role = State()
    name = State()
    contact = State()
    experience = State()
    qa = State()         # універсальний стан для 5 питань по ролі
    portfolio = State()  # фото робіт / посилання
    schedule = State()
    start_ready = State()


# =========================
# КЛАВІАТУРИ
# =========================

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

YES_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Погоджуюсь")]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# =========================
# ПИТАННЯ ПО РОЛЯХ
# =========================

ROLE_QUESTIONS = {
    "✂️ Перукар": [
        "Що у вас виходить найкраще? (2–4 пункти)",
        "Ваш середній таймінг: чоловіча коротка / жіноча стрижка?",
        "Що ви обов’язково уточнюєте в клієнта перед початком?",
        "Що робите, якщо клієнт запізнився на 10–15 хв?",
        "Чи готові працювати за стандартами (таймінги/сервіс/чистота)?",
    ],
    "💅 Манікюр/педикюр": [
        "Який тип манікюру робите найчастіше (апарат/комбі/класика) і чому?",
        "Опишіть коротко ваш протокол стерильності (кроки).",
        "Ваш середній таймінг: манікюр+покриття / педикюр?",
        "Як працюєте з тонкою пластиною або відшаруваннями?",
        "Чи готові до стандартів салону (таймінги/сервіс/чистота)?",
    ],
    "👁️ Брови/вії": [
        "Які процедури робите (брови/вії)?",
        "Чи робите ламінування (брів/вій)? Якщо так — що саме?",
        "Як підбираєте форму та досягаєте симетрії?",
        "Як працюєте з алергіями/протипоказаннями?",
        "Ваш середній таймінг на основні процедури?",
    ],
    "🧾 Адміністратор": [
        "Чи є досвід адміністрування/запису? Якщо так — який?",
        "Чи працювали з дзвінками та повідомленнями (Instagram/Telegram)?",
        "Що робите, якщо клієнт запізнився?",
        "Як заповнюєте ‘вікна’ в записі?",
        "Чи готові працювати за стандартами сервісу та комунікації?",
    ],
}


# =========================
# БОТ / ROUTER
# =========================

router = Router()
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


# =========================
# КОМАНДИ
# =========================

@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(
        f"Ваш chat_id: {message.chat.id}\nВаш user_id: {message.from_user.id}"
    )


@router.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    admin_chat_id = message.chat.id
    save_admin_chat_id(admin_chat_id)
    await message.answer(
        f"✅ Адміністратор встановлений.\nADMIN_CHAT_ID = {admin_chat_id}"
    )
    # тест
    try:
        await bot.send_message(admin_chat_id, "Тест: адмін-чат підключено ✅")
    except Exception as e:
        await message.answer(f"⚠️ Не зміг надіслати тестове повідомлення: {e}")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано. Щоб почати знову — /start", reply_markup=ReplyKeyboardRemove())


# =========================
# START -> ВІК
# =========================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Вітаю! 👋\nСкільки вам років? (вкажіть цифрами)",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Form.age)


@router.message(Form.age)
async def handle_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    try:
        age = int(text)
    except ValueError:
        await message.answer("Будь ласка, напишіть вік **цифрами** (наприклад: 22).")
        return

    if age < 18:
        await message.answer("Дякую! На жаль, ми розглядаємо кандидатів лише **18+**. 🙏")
        await state.clear()
        return

    await state.update_data(age=age)

    await message.answer(
        "Працюємо **конфіденційно**. Деталі (бренд/локація) — після відбору.\n"
        "Щоб продовжити, натисніть або напишіть: **Погоджуюсь** ✅",
        reply_markup=YES_KB,
    )
    await state.set_state(Form.consent)


@router.message(Form.consent)
async def handle_consent(message: Message, state: FSMContext):
    txt = (message.text or "").strip().lower()
    if "погодж" not in txt:
        await message.answer("Щоб продовжити, напишіть: **Погоджуюсь** ✅", reply_markup=YES_KB)
        return

    await message.answer("Оберіть позицію:", reply_markup=ROLE_KB)
    await state.set_state(Form.role)


# =========================
# АНКЕТА
# =========================

@router.message(Form.role)
async def handle_role(message: Message, state: FSMContext):
    role = (message.text or "").strip()
    if role not in ROLE_QUESTIONS:
        await message.answer("Будь ласка, оберіть позицію кнопкою нижче 👇", reply_markup=ROLE_KB)
        return

    await state.update_data(role=role)
    await message.answer("Ваше ім’я або псевдонім:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.name)


@router.message(Form.name)
async def handle_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Напишіть, будь ласка, ім’я (або псевдонім) ще раз.")
        return
    await state.update_data(name=name)
    await message.answer("Контакт (номер телефону або Telegram-нік):")
    await state.set_state(Form.contact)


@router.message(Form.contact)
async def handle_contact(message: Message, state: FSMContext):
    contact = (message.text or "").strip()
    if len(contact) < 3:
        await message.answer("Напишіть контакт ще раз (телефон або Telegram-нік).")
        return
    await state.update_data(contact=contact)
    await message.answer(
        "Досвід роботи:\n"
        "• 0–6 міс\n• 6–24 міс\n• 2–5 років\n• 5+ років\n\n"
        "Напишіть одним рядком."
    )
    await state.set_state(Form.experience)


@router.message(Form.experience)
async def handle_experience(message: Message, state: FSMContext):
    exp = (message.text or "").strip()
    if len(exp) < 2:
        await message.answer("Напишіть досвід ще раз (коротко).")
        return

    data = await state.get_data()
    role = data.get("role")
    questions = ROLE_QUESTIONS.get(role, [])

    await state.update_data(experience=exp, questions=questions, q_index=0, answers=[])

    # Питаємо перше питання
    if questions:
        await message.answer(f"Питання 1/{len(questions)}:\n{questions[0]}")
        await state.set_state(Form.qa)
    else:
        # на всяк випадок
        await message.answer("Надішліть, будь ласка, 1–10 фото робіт або посилання. Якщо немає — напишіть: немає.\nКоли завершите — напишіть: далі")
        await state.set_state(Form.portfolio)


@router.message(Form.qa)
async def handle_qa(message: Message, state: FSMContext):
    answer = (message.text or "").strip()
    if len(answer) < 1:
        await message.answer("Будь ласка, дайте коротку відповідь текстом.")
        return

    data = await state.get_data()
    questions: List[str] = data.get("questions", [])
    q_index: int = data.get("q_index", 0)
    answers: List[str] = data.get("answers", [])

    answers.append(answer)
    q_index += 1

    await state.update_data(q_index=q_index, answers=answers)

    if q_index < len(questions):
        await message.answer(f"Питання {q_index+1}/{len(questions)}:\n{questions[q_index]}")
        return

    # Переходимо до портфоліо
    await message.answer(
        "Надішліть **1–10 фото робіт** (можна кількома повідомленнями) або **посилання**.\n"
        "Якщо портфоліо немає — напишіть: **немає**\n"
        "Коли завершите — напишіть: **далі**"
    )
    await state.update_data(portfolio_photos=[], portfolio_links=[])
    await state.set_state(Form.portfolio)


@router.message(Form.portfolio, F.photo)
async def handle_portfolio_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: List[str] = data.get("portfolio_photos", [])

    # беремо найбільший розмір
    file_id = message.photo[-1].file_id
    photos.append(file_id)

    await state.update_data(portfolio_photos=photos)
    await message.answer(f"✅ Фото додано ({len(photos)}/10). Надішліть ще або напишіть: далі")


@router.message(Form.portfolio)
async def handle_portfolio_text(message: Message, state: FSMContext):
    txt = (message.text or "").strip()

    if txt.lower() == "далі":
        # йдемо далі
        await message.answer(
            "Який графік вам підходить?\n"
            "Наприклад: повний день / зміни / 3–4 дні / інше"
        )
        await state.set_state(Form.schedule)
        return

    if txt.lower() == "немає":
        await state.update_data(portfolio_photos=[], portfolio_links=[])
        await message.answer(
            "Ок. Який графік вам підходить?\n"
            "Наприклад: повний день / зміни / 3–4 дні / інше"
        )
        await state.set_state(Form.schedule)
        return

    # Якщо це посилання або текст-портфоліо — зберігаємо
    data = await state.get_data()
    links: List[str] = data.get("portfolio_links", [])
    links.append(txt)
    await state.update_data(portfolio_links=links)
    await message.answer("✅ Додано. Можна ще або напишіть: далі")


@router.message(Form.schedule)
async def handle_schedule(message: Message, state: FSMContext):
    schedule = (message.text or "").strip()
    if len(schedule) < 2:
        await message.answer("Напишіть, будь ласка, ваш варіант графіку.")
        return
    await state.update_data(schedule=schedule)
    await message.answer("Коли ви готові вийти/почати? (наприклад: одразу / 1 тиждень / 2 тижні / дата)")
    await state.set_state(Form.start_ready)


@router.message(Form.start_ready)
async def handle_start_ready(message: Message, state: FSMContext):
    start_ready = (message.text or "").strip()
    if len(start_ready) < 2:
        await message.answer("Напишіть, будь ласка, коли готові почати.")
        return

    await state.update_data(start_ready=start_ready)

    data = await state.get_data()
    admin_chat_id = load_admin_chat_id()

    # Формуємо зведення
    age = data.get("age", "—")
    role = data.get("role", "—")
    name = data.get("name", "—")
    contact = data.get("contact", "—")
    experience = data.get("experience", "—")
    schedule = data.get("schedule", "—")
    start_ready = data.get("start_ready", "—")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    links = data.get("portfolio_links", [])
    photos = data.get("portfolio_photos", [])

    username = message.from_user.username or "—"
    user_id = message.from_user.id

    qa_text_lines = []
    for i, q in enumerate(questions):
        a = answers[i] if i < len(answers) else "—"
        qa_text_lines.append(f"{i+1}) {q}\nВідповідь: {a}")

    links_text = "\n".join(links) if links else "—"
    photos_count = len(photos)

    summary = (
        "🆕 Нова анкета\n"
        "====================\n"
        f"Роль: {role}\n"
        f"Ім’я: {name}\n"
        f"Вік: {age}\n"
        f"Контакт: {contact}\n"
        f"Telegram: @{username}\n"
        f"user_id: {user_id}\n"
        f"Досвід: {experience}\n"
        "--------------------\n"
        "Відповіді:\n"
        + ("\n\n".join(qa_text_lines) if qa_text_lines else "—")
        + "\n--------------------\n"
        f"Портфоліо (посилання/текст): {links_text}\n"
        f"Фото робіт: {photos_count}\n"
        f"Графік: {schedule}\n"
        f"Готовність старту: {start_ready}\n"
        "===================="
    )

    # Відповідь кандидату
    await message.answer("Дякую! Повідомлення отримано ✅")

    # Надсилання адміну
    if admin_chat_id == 0:
        await message.answer(
            "⚠️ Адміністратор ще не налаштований.\n"
            "Напишіть /setadmin у чаті з ботом (адміністратором стане цей чат)."
        )
        await state.clear()
        return

    try:
        await bot.send_message(admin_chat_id, summary)

        # якщо є фото — відправляємо медіагрупою (до 10)
        if photos:
            media = [InputMediaPhoto(media=pid) for pid in photos[:10]]
            await bot.send_media_group(admin_chat_id, media)

    except Exception as e:
        # Якщо адмін-чат недоступний — повідомляємо (щоб ви побачили причину)
        await message.answer(f"⚠️ Не вдалося надіслати адміну: {e}\nСпробуйте /setadmin ще раз.")
    finally:
        await state.clear()


# =========================
# ЗАПУСК
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
