from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.posts import _normalize_buttons, sanitize_telegram_html
from api.rbac import require_action
from api.workspaces import audit


ui_router = APIRouter(prefix='/api', tags=['integrations'])
partner_router = APIRouter(prefix='/api/v1', tags=['partner-api'])

ALLOWED_SCOPES = {
    'drafts:create',
    'posts:read',
    'channels:read',
    'publish:request',
}
DEFAULT_SCOPES = ['drafts:create', 'posts:read', 'channels:read']
partner_bearer = HTTPBearer(auto_error=False)
WEBHOOK_EVENTS = {
    'post.created',
    'post.submitted',
}


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    scopes: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES), max_length=8)
    expires_at: datetime | None = None


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=1, max_length=2048)
    events: list[str] = Field(default_factory=lambda: ['post.created'], max_length=12)


class ExternalAsset(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    file_name: str = Field(default='attachment', max_length=255)
    file_type: str = Field(default='application/octet-stream', max_length=64)
    size_bytes: int | None = Field(default=None, ge=0)


class ExternalDraftCreate(BaseModel):
    title: str = Field(default='', max_length=255)
    text: str = Field(default='', max_length=40000)
    channel_id: int | None = None
    buttons: list[list[dict]] = Field(default_factory=list, max_length=8)
    assets: list[ExternalAsset] = Field(default_factory=list, max_length=10)
    source: str = Field(default='api', min_length=1, max_length=64)
    source_url: str | None = Field(default=None, max_length=2048)
    external_id: str | None = Field(default=None, max_length=255)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _validate_url(value: str, label: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(422, f'{label} должна начинаться с https:// или http://')
    return value.strip()


def _validate_scopes(scopes: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(scope.strip() for scope in scopes if scope.strip()))
    unknown = [scope for scope in normalized if scope not in ALLOWED_SCOPES]
    if unknown:
        raise HTTPException(422, f'Неизвестные права API: {", ".join(unknown)}')
    if not normalized:
        raise HTTPException(422, 'У API-ключа должно быть хотя бы одно право')
    return normalized


def _api_key_from_header(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'Передайте API-ключ в заголовке Authorization: Bearer cd_live_...')
    token = authorization[7:].strip()
    if not token.startswith('cd_live_') or len(token) < 24:
        raise HTTPException(401, 'Некорректный API-ключ')
    return token


def partner_api_key(credentials: HTTPAuthorizationCredentials | None = Depends(partner_bearer)) -> dict:
    token = _api_key_from_header(
        f'{credentials.scheme} {credentials.credentials}' if credentials else None
    )
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT k.id,k.workspace_id,k.name,k.scopes,k.created_by,k.expires_at,
        w.name AS workspace_name
        FROM cd_api_keys k JOIN cd_workspaces w ON w.id=k.workspace_id
        WHERE k.key_hash=%s AND k.revoked_at IS NULL
          AND w.is_active=true
          AND (k.expires_at IS NULL OR k.expires_at>now())""", (_hash(token),))
        key = cur.fetchone()
        if not key:
            raise HTTPException(401, 'API-ключ не найден, отозван или просрочен')
        cur.execute('UPDATE cd_api_keys SET last_used_at=now(),updated_at=now() WHERE id=%s', (key['id'],))
    return key


def _require_partner_access(key: dict, workspace_id: int, scope: str) -> None:
    if key['workspace_id'] != workspace_id:
        raise HTTPException(403, 'API-ключ не имеет доступа к этому рабочему пространству')
    scopes = key.get('scopes') or []
    if scope not in scopes:
        raise HTTPException(403, f'API-ключу не выдано право {scope}')


def _post_payload(post: dict, assets: list[dict] | None = None) -> dict:
    post_json = _jsonable(post)
    result = {
        'id': post_json.get('id'),
        'workspace_id': post_json.get('workspace_id'),
        'channel_id': post_json.get('channel_id'),
        'status': post_json.get('status'),
        'title': post_json.get('title'),
        'post': post_json,
    }
    if assets is not None:
        result['assets'] = _jsonable(assets)
    return result


def _webhook_request(event: str, payload: dict, webhook: dict) -> None:
    body = json.dumps({'event': event, 'data': _jsonable(payload)}, ensure_ascii=False, separators=(',', ':')).encode()
    signature = hmac.new(webhook['secret'].encode(), body, hashlib.sha256).hexdigest()
    delivery_id = secrets.token_urlsafe(12)
    request = Request(webhook['url'], data=body, method='POST', headers={
        'Content-Type': 'application/json',
        'User-Agent': 'ChannelDesk-Webhook/1.0',
        'X-ChannelDesk-Event': event,
        'X-ChannelDesk-Delivery': delivery_id,
        'X-ChannelDesk-Signature': f'sha256={signature}',
    })
    with urlopen(request, timeout=5) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f'HTTP {response.status}')


def _deliver_one_webhook(event: str, payload: dict, webhook: dict) -> None:
    try:
        _webhook_request(event, payload, webhook)
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""UPDATE cd_api_webhooks SET last_delivered_at=now(),last_error=NULL,updated_at=now()
            WHERE id=%s""", (webhook['id'],))
    except Exception as exc:  # noqa: BLE001
        try:
            with connect() as conn, conn.cursor() as cur:
                cur.execute("""UPDATE cd_api_webhooks SET last_error=%s,updated_at=now()
                WHERE id=%s""", (str(exc)[:500], webhook['id']))
        except Exception:
            pass


def emit_webhook_event(workspace_id: int, event: str, payload: dict) -> None:
    """Best-effort delivery for the small MVP webhook layer.

    Deliveries are parallelised and capped at five endpoints so a slow external
    service cannot serially block the whole request for every webhook.
    """
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT id,url,secret FROM cd_api_webhooks
            WHERE workspace_id=%s AND is_active=true AND events ? %s""", (workspace_id, event))
            webhooks = cur.fetchall() or []
        if webhooks:
            with ThreadPoolExecutor(max_workers=min(5, len(webhooks))) as executor:
                list(executor.map(lambda hook: _deliver_one_webhook(event, payload, hook), webhooks[:5]))
    except Exception:
        # Webhook failure must never break creation of a post.
        return


# ---------- Управление ключами и webhook-ами из Mini App ----------

@ui_router.get('/workspaces/{workspace_id}/api-keys')
def list_api_keys(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,name,key_prefix,scopes,expires_at,last_used_at,revoked_at,created_at
        FROM cd_api_keys WHERE workspace_id=%s ORDER BY created_at DESC,id DESC""", (workspace_id,))
        return cur.fetchall()


@ui_router.post('/workspaces/{workspace_id}/api-keys', status_code=201)
def create_api_key(workspace_id: int, payload: ApiKeyCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    scopes = _validate_scopes(payload.scopes)
    expires_at = payload.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(422, 'Срок действия ключа должен быть в будущем')
    token = f'cd_live_{secrets.token_urlsafe(32)}'
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_api_keys(workspace_id,name,key_prefix,key_hash,scopes,expires_at,created_by)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s)
        RETURNING id,name,key_prefix,scopes,expires_at,created_at""",
                    (workspace_id, payload.name.strip(), token[:16], _hash(token), json.dumps(scopes),
                     expires_at, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'api_key.created', 'api_key', row['id'])
    return {**row, 'token': token}


@ui_router.delete('/workspaces/{workspace_id}/api-keys/{key_id}', status_code=204)
def revoke_api_key(workspace_id: int, key_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_api_keys SET revoked_at=now(),updated_at=now()
        WHERE id=%s AND workspace_id=%s AND revoked_at IS NULL RETURNING id""", (key_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'API-ключ не найден или уже отозван')
        audit(cur, workspace_id, user['id'], 'api_key.revoked', 'api_key', key_id)
    return None


@ui_router.get('/workspaces/{workspace_id}/webhooks')
def list_webhooks(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,name,url,events,is_active,last_delivered_at,last_error,created_at
        FROM cd_api_webhooks WHERE workspace_id=%s ORDER BY created_at DESC,id DESC""", (workspace_id,))
        return cur.fetchall()


@ui_router.post('/workspaces/{workspace_id}/webhooks', status_code=201)
def create_webhook(workspace_id: int, payload: WebhookCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    url = _validate_url(payload.url, 'URL webhook-а')
    events = list(dict.fromkeys(payload.events))
    unknown = [event for event in events if event not in WEBHOOK_EVENTS]
    if unknown:
        raise HTTPException(422, f'Неизвестные события webhook-а: {", ".join(unknown)}')
    if not events:
        raise HTTPException(422, 'Выберите хотя бы одно событие')
    secret = f'whsec_{secrets.token_urlsafe(24)}'
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_api_webhooks(workspace_id,name,url,secret,events,created_by)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s)
        RETURNING id,name,url,events,is_active,created_at""",
                    (workspace_id, payload.name.strip(), url, secret, json.dumps(events), user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'webhook.created', 'webhook', row['id'])
    return {**row, 'secret': secret}


@ui_router.delete('/workspaces/{workspace_id}/webhooks/{webhook_id}', status_code=204)
def delete_webhook(workspace_id: int, webhook_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_api_webhooks SET is_active=false,updated_at=now()
        WHERE id=%s AND workspace_id=%s AND is_active=true RETURNING id""", (webhook_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Webhook не найден или уже отключён')
        audit(cur, workspace_id, user['id'], 'webhook.disabled', 'webhook', webhook_id)
    return None


# ---------- Партнёрский API ----------

@partner_router.get('/me')
def partner_me(key: dict = Depends(partner_api_key)):
    return {
        'api_key_id': key['id'],
        'workspace_id': key['workspace_id'],
        'workspace_name': key.get('workspace_name'),
        'name': key['name'],
        'scopes': key.get('scopes') or [],
        'expires_at': key.get('expires_at'),
    }


@partner_router.get('/workspaces/{workspace_id}/channels')
def partner_channels(workspace_id: int, key: dict = Depends(partner_api_key)):
    _require_partner_access(key, workspace_id, 'channels:read')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,title,username,telegram_chat_id
        FROM cd_channels WHERE workspace_id=%s AND is_active=true ORDER BY title""", (workspace_id,))
        return {'workspace_id': workspace_id, 'channels': cur.fetchall()}


@partner_router.post('/workspaces/{workspace_id}/drafts', status_code=201)
def partner_create_draft(workspace_id: int, payload: ExternalDraftCreate,
                         idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
                         key: dict = Depends(partner_api_key)):
    _require_partner_access(key, workspace_id, 'drafts:create')
    if idempotency_key and len(idempotency_key.strip()) > 255:
        raise HTTPException(422, 'Idempotency-Key слишком длинный')
    request_json = payload.model_dump(mode='json')
    request_hash = _hash(json.dumps(request_json, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    safe_text = sanitize_telegram_html(payload.text)
    buttons = _normalize_buttons(payload.buttons)
    source_url = _validate_url(payload.source_url, 'source_url') if payload.source_url else None
    source = payload.source.strip() or 'api'
    assets = []
    for asset in payload.assets:
        assets.append({
            'url': _validate_url(asset.url, 'URL вложения'),
            'file_name': asset.file_name.strip() or 'attachment',
            'file_type': asset.file_type.strip() or 'application/octet-stream',
            'size_bytes': asset.size_bytes,
        })

    with connect() as conn, conn.cursor() as cur:
        if idempotency_key:
            cur.execute("""SELECT request_hash,response_json,status_code
            FROM cd_api_idempotency_keys WHERE api_key_id=%s AND idempotency_key=%s""",
                        (key['id'], idempotency_key.strip()))
            previous = cur.fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    raise HTTPException(409, 'Этот Idempotency-Key уже использован с другими данными')
                return JSONResponse(content=previous['response_json'], status_code=previous['status_code'])

        if payload.channel_id is not None:
            cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                        (payload.channel_id, workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')
        cur.execute("""INSERT INTO cd_posts(
            workspace_id,channel_id,title,text,status,approval_required,created_by,buttons,source,source_url,external_id)
        VALUES(%s,%s,%s,%s,'draft',true,%s,%s::jsonb,%s,%s,%s) RETURNING *""",
                    (workspace_id, payload.channel_id, payload.title.strip(), safe_text, key.get('created_by'),
                     json.dumps(buttons), source, source_url, payload.external_id))
        post = cur.fetchone()
        if safe_text:
            cur.execute("""INSERT INTO cd_post_versions(post_id,title,text,created_by)
            VALUES(%s,%s,%s,%s)""", (post['id'], post['title'], post['text'], key.get('created_by')))
        asset_rows = []
        for asset in assets:
            cur.execute("""INSERT INTO cd_content_assets(
                workspace_id,post_id,file_name,file_type,file_url,size_bytes,uploaded_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                        (workspace_id, post['id'], asset['file_name'], asset['file_type'], asset['url'],
                         asset['size_bytes'], key.get('created_by')))
            asset_rows.append(cur.fetchone())
        audit(cur, workspace_id, key.get('created_by'), 'post.created_by_api', 'post', post['id'],
              json.dumps({'source': source, 'external_id': payload.external_id}))
        response = _post_payload(post, asset_rows)
        if idempotency_key:
            cur.execute("""INSERT INTO cd_api_idempotency_keys(
                api_key_id,idempotency_key,request_hash,response_json,status_code)
            VALUES(%s,%s,%s,%s::jsonb,201)""",
                        (key['id'], idempotency_key.strip(), request_hash, json.dumps(response, ensure_ascii=False, default=str)))
    emit_webhook_event(workspace_id, 'post.created', response)
    return response


@partner_router.get('/workspaces/{workspace_id}/posts/{post_id}')
def partner_get_post(workspace_id: int, post_id: int, key: dict = Depends(partner_api_key)):
    _require_partner_access(key, workspace_id, 'posts:read')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.*,c.title AS channel_title
        FROM cd_posts p LEFT JOIN cd_channels c ON c.id=p.channel_id
        WHERE p.id=%s AND p.workspace_id=%s""", (post_id, workspace_id))
        post = cur.fetchone()
        if not post:
            raise HTTPException(404, 'Пост не найден')
        cur.execute('SELECT * FROM cd_content_assets WHERE post_id=%s ORDER BY created_at', (post_id,))
        assets = cur.fetchall() or []
    return _post_payload(post, assets)


@partner_router.post('/workspaces/{workspace_id}/posts/{post_id}/submit')
def partner_submit_post(workspace_id: int, post_id: int, key: dict = Depends(partner_api_key)):
    _require_partner_access(key, workspace_id, 'publish:request')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_posts SET status='review',updated_at=now()
        WHERE id=%s AND workspace_id=%s AND status IN ('draft','in_progress','changes_requested') RETURNING *""",
                    (post_id, workspace_id))
        post = cur.fetchone()
        if not post:
            raise HTTPException(404, 'Пост не найден или его нельзя отправить на согласование')
        audit(cur, workspace_id, key.get('created_by'), 'post.submitted_by_api', 'post', post_id)
    response = _post_payload(post)
    emit_webhook_event(workspace_id, 'post.submitted', response)
    return response
