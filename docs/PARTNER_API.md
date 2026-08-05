# ChannelDesk Partner API

## Что это

Внешние сайты и CRM могут создавать черновики в рабочем пространстве ChannelDesk, читать их статусы и получать webhook-события.

Все внешние запросы используют:

```text
Authorization: Bearer cd_live_...
```

Ключ создаётся в Mini App: `Ещё → Интеграции`.

## Права API-ключа

- `channels:read` — список активных каналов;
- `drafts:create` — создание черновиков;
- `posts:read` — чтение постов и вложений;
- `publish:request` — отправка черновика на согласование.

Ключ показывается только один раз. Не храните его в браузерном JavaScript — для публичного сайта используйте серверную часть.

## Endpoints

```text
GET  /api/v1/workspaces/{workspace_id}/channels
POST /api/v1/workspaces/{workspace_id}/drafts
GET  /api/v1/workspaces/{workspace_id}/posts/{post_id}
POST /api/v1/workspaces/{workspace_id}/posts/{post_id}/submit
```

Черновик создаётся со статусом `draft`. Он не публикуется автоматически.

## Создание черновика

```bash
curl -X POST https://channeldesk.vercel.app/api/v1/workspaces/3/drafts \
  -H "Authorization: Bearer cd_live_..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: website-news-123" \
  -d '{
    "title": "Новость с сайта",
    "text": "Текст новости",
    "channel_id": 5,
    "source": "website",
    "source_url": "https://example.com/news/123",
    "external_id": "news-123",
    "assets": [
      {
        "url": "https://example.com/images/news.jpg",
        "file_name": "news.jpg",
        "file_type": "image/jpeg"
      }
    ]
  }'
```

## Ответ

```json
{
  "id": 248,
  "workspace_id": 3,
  "channel_id": 5,
  "status": "draft",
  "title": "Новость с сайта",
  "post": {},
  "assets": []
}
```

## Idempotency-Key

Если внешний сервис повторит запрос с тем же ключом, ChannelDesk вернёт первоначальный результат и не создаст второй пост.

Если тот же ключ отправлен с другими данными, API вернёт `409`.

## Webhooks

Webhook создаётся в `Ещё → Интеграции`.

Сейчас доступны события:

```text
post.created
post.submitted
```

Подпись проверяется по заголовку:

```text
X-ChannelDesk-Signature: sha256=<HMAC-SHA256 от тела запроса>
```

Секрет webhook-а показывается один раз при создании.
