import os
import json
import logging
from typing import List

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

# Рекомендується задати в Render. Якщо 0 — можна /setadmin (тимчасово, до перезапуску/деплою)
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID", "0").strip()

CONFIG_FILE = "config.json"  # допоміжно, якщо ENV=0 (на Render може не зберігатися після деплою)


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
    qa = State()
    portfolio = State()
    schedule = State()
    start_ready = State()


# -------------------------
# КЛАВІАТУРИ
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


# -------------------------
# ПИТАННЯ ПО РОЛЯХ
# -------------------------
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
        "Як заповнюєте вікна в записі?",
        "Чи готові працювати за стандартами сервісу та комунікації?",
    ],
}


# -------------------------
# БОТ / DP / ROUTER
# -------------------------
router = Router()
bot = Bot(BOT_TOKEN)  # без parse_mode
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


async def safe_answer(message: Message, text: str, **kwargs):
    try:
        await message.answer(text, **kwargs)
    except Exception as e:
        log.exception("Помилка відправки повідомлення: %s", e)


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

    await safe_answer(
        message,
        "Адміністратор встановлений.\n"
        f"ADMIN_CHAT_ID = {admin_chat_id}\n"
        "Рекомендовано: додайте цей ADMIN_CHAT_ID у Render -> Environment, щоб не збивалося після деплою."
    )
    try:
        await bot.send_message(admin_chat_id, "Тест: адмін-чат підключено ✅")
    except Exception as e:
        await safe_answer(message, f"Не зміг надіслати тестове повідомлення адміну: {e}")


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
    try:
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

    except Exception as e:
        log.exception("Помилка на етапі віку: %s", e)
        await safe_answer(message, "Сталася технічна помилка. Спробуйте ще раз: /start")
        await state.clear()


@router.message(Form.age)
async def handle_age_not_text(message: Message):
    await safe_answer(message, "Напишіть, будь ласка, вік цифрами (наприклад: 22).")


@router.message(Form.consent, F.text)
async def handle_consent(message: Message, state: FSMContext):
    try:
        txt = (message.text or "").strip().lower()
        if "погодж" not in txt:
            await safe_answer(message, "Щоб продовжити, напишіть: Погоджуюсь ✅", reply_markup=YES_KB)
            return

        await safe_answer(message, "Оберіть позицію:", reply_markup=ROLE_KB)
        await state.set_state(Form.role)

    except Exception as e:
        log.exception("Помилка на етапі згоди: %s", e)
        await safe_answer(message, "Сталася технічна помилка. Спробуйте ще раз: /start")
        await state.clear()


# -------------------------
# АНКЕТА
# -------------------------
@router.message(Form.role, F.text)
async def handle_role(message: Message, state: FSMContext):
    role = (message.text or "").strip()
    if role not in ROLE_QUESTIONS:
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
        "Досвід роботи (напишіть одним рядком):\n"
        "0–6 міс / 6–24 міс / 2–5 років / 5+ років"
    )
    await state.set_state(Form.experience)


@router.message(Form.experience, F.text)
async def handle_experience(message: Message, state: FSMContext):
    exp = (message.text or "").strip()
    if len(exp) < 2:
        await safe_answer(message, "Напишіть досвід ще раз (коротко).")
        return

    data = await state.get_data()
    role = data.get("role")
    questions = ROLE_QUESTIONS.get(role, [])

    await state.update_data(experience=exp, questions=questions, q_index=0, answers=[])

    if questions:
        await safe_answer(message, f"Питання 1/{len(questions)}:\n{questions[0]}")
        await state.set_state(Form.qa)
    else:
        await safe_answer(message, "Надішліть 1–10 фото робіт або посилання. Якщо немає — напишіть: немає. Коли завершите — напишіть: далі")
        await state.set_state(Form.portfolio)


@router.message(Form.qa, F.text)
async def handle_qa(message: Message, state: FSMContext):
    answer = (message.text or "").strip()
    if not answer:
        await safe_answer(message, "Дайте коротку відповідь текстом.")
        return

    data = await state.get_data()
    questions: List[str] = data.get("questions", [])
    q_index: int = data.get("q_index", 0)
    answers: List[str] = data.get("answers", [])

    answers.append(answer)
    q_index += 1
    await state.update_data(q_index=q_index, answers=answers)

    if q_index < len(questions):
        await safe_answer(message, f"Питання {q_index+1}/{len(questions)}:\n{questions[q_index]}")
        return

    await safe_answer(
        message,
        "Надішліть 1–10 фото робіт (можна кількома повідомленнями) або посилання.\n"
        "Якщо портфоліо немає — напишіть: немає\n"
        "Коли завершите — напишіть: далі"
    )
    await state.update_data(portfolio_photos=[], portfolio_links=[])
    await state.set_state(Form.portfolio)


@router.message(Form.portfolio, F.photo)
async def handle_portfolio_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: List[str] = data.get("portfolio_photos", [])

    if len(photos) < 10:
        file_id = message.photo[-1].file_id
        photos.append(file_id)

    await state.update_data(portfolio_photos=photos)
    await safe_answer(message, f"Фото додано ({len(photos)}/10). Надішліть ще або напишіть: далі")


@router.message(Form.portfolio, F.text)
async def handle_portfolio_text(message: Message, state: FSMContext):
    txt = (message.text or "").strip()

    if txt.lower() == "далі":
        await safe_answer(message, "Який графік вам підходить? (повний день / зміни / 3–4 дні / інше)")
        await state.set_state(Form.schedule)
        return

    if txt.lower() == "немає":
        await state.update_data(portfolio_photos=[], portfolio_links=[])
        await safe_answer(message, "Ок. Який графік вам підходить? (повний день / зміни / 3–4 дні / інше)")
        await state.set_state(Form.schedule)
        return

    data = await state.get_data()
    links: List[str] = data.get("portfolio_links", [])
    links.append(txt)
    await state.update_data(portfolio_links=links)
    await safe_answer(message, "Додано. Можна ще або напишіть: далі")


@router.message(Form.schedule, F.text)
async def handle_schedule(message: Message, state: FSMContext):
    schedule = (message.text or "").strip()
    if len(schedule) < 2:
        await safe_answer(message, "Напишіть ваш варіант графіку.")
        return

    await state.update_data(schedule=schedule)
    await safe_answer(message, "Коли готові вийти/почати? (одразу / 1 тиж / 2 тиж / дата)")
    await state.set_state(Form.start_ready)


@router.message(Form.start_ready, F.text)
async def handle_start_ready(message: Message, state: FSMContext):
    start_ready = (message.text or "").strip()
    if len(start_ready) < 2:
        await safe_answer(message, "Напишіть, будь ласка, коли готові почати.")
        return

    await state.update_data(start_ready=start_ready)

    data = await state.get_data()
    admin_chat_id = load_admin_chat_id()

    age = data.get("age", "—")
    role = data.get("role", "—")
    name = data.get("name", "—")
    contact = data.get("contact", "—")
    experience = data.get("experience", "—")
    schedule = data.get("schedule", "—")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    links = data.get("portfolio_links", [])
    photos = data.get("portfolio_photos", [])

    username = message.from_user.username or "—"
    user_id = message.from_user.id

    qa_lines = []
    for i, q in enumerate(questions):
        a = answers[i] if i < len(answers) else "—"
        qa_lines.append(f"{i+1}) {q}\nВідповідь: {a}")

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
        await safe_answer(message, f"Не вдалося надіслати адміну. Спробуйте /setadmin ще раз. Помилка: {e}")
    finally:
        await state.clear()


# -------------------------
# ГЛОБАЛЬНИЙ ЛОВЕЦЬ ПОМИЛОК
# -------------------------
@router.errors()
async def on_error(event, exception):
    log.exception("Unhandled error: %s", exception)
    return True


# -------------------------
# ЗАПУСК
# -------------------------
async def main():
    log.info("Bot started polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
