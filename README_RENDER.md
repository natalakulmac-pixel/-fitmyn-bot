# FitMyN — Render webhook version

Эта версия рассчитана на Render Web Service и Telegram webhook.

## Что изменено
- PostgreSQL вместо SQLite.
- Telegram webhook вместо polling.
- HTTP endpoints `/` и `/health`.
- Автоматическая установка webhook по `RENDER_EXTERNAL_URL`.
- Команда `/delete_me` для удаления персональных данных пользователя.
- Модель по умолчанию: `gpt-6-luna`.

## Нужные переменные окружения
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `DATABASE_URL`
- `WEBHOOK_SECRET`
- `ADMIN_IDS`
- `OPENAI_MODEL=gpt-6-luna`

Секреты нельзя коммитить в GitHub.

На Render бесплатный web service может засыпать при отсутствии входящего трафика.
Webhook-подход подходит лучше polling, потому что новое сообщение Telegram создаёт входящий HTTP-запрос.
