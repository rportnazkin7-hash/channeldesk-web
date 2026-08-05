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
REQUIRED_CHANNEL=@thechanneldesk
REQUIRED_CHANNEL_URL=https://t.me/thechanneldesk
ZBT_ENABLED=true
ALLOWED_ORIGINS=https://channeldesk.vercel.app
```

## Partner API

В Mini App откройте `Ещё → Интеграции`, создайте API-ключ и передайте его внешнему сайту или CRM. Ключ показывается только один раз.

Получить каналы:

```bash
curl https://channeldesk.vercel.app/api/v1/workspaces/3/channels \\
  -H "Authorization: Bearer cd_live_..."
```

Создать черновик:

```bash
curl -X POST https://channeldesk.vercel.app/api/v1/workspaces/3/drafts \\
  -H "Authorization: Bearer cd_live_..." \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: website-news-123" \\
  -d '{
    "title": "Новость с сайта",
    "text": "Текст новости",
    "channel_id": 5,
    "source": "website",
    "source_url": "https://example.com/news/123",
    "external_id": "news-123"
  }'
```

По умолчанию внешний API создаёт только черновики. Публикация проходит через обычную проверку ChannelDesk. Для защиты повторных запросов используйте `Idempotency-Key`. Webhook подписывается заголовком `X-ChannelDesk-Signature: sha256=...` с помощью HMAC-SHA256.

## Проверка

```bash
npm ci && npm run typecheck && npm run build
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

> Бот (`bot/`, Bothost) живёт в репозитории **channeldesk** — здесь его нет.
