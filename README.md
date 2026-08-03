# ChannelDesk Web

Frontend (React/Vite Mini App) + FastAPI backend. Деплоится на **Vercel** → https://channeldesk.vercel.app

## Структура

- `src/` — React/Vite Mini App (Telegram WebApp)
- `api/` — FastAPI (auth, workspaces, channels, invites, audit, RBAC)
- `migrations/` + `migrate.py` — SQL-миграции для Supabase
- `tests/` — pytest-тесты API
- `requirements.txt` — зависимости Python-функций Vercel

## Переменные окружения (Vercel)

```text
BOT_TOKEN=<токен @channel_desk_bot>
DATABASE_URL=<Supabase pooler URL>
ADMIN_IDS=<Telegram ID владельца>
ALLOWED_ORIGINS=https://channeldesk.vercel.app
```

## Проверка

```bash
npm ci && npm run typecheck && npm run build
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

> Бот (`bot/`, Bothost) живёт в репозитории **channeldesk** — здесь его нет.
