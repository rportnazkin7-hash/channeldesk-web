from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.posts import sanitize_telegram_html
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['public-news'])
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


class PublicNewsPageCreate(BaseModel):
    channel_id: int | None = None
    title: str = Field(default='Предложить новость', min_length=2, max_length=160)
    description: str = Field(default='', max_length=2000)


class PublicNewsUpload(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default='application/octet-stream', max_length=64)
    size: int = Field(default=0, ge=0)


class PublicNewsSubmit(BaseModel):
    title: str = Field(default='', max_length=255)
    text: str = Field(default='', max_length=40000)
    contact_name: str = Field(default='', max_length=160)
    contact_telegram: str = Field(default='', max_length=160)
    contact_email: str = Field(default='', max_length=255)
    source_url: str = Field(default='', max_length=2048)
    is_anonymous: bool = False
    asset_ids: list[int] = Field(default_factory=list, max_length=10)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _url(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(422, 'Ссылка должна начинаться с https:// или http://')
    return value


def _page(cur, token: str) -> dict | None:
    cur.execute("""SELECT p.id,p.workspace_id,p.channel_id,p.title,p.description,
    c.title AS channel_title
    FROM cd_public_news_pages p
    LEFT JOIN cd_channels c ON c.id=p.channel_id
    WHERE p.token_hash=%s AND p.is_active=true""", (_hash(token),))
    return cur.fetchone()


@router.post('/workspaces/{workspace_id}/public-news-pages', status_code=201)
def create_public_news_page(workspace_id: int, payload: PublicNewsPageCreate,
                            user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    with connect() as conn, conn.cursor() as cur:
        if payload.channel_id is not None:
            cur.execute('SELECT id,title FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                        (payload.channel_id, workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')
        token = secrets.token_urlsafe(24)
        cur.execute("""INSERT INTO cd_public_news_pages(
            workspace_id,channel_id,token_hash,title,description,created_by)
        VALUES(%s,%s,%s,%s,%s,%s) RETURNING id,title,description,channel_id""",
                    (workspace_id, payload.channel_id, _hash(token), payload.title.strip(),
                     payload.description.strip(), user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'public_news.page_created', 'public_news_page', row['id'])
    return {**row, 'path': f'/public-news?token={token}'}


@router.delete('/workspaces/{workspace_id}/public-news-pages/{page_id}', status_code=204)
def delete_public_news_page(workspace_id: int, page_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'api.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_public_news_pages SET is_active=false,updated_at=now()
        WHERE id=%s AND workspace_id=%s AND is_active=true RETURNING id""", (page_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Страница приёма новостей не найдена')
        audit(cur, workspace_id, user['id'], 'public_news.page_disabled', 'public_news_page', page_id)
    return None


@router.get('/public-news/{token}')
def get_public_news_page(token: str):
    with connect() as conn, conn.cursor() as cur:
        page = _page(cur, token)
    if not page:
        raise HTTPException(404, 'Страница приёма новостей не найдена или отключена')
    return {
        'title': page['title'],
        'description': page['description'],
        'channel_title': page.get('channel_title'),
        'channel_id': page.get('channel_id'),
    }


@router.post('/public-news/{token}/upload-url', status_code=201)
def public_news_upload_url(token: str, payload: PublicNewsUpload):
    if payload.size > MAX_UPLOAD_SIZE:
        raise HTTPException(413, 'Файл больше 50 МБ')
    # Импортируем здесь, чтобы публичный GET страницы не зависел от Storage env.
    from api.assets import anon_key, storage_base_url
    base = storage_base_url()
    storage_key = anon_key()
    with connect() as conn, conn.cursor() as cur:
        page = _page(cur, token)
        if not page:
            raise HTTPException(404, 'Страница приёма новостей не найдена или отключена')
        ext = Path(payload.file_name).suffix.lower()
        path = f"{page['workspace_id']}/public-news/{page['id']}/{uuid4().hex}{ext}"
        file_url = f'{base}/storage/v1/object/public/channeldesk-assets/{path}'
        upload_url = f'{base}/storage/v1/object/channeldesk-assets/{path}'
        cur.execute("""INSERT INTO cd_content_assets(
            workspace_id,post_id,file_name,file_type,file_url,size_bytes,uploaded_by)
        VALUES(%s,NULL,%s,%s,%s,%s,NULL) RETURNING id""",
                    (page['workspace_id'], payload.file_name.strip(), payload.content_type.strip(),
                     file_url, payload.size))
        asset = cur.fetchone()
    return {'asset_id': asset['id'], 'file_url': file_url, 'upload_url': upload_url,
            'anon_key': storage_key, 'bucket': 'channeldesk-assets'}


def _notify_workspace(workspace_id: int, post_id: int, request_id: int,
                      title: str, contact_name: str, contact_telegram: str,
                      contact_email: str, is_anonymous: bool) -> None:
    """Best-effort notification to workspace owners/admins through Bot API."""
    try:
        from api.telegram import _get_json
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT u.telegram_id FROM cd_workspace_members m
            JOIN cd_users u ON u.id=m.user_id
            WHERE m.workspace_id=%s AND m.status='active' AND m.role IN ('owner','admin')""",
                        (workspace_id,))
            recipients = cur.fetchall() or []
        text = f'📰 Новая заявка в редакцию\n{title or "Без заголовка"}\nЗаявка #{request_id}'
        if is_anonymous:
            text += '\nИсточник: анонимно'
        else:
            if contact_name.strip():
                text += f'\nАвтор: {contact_name.strip()}'
            if contact_telegram.strip():
                text += f'\nTelegram: {contact_telegram.strip()}'
            if contact_email.strip():
                text += f'\nEmail: {contact_email.strip()}'
        mini_url = os.getenv('MINI_APP_URL', '').strip()
        markup = None
        if mini_url:
            separator = '&' if '?' in mini_url else '?'
            markup = json.dumps({
                'inline_keyboard': [[{
                    'text': 'Открыть черновик',
                    'web_app': {'url': f'{mini_url}{separator}forward_post={post_id}&forward_workspace={workspace_id}'},
                }]]
            })
        for recipient in recipients:
            params = {'chat_id': recipient['telegram_id'], 'text': text}
            if markup:
                params['reply_markup'] = markup
            _get_json('sendMessage', params)
    except Exception:
        return


@router.post('/public-news/{token}/submit', status_code=201)
def submit_public_news(token: str, payload: PublicNewsSubmit):
    source_url = _url(payload.source_url) if payload.source_url.strip() else ''
    safe_text = sanitize_telegram_html(payload.text)
    title = payload.title.strip()
    if not title:
        title = next((line.strip() for line in payload.text.splitlines() if line.strip()), '')[:255]
    if not title:
        title = 'Предложение новости'
    if not safe_text and not payload.asset_ids:
        raise HTTPException(422, 'Добавьте текст или хотя бы один файл')

    with connect() as conn, conn.cursor() as cur:
        page = _page(cur, token)
        if not page:
            raise HTTPException(404, 'Страница приёма новостей не найдена или отключена')
        # Простая защита публичной формы от случайного/массового спама.
        cur.execute("""SELECT count(*) AS cnt FROM cd_public_news_requests
        WHERE page_id=%s AND created_at>now()-interval '10 minutes'""", (page['id'],))
        if int(cur.fetchone()['cnt'] or 0) >= 20:
            raise HTTPException(429, 'Форма временно перегружена. Попробуйте позже.')
        asset_rows = []
        if payload.asset_ids:
            placeholders = ','.join(['%s'] * len(payload.asset_ids))
            cur.execute(f"""SELECT id,file_name,file_type,file_url,size_bytes
            FROM cd_content_assets
            WHERE id IN ({placeholders}) AND workspace_id=%s
              AND file_url LIKE %s
              AND post_id IS NULL
              AND created_at>now()-interval '2 hours'""",
                        [*payload.asset_ids, page['workspace_id'], f"%/{page['workspace_id']}/public-news/{page['id']}/%"])
            asset_rows = cur.fetchall() or []
            if len(asset_rows) != len(set(payload.asset_ids)):
                raise HTTPException(422, 'Одно из вложений устарело. Загрузите файлы ещё раз.')
        cur.execute("""INSERT INTO cd_posts(
            workspace_id,channel_id,title,text,status,approval_required,buttons,source,source_url)
        VALUES(%s,%s,%s,%s,'draft',true,'[]'::jsonb,'public_news',%s) RETURNING id""",
                    (page['workspace_id'], page['channel_id'], title, safe_text, source_url))
        post = cur.fetchone()
        if safe_text:
            cur.execute("""INSERT INTO cd_post_versions(post_id,title,text,created_by)
            VALUES(%s,%s,%s,NULL)""", (post['id'], title, safe_text))
        if asset_rows:
            placeholders = ','.join(['%s'] * len(asset_rows))
            cur.execute(f"UPDATE cd_content_assets SET post_id=%s WHERE id IN ({placeholders})",
                        [post['id'], *[asset['id'] for asset in asset_rows]])
        cur.execute("""INSERT INTO cd_public_news_requests(
            page_id,workspace_id,channel_id,post_id,contact_name,contact_telegram,
            contact_email,source_url,is_anonymous)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (page['id'], page['workspace_id'], page['channel_id'], post['id'],
                     payload.contact_name.strip(), payload.contact_telegram.strip(), payload.contact_email.strip(),
                     source_url, payload.is_anonymous))
        request = cur.fetchone()
        cur.execute("""INSERT INTO cd_audit_log(workspace_id,user_id,action,entity_type,entity_id,details)
        VALUES(%s,NULL,'public_news.submitted','post',%s,%s::jsonb)""",
                    (page['workspace_id'], post['id'], json.dumps({'request_id': request['id']})))
    _notify_workspace(page['workspace_id'], post['id'], request['id'], title,
                      payload.contact_name, payload.contact_telegram, payload.contact_email,
                      payload.is_anonymous)
    return {'request_id': request['id'], 'post_id': post['id'],
            'message': 'Материал отправлен редактору. Спасибо!'}
