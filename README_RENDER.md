# Fitmy deployment

Runtime: Python 3.12.12. Start: python main.py. Health endpoint: /health.

Required environment variables: TELEGRAM_BOT_TOKEN, DATABASE_URL, WEBHOOK_SECRET, RENDER_EXTERNAL_URL. AI additionally requires OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL and a funded provider account. CRON_SECRET protects /cron/due. Never commit secrets.

The Mini App source is mini_app.html; dish recipes are meal_recipes.json. Edit these sources directly. Legacy JS patch files are not loaded.

Run: python -m unittest discover -s tests -v; node tests/frontend.cjs. GitHub Actions additionally runs mobile Chromium workflows using mocked API responses. These do not test real Telegram Stars billing.

Database tables are created additively during startup. Telegram updates and dialogue state are persisted in PostgreSQL. A single inbox consumer is expected; do not increase instance count without adding queue claims. Delivery is at-least-once; side effects must remain idempotent.

Production requirements still requiring account configuration: move free Postgres to a permanent plan before its expiration, enable external backups, configure paid AI quota, and set Render Health Check Path to /health. render.yaml changes do not automatically update a manually-created service.

Meal calories are estimates from the catalog; the app is not a medically reviewed meal planner. Basic exercise plans are not prescribed for profiles with declared health restrictions. Food exclusions use a limited explicit ingredient filter, not clinical allergy assessment.
