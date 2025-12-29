import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# ========= Налаштування =========
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

_admin_env = os.getenv("ADMIN_CHAT_ID", "").strip()
ADMIN_CHAT_ID = int(_admin_env) if _admin_env.isdigit() else 0

if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN не заданий. Задайте: set "BOT_TOKEN=..."')

CONF_TEXT = (
    "⚠️ Конфіденційно: бренд/локація повідомляються лише після відбору.\n"
    "Просимо не публікувати переписку/умови та не ставити геолокацію."
)

ROLES = [
    "✂️ Перукар",
    "💅 Манікюр/Педикюр",
    "👁️ Брови/Вії",
    "🧾 Адміністратор",
]

role_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=r)] for r in ROLES],
    resize_keyboard=True,
    one_time_keyboard=True,
)

def make_app_id(role_short: str) -> str:
    return f"{role_short}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ========= FSM анкета =========
class Form(StatesGroup):
    agree = State()
    role = State()
    name = State()
    contact = State()
    experience = State()
    skills = State()
    portfolio = State()
    schedule = State()
    ready = State()

# ========= Бот =========
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- Службові команди ---
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    # підготуємо місце під фото
    await state.update_data(portfolio_photos=[])
    await message.answer(
        "Вітаю! Це конфіденційний бот для набору персоналу.\n\n"
        f"{CONF_TEXT}\n\n"
        "Щоб почати анкету, підтвердіть згоду:\n"
        "Напишіть: **Погоджуюсь**",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.agree)

@dp.message(Command("myid"))
async def myid(message: Message):
    await message.answer(f"Ваш chat_id: {message.chat.id}\nВаш user_id: {message.from_user.id}")

@dp.message(Command("setadmin"))
async def setadmin(message: Message):
    global ADMIN_CHAT_ID
    ADMIN_CHAT_ID = message.chat.id
    await message.answer("✅ Адміністратор встановлений. Тепер заявки приходитимуть сюди.")

@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано. Щоб почати знову — /start")

# --- Анкета ---
@dp.message(Form.agree)
async def agree_step(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if "погод" not in text:
        await message.answer("Щоб продовжити, напишіть слово: **Погоджуюсь**", parse_mode="Markdown")
        return

    await message.answer("Дякую ✅ Оберіть позицію:", reply_markup=role_kb)
    await state.set_state(Form.role)

@dp.message(Form.role)
async def role_step(message: Message, state: FSMContext):
    if message.text not in ROLES:
        await message.answer("Оберіть позицію з меню 👇", reply_markup=role_kb)
        return

    await state.update_data(role=message.text)

    await message.answer("Як до вас звертатися? (ім’я або псевдонім)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.name)

@dp.message(Form.name)
async def name_step(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Контакт: номер телефону або Telegram-нік (@...)")
    await state.set_state(Form.contact)

@dp.message(Form.contact)
async def contact_step(message: Message, state: FSMContext):
    await state.update_data(contact=message.text.strip())
    await message.answer("Досвід: 0–6 міс / 6–24 міс / 2–5 років / 5+ (коротко)")
    await state.set_state(Form.experience)

@dp.message(Form.experience)
async def experience_step(message: Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())

    data = await state.get_data()
    role = data.get("role", "")

    if role == "✂️ Перукар":
        q = (
            "5 питань (коротко):\n"
            "1) Що робите найкраще (2–4 пункти)?\n"
            "2) Таймінг: чоловіча коротка / жіноча стрижка?\n"
            "3) Що питаєте перед початком?\n"
            "4) Що робите при запізненні клієнта 10–15 хв?\n"
            "5) Чи готові працювати за стандартами салону (таймінги/сервіс/чистота)?"
        )
    elif role == "💅 Манікюр/Педикюр":
        q = (
            "5 питань (коротко):\n"
            "1) Який тип манікюру: апарат/комбі/класика — і чому?\n"
            "2) Опишіть протокол стерильності (кроки).\n"
            "3) Таймінг: манікюр+покриття / педикюр?\n"
            "4) Як працюєте з тонкою пластиною/відшаруваннями?\n"
            "5) Чи готові до стандартів салону (таймінги/запис/чистота)?"
        )
    elif role == "👁️ Брови/Вії":
        q = (
            "Коротко відповідайте:\n"
            "1) Які процедури робите (брови/вії)?\n"
            "2) Чи робите ламінування (брів/вій)?\n"
            "3) Як підбираєте форму/симетрію?\n"
            "4) Як працюєте з алергіями/протипоказаннями?\n"
            "5) Ваш таймінг на основні процедури?"
        )
    else:  # Адміністратор
        q = (
            "Коротко відповідайте:\n"
            "1) Чи є досвід адміністрування/запису?\n"
            "2) Чи працювали з Instagram Direct/дзвінками?\n"
            "3) Як дієте, якщо клієнт запізнився?\n"
            "4) Як заповнюєте 'вікна' у записі?\n"
            "5) Чи готові працювати за стандартами сервісу?"
        )

    await message.answer(q)
    await state.set_state(Form.skills)

@dp.message(Form.skills)
async def skills_step(message: Message, state: FSMContext):
    await state.update_data(skills=message.text.strip())

    # Обнуляємо список фото на всяк випадок
    await state.update_data(portfolio_photos=[])

    await message.answer(
        "Портфоліо:\n"
        "— надішліть 1–10 фото робіт прямо сюди (можна кілька повідомлень), або\n"
        "— надішліть посилання (Instagram/Drive), або\n"
        "— напишіть 'немає'.\n\n"
        "Коли закінчите з фото — напишіть: **далі**",
        parse_mode="Markdown"
    )
    await state.set_state(Form.portfolio)

# --- ПОРТФОЛІО: фото ---
@dp.message(Form.portfolio, F.photo)
async def portfolio_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("portfolio_photos", [])

    # Беремо найбільший розмір фото
    file_id = message.photo[-1].file_id
    photos.append(file_id)

    await state.update_data(portfolio_photos=photos)

    await message.answer(
        f"📷 Фото додано ({len(photos)}). Можете надіслати ще або напишіть **далі**.",
        parse_mode="Markdown"
    )

# --- ПОРТФОЛІО: текст/посилання/далі ---
@dp.message(Form.portfolio)
async def portfolio_text(message: Message, state: FSMContext):
    txt = message.text.strip()

    # Якщо людина завершила портфоліо
    if txt.lower() in ["далі", "далi", "готово", "next"]:
        await state.update_data(portfolio_text="(фото надіслані в чат)" )
        await message.answer("Який графік вам підходить: повний день / зміни / 3–4 дні?")
        await state.set_state(Form.schedule)
        return

    # Якщо людина пише, що нема
    if txt.lower() in ["немає", "нема", "no"]:
        await state.update_data(portfolio_text="немає", portfolio_photos=[])
        await message.answer("Який графік вам підходить: повний день / зміни / 3–4 дні?")
        await state.set_state(Form.schedule)
        return

    # Якщо це посилання або просто текст
    await state.update_data(portfolio_text=txt)
    await message.answer(
        "Дякую! Якщо хочете — ще надішліть фото робіт.\n"
        "Коли завершите — напишіть **далі**.",
        parse_mode="Markdown"
    )

@dp.message(Form.schedule)
async def schedule_step(message: Message, state: FSMContext):
    await state.update_data(schedule=message.text.strip())
    await message.answer("Коли готові вийти: одразу / 1 тиж / 2 тиж / інше?")
    await state.set_state(Form.ready)

@dp.message(Form.ready)
async def ready_step(message: Message, state: FSMContext):
    await state.update_data(ready=message.text.strip())
    data = await state.get_data()

    role = data.get("role", "")
    role_short = {
        "✂️ Перукар": "HAIR",
        "💅 Манікюр/Педикюр": "NAIL",
        "👁️ Брови/Вії": "BROW",
        "🧾 Адміністратор": "ADMIN",
    }.get(role, "APP")

    app_id = make_app_id(role_short)

    # Повідомлення кандидату
    await message.answer(
        f"✅ Дякую! Анкету прийнято.\n"
        f"Код заявки: {app_id}\n"
        "Ми напишемо вам у цьому чаті, якщо запросимо на пробний.",
        reply_markup=ReplyKeyboardRemove(),
    )

    # Повідомлення адміну (текст)
    portfolio_text = data.get("portfolio_text", "")
    photos = data.get("portfolio_photos", []) or []

    admin_text = (
        f"🆕 Нова заявка: {app_id}\n"
        f"Роль: {role}\n"
        f"Ім'я: {data.get('name','')}\n"
        f"Контакт: {data.get('contact','')}\n"
        f"Досвід: {data.get('experience','')}\n"
        f"Відповіді: {data.get('skills','')}\n"
        f"Портфоліо (текст/посилання): {portfolio_text}\n"
        f"Фото: {len(photos)} шт.\n"
        f"Графік: {data.get('schedule','')}\n"
        f"Готовність: {data.get('ready','')}\n"
    )

    if message.from_user.username:
        admin_text += f"TG: @{message.from_user.username}\n"
    else:
        admin_text += f"TG: (нема) user_id={message.from_user.id}\n"

    # Надсилання адміну
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, admin_text)
        except TelegramBadRequest:
            pass

        # Надіслати фото (якщо є). Підпишемо перше фото кодом заявки.
        if photos:
            for i, fid in enumerate(photos[:10]):  # ліміт 10 фото
                try:
                    caption = f"{app_id} — фото портфоліо ({i+1}/{min(len(photos),10)})" if i == 0 else ""
                    await bot.send_photo(ADMIN_CHAT_ID, fid, caption=caption)
                except TelegramBadRequest:
                    pass

    await state.clear()

# --- якщо люди пишуть без /start ---
@dp.message()
async def fallback(message: Message):
    await message.answer("Щоб подати заявку — натисніть /start")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
