import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    Update,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openrouter/free").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fitmyn-webhook").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
DEFAULT_MORNING_TIME = os.getenv("DEFAULT_MORNING_TIME", "08:00").strip() or "08:00"
DEFAULT_EVENING_TIME = os.getenv("DEFAULT_EVENING_TIME", "20:30").strip() or "20:30"

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitmyn")

router = Router()
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

bot = Bot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL) if OPENAI_API_KEY else None
pool: asyncpg.Pool | None = None

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🥗 Питание"), KeyboardButton(text="🏋️ Тренировка")],
        [KeyboardButton(text="📊 Отчёт"), KeyboardButton(text="📅 Неделя")],
        [KeyboardButton(text="💬 Спросить агента"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="⏰ Расписание")],
    ],
    resize_keyboard=True,
)

CONSENT_KB = InlineKeyboardMarkup(
    inline_keyboard=[[
        InlineKeyboardButton(text="Согласен", callback_data="consent_yes"),
        InlineKeyboardButton(text="Не согласен", callback_data="consent_no"),
    ]]
)

SYSTEM_PROMPT = """
Ты — персональный ИИ-ассистент по питанию, тренировкам, восстановлению и устойчивым привычкам.

Работай как помощник по питанию, персональный тренер, трекер прогресса и коуч по привычкам.

Правила безопасности:
- Не ставь диагнозы и не заменяй врача.
- Не назначай лекарства, БАДы, гормоны или лечение.
- Не рекомендуй экстремальные диеты, длительное голодание, обезвоживание, очищения или опасное снижение веса.
- Не стыди человека за еду, вес, внешность или пропущенные тренировки.
- При боли в груди, выраженной одышке, обмороке, сильной необычной боли и других потенциально опасных симптомах
  рекомендуй прекратить тренировку и обратиться за медицинской помощью.
- При беременности, расстройствах пищевого поведения, серьёзных травмах, хронических заболеваниях или значимых лекарствах
  действуй осторожно и при необходимости рекомендуй консультацию профильного специалиста.
- Не создавай ложную точность для калорий и КБЖУ.
- Для тренировок учитывай уровень, ограничения, оборудование, восстановление и постепенную прогрессию.
- Для питания учитывай предпочтения, доступность продуктов, поездки, домашнюю еду и рестораны.
- Не раскрывай данные других пользователей.
- Для командной механики не соревнуй людей по весу, калориям или внешности.

Стиль ответа для Telegram:
- Пиши простым живым русским языком.
- Не используй Markdown-разметку: никаких **, ##, ``` и таблиц.
- Не используй HTML-теги, включая <br>.
- Не используй таблицы и вертикальные черты |.
- Делай короткие абзацы и списки с символом •.
- Для нумерации используй обычные 1., 2., 3.
- Заголовок — одна короткая строка с подходящим эмодзи.
- Не делай длинное полотно текста.
- Не повторяй данные профиля без необходимости.
- Для тренировки используй блоки: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.
- Для питания используй блоки: Главная задача, Завтрак, Обед, Ужин, Перекус, Фокус дня.
- Ответ обычно должен помещаться примерно в 900–1400 символов.
- Выводи только готовый текст для пользователя, без пояснений про форматирование.
"""

class Onboarding(StatesGroup):
    name = State()
    age = State()
    sex = State()
    height = State()
    weight = State()
    goal = State()
    activity = State()
    frequency = State()
    equipment = State()
    restrictions = State()
    food = State()
    sleep = State()

class Checkin(StatesGroup):
    waiting_report = State()

def now_utc():
    return datetime.now(timezone.utc)

async def db_execute(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        await conn.execute(sql, *params)

async def db_fetchrow(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *params)

async def db_fetch(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)

async def init_db():
    global pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL is missing; service starts in configuration mode")
        return

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            consent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            last_seen TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            telegram_id BIGINT PRIMARY KEY,
            name TEXT,
            age TEXT,
            sex TEXT,
            height TEXT,
            weight TEXT,
            goal TEXT,
            activity TEXT,
            frequency TEXT,
            equipment TEXT,
            restrictions TEXT,
            food TEXT,
            sleep TEXT,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            report TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_settings (
            telegram_id BIGINT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
            morning_time TEXT NOT NULL DEFAULT '08:00',
            evening_time TEXT NOT NULL DEFAULT '20:30',
            workout_days TEXT NOT NULL DEFAULT '0,2,4',
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            local_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            UNIQUE(telegram_id, kind, local_date)
        );
        """)

async def touch_user(message: Message):
    await db_execute(
        """
        INSERT INTO users(telegram_id, username, first_name, created_at, last_seen)
        VALUES ($1, $2, $3, $4, $4)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=EXCLUDED.username,
            first_name=EXCLUDED.first_name,
            last_seen=EXCLUDED.last_seen
        """,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        now_utc(),
    )

async def has_consent(user_id: int) -> bool:
    row = await db_fetchrow("SELECT consent FROM users WHERE telegram_id=$1", user_id)
    return bool(row and row["consent"])

async def get_profile(user_id: int):
    return await db_fetchrow("SELECT * FROM profiles WHERE telegram_id=$1", user_id)

def profile_to_text(p) -> str:
    if not p:
        return "Профиль ещё не заполнен."
    return f"""
Имя: {p['name']}
Возраст: {p['age']}
Пол: {p['sex']}
Рост: {p['height']}
Вес: {p['weight']}
Цель: {p['goal']}
Активность: {p['activity']}
Тренировок в неделю: {p['frequency']}
Где тренируется / оборудование: {p['equipment']}
Ограничения и травмы: {p['restrictions']}
Питание и предпочтения: {p['food']}
Сон: {p['sleep']}
""".strip()



def workout_days_from_frequency(value: str | None) -> str:
    """Подбирает равномерные тренировочные дни из ответа анкеты."""
    match = re.search(r"\d+", value or "")
    n = int(match.group()) if match else 3
    if n <= 1:
        days = [2]  # Ср
    elif n == 2:
        days = [1, 4]  # Вт, Пт
    elif n == 3:
        days = [0, 2, 4]  # Пн, Ср, Пт
    elif n == 4:
        days = [0, 1, 3, 5]  # Пн, Вт, Чт, Сб
    elif n == 5:
        days = [0, 1, 2, 4, 5]  # Пн, Вт, Ср, Пт, Сб
    elif n == 6:
        days = [0, 1, 2, 3, 4, 5]
    else:
        days = [0, 1, 2, 3, 4, 5, 6]
    return ",".join(str(x) for x in days)


def workout_days_label(value: str) -> str:
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item.isdigit() and 0 <= int(item) <= 6:
            result.append(labels[int(item)])
    return ", ".join(result) or "не выбраны"


def timezone_label(value: str) -> str:
    names = {
        "Europe/Moscow": "Москва",
        "Europe/London": "Лондон",
        "Asia/Dubai": "Дубай",
        "Asia/Novosibirsk": "Новосибирск",
        "Asia/Almaty": "Алматы",
        "Asia/Tbilisi": "Тбилиси",
    }
    return names.get(value, value)


async def ensure_notification_settings(user_id: int):
    row = await db_fetchrow(
        "SELECT * FROM notification_settings WHERE telegram_id=$1", user_id
    )
    if row:
        return row
    profile = await get_profile(user_id)
    days = workout_days_from_frequency(profile["frequency"] if profile else None)
    await db_execute(
        """
        INSERT INTO notification_settings(
            telegram_id, enabled, timezone, morning_time, evening_time,
            workout_days, updated_at
        ) VALUES ($1, TRUE, $2, $3, $4, $5, $6)
        ON CONFLICT(telegram_id) DO NOTHING
        """,
        user_id, DEFAULT_TIMEZONE, DEFAULT_MORNING_TIME, DEFAULT_EVENING_TIME,
        days, now_utc()
    )
    return await db_fetchrow(
        "SELECT * FROM notification_settings WHERE telegram_id=$1", user_id
    )


def schedule_keyboard(settings) -> InlineKeyboardMarkup:
    toggle_text = "🔕 Выключить авто" if settings["enabled"] else "🔔 Включить авто"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="notify_toggle")],
        [
            InlineKeyboardButton(text="Утро 07:00", callback_data="notify_m_0700"),
            InlineKeyboardButton(text="08:00", callback_data="notify_m_0800"),
            InlineKeyboardButton(text="09:00", callback_data="notify_m_0900"),
            InlineKeyboardButton(text="10:00", callback_data="notify_m_1000"),
        ],
        [
            InlineKeyboardButton(text="Вечер 19:00", callback_data="notify_e_1900"),
            InlineKeyboardButton(text="20:00", callback_data="notify_e_2000"),
            InlineKeyboardButton(text="21:00", callback_data="notify_e_2100"),
            InlineKeyboardButton(text="22:00", callback_data="notify_e_2200"),
        ],
        [
            InlineKeyboardButton(text="Москва", callback_data="notify_tz_moscow"),
            InlineKeyboardButton(text="Лондон", callback_data="notify_tz_london"),
        ],
        [
            InlineKeyboardButton(text="Дубай", callback_data="notify_tz_dubai"),
            InlineKeyboardButton(text="Новосибирск", callback_data="notify_tz_nsk"),
        ],
        [InlineKeyboardButton(text="♻️ Дни тренировок по анкете", callback_data="notify_days_auto")],
    ])


def schedule_text(settings) -> str:
    status = "включены" if settings["enabled"] else "выключены"
    return (
        "⏰ Автоматическое сопровождение\n\n"
        f"Статус: {status}\n"
        f"Часовой пояс: {timezone_label(settings['timezone'])}\n"
        f"Утренний план: {settings['morning_time']}\n"
        f"Вечерний отчёт: {settings['evening_time']}\n"
        f"Тренировочные дни: {workout_days_label(settings['workout_days'])}\n\n"
        "Утром я сам пришлю питание и тренировку или восстановление. "
        "Вечером напомню про короткий отчёт."
    )


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":", 1)
        return int(h), int(m)
    except Exception:
        return 8, 0


def is_due(local_now: datetime, hhmm: str, window_minutes: int = 90) -> bool:
    hour, minute = parse_hhmm(hhmm)
    scheduled = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return scheduled <= local_now < scheduled + timedelta(minutes=window_minutes)


async def claim_notification(user_id: int, kind: str, local_date):
    return await db_fetchrow(
        """
        INSERT INTO notification_log(telegram_id, kind, local_date, created_at)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT(telegram_id, kind, local_date) DO NOTHING
        RETURNING id
        """,
        user_id, kind, local_date, now_utc()
    )


async def release_notification(log_id: int):
    await db_execute("DELETE FROM notification_log WHERE id=$1", log_id)


async def build_daily_auto_plan(user_id: int, workout_day: bool) -> tuple[str, str]:
    task = "Сегодня тренировочный день." if workout_day else "Сегодня день восстановления без силовой тренировки."
    answer = await ask_ai(
        user_id,
        f"Составь автоматический план на сегодня. {task}",
        f"""
Сформируй два коротких сообщения для Telegram на сегодня с учетом профиля пользователя.
{task}

Сначала питание, потом тренировку или восстановление.
Между сообщениями поставь отдельной строкой ТОЧНО такой маркер:
===FITMYN_SPLIT===

Первая часть:
🥗 Питание на сегодня
Главная задача
Завтрак
Обед
Ужин
Перекус
Фокус дня

Вторая часть:
{'🏋️ Тренировка на сегодня: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.' if workout_day else '🌿 Восстановление сегодня: активность, мобильность, шаги, сон и один совет.'}

Каждая часть должна быть компактной. Без Markdown, HTML, таблиц и <br>.
"""
    )
    parts = [p.strip() for p in answer.split("===FITMYN_SPLIT===", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    # Если модель не поставила маркер, не теряем ответ.
    return answer, (
        "🏋️ Тренировка сегодня\n\nОткрой кнопку «🏋️ Тренировка», и я соберу план под тебя."
        if workout_day else
        "🌿 Сегодня восстановление\n\nЛёгкая активность, прогулка и качественный сон — достаточно."
    )


async def send_morning_plan(user_id: int, local_date, workout_day: bool):
    if not bot:
        return False
    claim = await claim_notification(user_id, "morning", local_date)
    if not claim:
        return False
    log_id = claim["id"]
    try:
        food, activity = await build_daily_auto_plan(user_id, workout_day)
        await bot.send_message(user_id, food, reply_markup=MAIN_KB)
        await asyncio.sleep(0.3)
        await bot.send_message(user_id, activity, reply_markup=MAIN_KB)
        return True
    except Exception:
        logger.exception("Failed to send morning plan to %s", user_id)
        await release_notification(log_id)
        return False


async def send_evening_checkin(user_id: int, local_date):
    if not bot:
        return False
    claim = await claim_notification(user_id, "evening", local_date)
    if not claim:
        return False
    log_id = claim["id"]
    try:
        await bot.send_message(
            user_id,
            "📊 Как прошёл день?\n\n"
            "Нажми «📊 Отчёт» и коротко отметь питание, тренировку или активность, сон, энергию и самочувствие.",
            reply_markup=MAIN_KB,
        )
        return True
    except Exception:
        logger.exception("Failed to send evening checkin to %s", user_id)
        await release_notification(log_id)
        return False


async def run_due_notifications() -> dict:
    if not pool or not bot:
        return {"checked": 0, "morning_sent": 0, "evening_sent": 0}

    users = await db_fetch(
        """
        SELECT u.telegram_id
        FROM users u
        JOIN profiles p ON p.telegram_id=u.telegram_id
        WHERE u.consent=TRUE
        ORDER BY u.telegram_id
        """
    )
    stats = {"checked": len(users), "morning_sent": 0, "evening_sent": 0}
    utc_now = now_utc()

    for row in users:
        uid = row["telegram_id"]
        settings = await ensure_notification_settings(uid)
        if not settings or not settings["enabled"]:
            continue
        try:
            tz = ZoneInfo(settings["timezone"])
        except ZoneInfoNotFoundError:
            tz = ZoneInfo(DEFAULT_TIMEZONE)
        local_now = utc_now.astimezone(tz)
        local_date = local_now.date()

        if is_due(local_now, settings["morning_time"]):
            workout_days = {
                int(x) for x in settings["workout_days"].split(",")
                if x.strip().isdigit()
            }
            if await send_morning_plan(uid, local_date, local_now.weekday() in workout_days):
                stats["morning_sent"] += 1

        if is_due(local_now, settings["evening_time"]):
            if await send_evening_checkin(uid, local_date):
                stats["evening_sent"] += 1

    return stats


async def notification_loop():
    """Фоновая подстраховка, пока Render-сервис не спит."""
    while True:
        try:
            await run_due_notifications()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification loop error")
        await asyncio.sleep(60)

async def recent_history(user_id: int, limit: int = 12):
    rows = await db_fetch(
        """
        SELECT role, content
        FROM messages
        WHERE telegram_id=$1
        ORDER BY id DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return list(reversed(rows))

async def save_message(user_id: int, role: str, content: str):
    await db_execute(
        "INSERT INTO messages(telegram_id, role, content, created_at) VALUES ($1,$2,$3,$4)",
        user_id, role, content, now_utc()
    )

def clean_telegram_text(text: str) -> str:
    """Убирает типичные артефакты Markdown/HTML из ответов моделей."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("**", "").replace("__", "").replace("```", "")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*\|[ \t]*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*", " • ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

async def ask_ai(user_id: int, user_text: str, extra_instruction: str = "") -> str:
    if not client:
        return "ИИ пока не подключён. Администратору нужно добавить OPENAI_API_KEY."

    profile = await get_profile(user_id)
    history = await recent_history(user_id)

    history_text = "\n".join(
        f"{row['role'].upper()}: {row['content']}" for row in history
    )

    instructions = SYSTEM_PROMPT
    if extra_instruction:
        instructions += "\n\nТекущая задача:\n" + extra_instruction

    prompt = f"""
ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{profile_to_text(profile)}

ПОСЛЕДНИЙ КОНТЕКСТ:
{history_text or "Нет истории."}

НОВОЕ СООБЩЕНИЕ:
{user_text}
""".strip()

    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=instructions,
        input=prompt,
    )
    answer = clean_telegram_text((response.output_text or "").strip()) or "Не получилось сформировать ответ."
    await save_message(user_id, "user", user_text)
    await save_message(user_id, "assistant", answer)
    return answer

async def ensure_ready(message: Message) -> bool:
    if not pool:
        await message.answer("База данных пока не подключена. Администратор завершает настройку.")
        return False
    await touch_user(message)
    if not await has_consent(message.from_user.id):
        await message.answer("Сначала нужно согласиться с правилами через /start.")
        return False
    if not await get_profile(message.from_user.id):
        await message.answer("Сначала заполним короткую анкету. Напиши /start.")
        return False
    return True

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not pool:
        await message.answer("FitMyN почти готов. Администратор завершает подключение базы.")
        return

    await touch_user(message)
    await state.clear()

    if await has_consent(message.from_user.id) and await get_profile(message.from_user.id):
        await message.answer(
            "Я FitMyN — твой ИИ-помощник по питанию, тренировкам и привычкам. Что делаем?",
            reply_markup=MAIN_KB,
        )
        return

    await message.answer(
        "Привет! Я FitMyN — ИИ-помощник по питанию, тренировкам и привычкам.\n\n"
        "Я не заменяю врача и не ставлю диагнозы. Для персонализации я сохраняю только данные, "
        "которые ты сам сообщишь: цель, питание, активность, тренировки и ограничения.\n\n"
        "Продолжить?",
        reply_markup=CONSENT_KB,
    )

@router.callback_query(F.data == "consent_no")
async def consent_no(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Без согласия персональный профиль сохраняться не будет. Если передумаешь — /start."
    )

@router.callback_query(F.data == "consent_yes")
async def consent_yes(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await db_execute("UPDATE users SET consent=TRUE WHERE telegram_id=$1", call.from_user.id)
    await state.set_state(Onboarding.name)
    await call.message.answer("Как тебя зовут?")

@router.message(Onboarding.name)
async def ob_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Onboarding.age)
    await message.answer("Сколько тебе лет?")

@router.message(Onboarding.age)
async def ob_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text.strip())
    await state.set_state(Onboarding.sex)
    await message.answer("Пол? Можно написать: женский / мужской / не хочу указывать.")

@router.message(Onboarding.sex)
async def ob_sex(message: Message, state: FSMContext):
    await state.update_data(sex=message.text.strip())
    await state.set_state(Onboarding.height)
    await message.answer("Рост в сантиметрах? Можно написать «пропустить».")

@router.message(Onboarding.height)
async def ob_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text.strip())
    await state.set_state(Onboarding.weight)
    await message.answer("Текущий вес? Если не хочешь указывать — «пропустить».")

@router.message(Onboarding.weight)
async def ob_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text.strip())
    await state.set_state(Onboarding.goal)
    await message.answer(
        "Какая главная цель? Например: снизить вес, набрать мышцы, стать сильнее, "
        "улучшить форму или повысить уровень энергии."
    )

@router.message(Onboarding.goal)
async def ob_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text.strip())
    await state.set_state(Onboarding.activity)
    await message.answer(
        "Опиши обычную активность: сидячая работа, сколько примерно шагов, есть ли спорт сейчас."
    )

@router.message(Onboarding.activity)
async def ob_activity(message: Message, state: FSMContext):
    await state.update_data(activity=message.text.strip())
    await state.set_state(Onboarding.frequency)
    await message.answer("Сколько тренировок в неделю реально готов(а) делать?")

@router.message(Onboarding.frequency)
async def ob_frequency(message: Message, state: FSMContext):
    await state.update_data(frequency=message.text.strip())
    await state.set_state(Onboarding.equipment)
    await message.answer("Где будешь тренироваться и какое оборудование доступно?")

@router.message(Onboarding.equipment)
async def ob_equipment(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text.strip())
    await state.set_state(Onboarding.restrictions)
    await message.answer(
        "Есть ли травмы, боли, ограничения, заболевания или другие особенности, "
        "которые важно учитывать? Если нет — напиши «нет»."
    )

@router.message(Onboarding.restrictions)
async def ob_restrictions(message: Message, state: FSMContext):
    await state.update_data(restrictions=message.text.strip())
    await state.set_state(Onboarding.food)
    await message.answer(
        "Расскажи про питание: что любишь/не ешь, аллергии, готовишь ли дома, "
        "хочешь ли считать калории."
    )

@router.message(Onboarding.food)
async def ob_food(message: Message, state: FSMContext):
    await state.update_data(food=message.text.strip())
    await state.set_state(Onboarding.sleep)
    await message.answer("Сколько обычно спишь и как оцениваешь качество сна?")

@router.message(Onboarding.sleep)
async def ob_sleep(message: Message, state: FSMContext):
    await state.update_data(sleep=message.text.strip())
    data = await state.get_data()
    uid = message.from_user.id

    await db_execute(
        """
        INSERT INTO profiles(
            telegram_id, name, age, sex, height, weight, goal, activity,
            frequency, equipment, restrictions, food, sleep, updated_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        ON CONFLICT(telegram_id) DO UPDATE SET
            name=EXCLUDED.name,
            age=EXCLUDED.age,
            sex=EXCLUDED.sex,
            height=EXCLUDED.height,
            weight=EXCLUDED.weight,
            goal=EXCLUDED.goal,
            activity=EXCLUDED.activity,
            frequency=EXCLUDED.frequency,
            equipment=EXCLUDED.equipment,
            restrictions=EXCLUDED.restrictions,
            food=EXCLUDED.food,
            sleep=EXCLUDED.sleep,
            updated_at=EXCLUDED.updated_at
        """,
        uid, data["name"], data["age"], data["sex"], data["height"], data["weight"],
        data["goal"], data["activity"], data["frequency"], data["equipment"],
        data["restrictions"], data["food"], data["sleep"], now_utc()
    )
    await state.clear()

    await message.answer("Профиль готов. Собираю стартовый план…", reply_markup=MAIN_KB)
    answer = await ask_ai(
        uid,
        "Составь мой стартовый план.",
        """
Сделай стартовый план на 7 дней.
Оформи короткими блоками с эмодзи и маркированными списками.
Без таблиц, Markdown, HTML и <br>.

Нужные блоки:
🎯 Цель недели
🥗 Питание — 4–6 простых правил
🍽 Пример одного дня
🏋️ Тренировки на неделю
⚡ Минимум на занятый день
📊 Что отслеживать ежедневно

Не давай медицинских обещаний.
""",
    )
    await message.answer(answer)

@router.message(F.text == "🥗 Питание")
async def food_menu(message: Message):
    if not await ensure_ready(message):
        return
    answer = await ask_ai(
        message.from_user.id,
        "Составь мне план питания на сегодня.",
        """
Составь практичный план питания на сегодня с учётом профиля пользователя.

Формат:
🥗 Питание на сегодня

Главная задача
1–2 коротких предложения.

Завтрак
• вариант блюда
• при необходимости замена

Обед
• вариант блюда
• при необходимости замена

Ужин
• вариант блюда

Перекус
• 1–2 варианта

Фокус дня
Одна простая задача.

Без таблиц, Markdown, HTML и <br>. Пиши компактно.
"""
    )
    await message.answer(answer)

@router.message(F.text == "🏋️ Тренировка")
async def workout_menu(message: Message):
    if not await ensure_ready(message):
        return
    answer = await ask_ai(
        message.from_user.id,
        "Какую тренировку мне сделать сегодня?",
        """
Подбери тренировку под профиль пользователя и доступное оборудование.

Формат:
🏋️ Тренировка на сегодня

Цель
Одна короткая строка.

Разминка
• 2–4 пункта

Основная часть
1. Упражнение — подходы × повторения
2. Упражнение — подходы × повторения
3. И так далее, без лишнего текста

Отдых
• сколько между подходами

Заминка
• 2–3 коротких пункта

Совет
Одна рекомендация по технике или нагрузке.

Без таблиц, Markdown, HTML, <br> и вертикальных черт.
Если есть боль или выраженное недомогание, не предлагай нагрузку через боль.
"""
    )
    await message.answer(answer)

@router.message(F.text == "📊 Отчёт")
async def report_start(message: Message, state: FSMContext):
    if not await ensure_ready(message): return
    await state.set_state(Checkin.waiting_report)
    await message.answer(
        "Пришли одним сообщением:\n\n"
        "Питание: …\nТренировка: …\nШаги/активность: …\nСон: … часов\n"
        "Энергия: …/10\nГолод: …/10\nСамочувствие: …\nЧто было сложным: …"
    )

@router.message(Checkin.waiting_report)
async def report_finish(message: Message, state: FSMContext):
    report = message.text.strip()
    await db_execute(
        "INSERT INTO checkins(telegram_id, report, created_at) VALUES ($1,$2,$3)",
        message.from_user.id, report, now_utc()
    )
    await state.clear()
    answer = await ask_ai(
        message.from_user.id,
        report,
        """
Это ежедневный отчёт. Ответь:
Итог дня
Что получилось
Что скорректировать — максимум 2 пункта
Одна задача на завтра
Будь кратким.
"""
    )
    await message.answer(answer, reply_markup=MAIN_KB)

@router.message(F.text == "📅 Неделя")
async def week_summary(message: Message):
    if not await ensure_ready(message): return
    since = now_utc() - timedelta(days=7)
    rows = await db_fetch(
        """
        SELECT report, created_at
        FROM checkins
        WHERE telegram_id=$1 AND created_at >= $2
        ORDER BY created_at ASC
        """,
        message.from_user.id, since
    )
    if not rows:
        await message.answer("За последние 7 дней пока нет отчётов. Начни с «📊 Отчёт».")
        return

    reports = "\n\n".join(
        f"{r['created_at'].date()}:\n{r['report']}" for r in rows
    )
    answer = await ask_ai(
        message.from_user.id,
        f"Мои отчёты за неделю:\n\n{reports}",
        """
Сделай недельный разбор:
1. Что получилось.
2. Какие тенденции видны.
3. Что мешает.
4. Что изменить на следующей неделе.
5. План тренировок.
6. Фокус питания.
7. Одна главная задача недели.
Не делай выводов по одному измерению веса.
"""
    )
    await message.answer(answer)

@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    if not await ensure_ready(message): return
    await message.answer(profile_to_text(await get_profile(message.from_user.id)))

@router.message(F.text == "💬 Спросить агента")
async def ask_prompt(message: Message):
    if not await ensure_ready(message): return
    await message.answer("Напиши вопрос обычным сообщением. Я учту профиль и последние диалоги.")


@router.message(Command("schedule"))
@router.message(F.text == "⏰ Расписание")
async def notification_schedule(message: Message):
    if not await ensure_ready(message):
        return
    settings = await ensure_notification_settings(message.from_user.id)
    await message.answer(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data == "notify_toggle")
async def notify_toggle(call: CallbackQuery):
    await call.answer()
    settings = await ensure_notification_settings(call.from_user.id)
    await db_execute(
        "UPDATE notification_settings SET enabled=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, not settings["enabled"], now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_m_"))
async def notify_morning_time(call: CallbackQuery):
    await call.answer("Время сохранено")
    raw = call.data.rsplit("_", 1)[-1]
    value = f"{raw[:2]}:{raw[2:]}"
    await db_execute(
        "UPDATE notification_settings SET morning_time=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_e_"))
async def notify_evening_time(call: CallbackQuery):
    await call.answer("Время сохранено")
    raw = call.data.rsplit("_", 1)[-1]
    value = f"{raw[:2]}:{raw[2:]}"
    await db_execute(
        "UPDATE notification_settings SET evening_time=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_tz_"))
async def notify_timezone(call: CallbackQuery):
    mapping = {
        "notify_tz_moscow": "Europe/Moscow",
        "notify_tz_london": "Europe/London",
        "notify_tz_dubai": "Asia/Dubai",
        "notify_tz_nsk": "Asia/Novosibirsk",
    }
    value = mapping.get(call.data)
    if not value:
        await call.answer("Не удалось выбрать часовой пояс")
        return
    await call.answer("Часовой пояс сохранён")
    await ensure_notification_settings(call.from_user.id)
    await db_execute(
        "UPDATE notification_settings SET timezone=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data == "notify_days_auto")
async def notify_days_auto(call: CallbackQuery):
    await call.answer("Дни обновлены")
    await ensure_notification_settings(call.from_user.id)
    profile = await get_profile(call.from_user.id)
    days = workout_days_from_frequency(profile["frequency"] if profile else None)
    await db_execute(
        "UPDATE notification_settings SET workout_days=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, days, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.message(Command("team"))
async def team_stats(message: Message):
    if not pool:
        await message.answer("База данных пока не подключена.")
        return
    await touch_user(message)
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта команда доступна только администратору.")
        return

    since = now_utc() - timedelta(days=7)
    total = await db_fetchrow("SELECT COUNT(*) AS c FROM users WHERE consent=TRUE")
    active = await db_fetchrow(
        "SELECT COUNT(DISTINCT telegram_id) AS c FROM checkins WHERE created_at >= $1", since
    )
    checkins = await db_fetchrow(
        "SELECT COUNT(*) AS c FROM checkins WHERE created_at >= $1", since
    )
    await message.answer(
        "Команда за 7 дней\n\n"
        f"Участников с согласием: {total['c']}\n"
        f"Сдали хотя бы 1 отчёт: {active['c']}\n"
        f"Всего дневных отчётов: {checkins['c']}\n\n"
        "Личные медицинские сведения, вес и ограничения здесь не показываются."
    )

@router.message(Command("reset_profile"))
async def reset_profile(message: Message, state: FSMContext):
    if not pool: return
    await touch_user(message)
    if not await has_consent(message.from_user.id):
        await message.answer("Сначала /start.")
        return
    await db_execute("DELETE FROM profiles WHERE telegram_id=$1", message.from_user.id)
    await state.clear()
    await message.answer("Профиль сброшен. Напиши /start, чтобы заполнить его заново.")

@router.message(Command("delete_me"))
async def delete_me(message: Message, state: FSMContext):
    if not pool: return
    uid = message.from_user.id
    await db_execute("DELETE FROM notification_log WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM notification_settings WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM checkins WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM messages WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM profiles WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM users WHERE telegram_id=$1", uid)
    await state.clear()
    await message.answer("Твои данные FitMyN удалены. Чтобы начать заново — /start.")

@router.message()
async def free_chat(message: Message):
    if not message.text: return
    if not await ensure_ready(message): return
    try:
        answer = await ask_ai(message.from_user.id, message.text)
        await message.answer(answer)
    except Exception:
        logger.exception("AI error")
        await message.answer("Не получилось получить ответ. Попробуй ещё раз.")

async def setup_telegram():
    if not bot:
        logger.warning("TELEGRAM_BOT_TOKEN is missing")
        return
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать работу с FitMyN"),
        BotCommand(command="team", description="Статистика команды"),
        BotCommand(command="schedule", description="Настроить авто-сообщения"),
        BotCommand(command="reset_profile", description="Перезаполнить профиль"),
        BotCommand(command="delete_me", description="Удалить мои данные"),
    ])
    await bot.set_my_description(
        "FitMyN — персональный ИИ-помощник по питанию, тренировкам и привычкам."
    )
    await bot.set_my_short_description(
        "ИИ-тренер и помощник по питанию: план, тренировки и контроль прогресса."
    )

    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
        await bot.set_webhook(
            webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
        )
        logger.info("Webhook configured: %s", webhook_url)
    else:
        logger.warning("RENDER_EXTERNAL_URL missing; webhook not configured")

async def health(request: web.Request):
    configured = bool(bot and client and pool)
    status = 200 if configured else 503
    return web.json_response(
        {
            "service": "FitMyN",
            "configured": configured,
            "telegram": bool(bot),
            "openai": bool(client),
            "database": bool(pool),
        },
        status=status,
    )

async def telegram_webhook(request: web.Request):
    if not bot:
        return web.Response(status=503, text="Telegram not configured")

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != WEBHOOK_SECRET:
        return web.Response(status=403, text="Forbidden")

    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": bot})
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


async def cron_due(request: web.Request):
    if not CRON_SECRET:
        return web.Response(status=503, text="CRON_SECRET is not configured")
    supplied = request.headers.get("X-Cron-Secret", "")
    if supplied != CRON_SECRET:
        return web.Response(status=403, text="Forbidden")
    stats = await run_due_notifications()
    return web.json_response(stats)


async def on_startup(app: web.Application):
    await init_db()
    await setup_telegram()
    app["notification_task"] = asyncio.create_task(notification_loop())

async def on_cleanup(app: web.Application):
    task = app.get("notification_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if bot:
        await bot.session.close()
    if pool:
        await pool.close()

def create_app():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/telegram/{secret}", telegram_webhook)
    app.router.add_post("/cron/due", cron_due)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
