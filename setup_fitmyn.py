import asyncio
import getpass
from pathlib import Path
from aiogram import Bot
from aiogram.types import BotCommand

ENV = Path(".env")

DESCRIPTION = (
    "FitMyN — персональный ИИ-помощник по питанию, тренировкам и привычкам. "
    "Помогает составить реалистичный план, отслеживать прогресс и корректировать его."
)
SHORT_DESCRIPTION = "ИИ-тренер и помощник по питанию: план, тренировки и контроль прогресса."
COMMANDS = [
    BotCommand(command="start", description="Начать работу с FitMyN"),
    BotCommand(command="team", description="Статистика команды (администратор)"),
    BotCommand(command="reset_profile", description="Перезаполнить профиль"),
]

def save_env(token: str, api_key: str, admin_id: str):
    ENV.write_text(
        f"TELEGRAM_BOT_TOKEN={token}\n"
        f"OPENAI_API_KEY={api_key}\n"
        f"OPENAI_MODEL=gpt-5.6-luna\n"
        f"ADMIN_IDS={admin_id}\n"
        f"DB_PATH=coach_bot.db\n",
        encoding="utf-8",
    )

async def configure_bot(token: str):
    bot = Bot(token)
    me = await bot.get_me()
    await bot.set_my_commands(COMMANDS)
    await bot.set_my_description(DESCRIPTION)
    await bot.set_my_short_description(SHORT_DESCRIPTION)
    await bot.session.close()
    return me

async def main():
    print("FitMyN — безопасная первичная настройка\n")
    token = getpass.getpass("Вставь НОВЫЙ Telegram bot token: ").strip()
    api_key = getpass.getpass("Вставь OpenAI API key: ").strip()
    admin_id = input("Вставь свой numeric Telegram ID (можно оставить пустым): ").strip()

    if not token or ":" not in token:
        raise SystemExit("Telegram token указан неверно.")
    if not api_key:
        raise SystemExit("OpenAI API key не указан.")

    me = await configure_bot(token)
    save_env(token, api_key, admin_id)
    print(f"\nГотово: @{me.username} настроен.")
    print("Описание и команды Telegram установлены автоматически.")
    print("Секреты сохранены локально в .env.")
    print("Теперь запусти: python main.py")

if __name__ == "__main__":
    asyncio.run(main())
