from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['posts'])

# Статусы и допустимые переходы для явных workflow-эндпоинтов.
ALLOWED_STATUSES = {
    'idea', 'draft', 'in_progress', 'review', 'changes_requested', 'approved',
    'scheduled', 'publishing', 'published', 'failed', 'cancelled',
}
CREATABLE = {'idea', 'draft', 'in_progress'}
EDITABLE = {'idea', 'draft', 'in_progress', 'approved', 'scheduled'}
PUBLISHED_LOCKED = {'publishing', 'published', 'cancelled'}


class PostCreate(BaseModel):
    title: str = Field(default='', max_length=255)
    text: str = Field(default='', max_length=40000)
    channel_id: int | None = None
    status: str = 'draft'
    scheduled_at: datetime | None = None
    approval_required: bool = True
    buttons: list[list[dict]] = Field(default=[], max_length=8)


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    text: str | None = Field(default=None, max_length=40000)
    channel_id: int | None = None
    scheduled_at: datetime | None = None
    buttons: list[list[dict]] | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    title: str = Field(default='', max_length=255)
    text: str = Field(default='', max_length=40000)


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SchedulePayload(BaseModel):
    scheduled_at: datetime | None = None


def _get_post(cur, workspace_id: int, post_id: int) -> dict:
    cur.execute('SELECT * FROM cd_posts WHERE id=%s AND workspace_id=%s', (post_id, workspace_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Публикация не найдена')
    return row


def _ensure_channel(cur, workspace_id: int, channel_id: int | None) -> None:
    if channel_id is None:
        return
    cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true', (channel_id, workspace_id))
    if not cur.fetchone():
        raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')


def _normalize_buttons(buttons) -> list:
    """Нормализует inline-кнопки: [[{text,url}], ...]. Для каналов — только URL-кнопки."""
    if not buttons:
        return []
    if not isinstance(buttons, list):
        raise HTTPException(422, 'buttons должен быть списком рядов')
    out: list = []
    for row in buttons:
        if not isinstance(row, list):
            raise HTTPException(422, 'Каждый ряд кнопок — список')
        row_out: list = []
        for btn in row:
            if not isinstance(btn, dict):
                raise HTTPException(422, 'Кнопка должна быть объектом')
            text = str(btn.get('text', '')).strip()
            url = str(btn.get('url', '')).strip()
            if not text:
                raise HTTPException(422, 'У кнопки нет текста')
            if not url:
                raise HTTPException(422, 'У кнопки нет url — в каналах доступны только URL-кнопки')
            parsed = urlparse(url)
            if parsed.scheme not in {'http', 'https', 'tg'} or (parsed.scheme != 'tg' and not parsed.netloc):
                raise HTTPException(422, 'URL кнопки должен начинаться с https://, http:// или tg://')
            row_out.append({'text': text, 'url': url})
        out.append(row_out)
    return out


def _save_version(cur, post_id: int, title: str, text: str, user_id: int | None) -> None:
    cur.execute('INSERT INTO cd_post_versions(post_id,title,text,created_by) VALUES(%s,%s,%s,%s)',
                (post_id, title, text, user_id))


@router.post('/workspaces/{workspace_id}/posts', status_code=201)
def create_post(workspace_id: int, payload: PostCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.create')
    if payload.status not in CREATABLE:
        raise HTTPException(422, 'Нельзя создать публикацию в этом статусе')
    buttons = _normalize_buttons(payload.buttons)
    with connect() as conn, conn.cursor() as cur:
        _ensure_channel(cur, workspace_id, payload.channel_id)
        cur.execute("""INSERT INTO cd_posts(workspace_id,channel_id,title,text,status,approval_required,scheduled_at,created_by,buttons)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                    (workspace_id, payload.channel_id, payload.title.strip(), payload.text,
                     payload.status, payload.approval_required, payload.scheduled_at, user['id'], json.dumps(buttons)))
        post = cur.fetchone()
        if payload.text:
            _save_version(cur, post['id'], post['title'], post['text'], user['id'])
        audit(cur, workspace_id, user['id'], 'post.created', 'post', post['id'])
        return post


@router.get('/workspaces/{workspace_id}/posts')
def list_posts(workspace_id: int, status: str | None = None, channel_id: int | None = None,
               date_from: datetime | None = None, date_to: datetime | None = None,
               limit: int = 100, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    limit = max(1, min(limit, 200))
    sql = """SELECT p.*, c.title AS channel_title, u.username AS author_username
             FROM cd_posts p LEFT JOIN cd_channels c ON c.id=p.channel_id
             LEFT JOIN cd_users u ON u.id=p.created_by
             WHERE p.workspace_id=%s"""
    params: list = [workspace_id]
    if status:
        if status not in ALLOWED_STATUSES:
            raise HTTPException(422, 'Неизвестный статус')
        sql += ' AND p.status=%s'
        params.append(status)
    if channel_id is not None:
        sql += ' AND p.channel_id=%s'
        params.append(channel_id)
    if date_from is not None:
        sql += ' AND p.scheduled_at >= %s'
        params.append(date_from)
    if date_to is not None:
        sql += ' AND p.scheduled_at <= %s'
        params.append(date_to)
    sql += ' ORDER BY p.updated_at DESC LIMIT %s'
    params.append(limit)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get('/workspaces/{workspace_id}/posts/{post_id}')
def get_post(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        cur.execute('SELECT * FROM cd_post_versions WHERE post_id=%s ORDER BY created_at DESC LIMIT 1', (post_id,))
        version = cur.fetchone()
    return {'post': post, 'latest_version': version}


@router.patch('/workspaces/{workspace_id}/posts/{post_id}')
def update_post(workspace_id: int, post_id: int, payload: PostUpdate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if member['role'] == 'author' and post['created_by'] != user['id']:
            raise HTTPException(403, 'Автор может редактировать только свои публикации')
        if post['status'] in PUBLISHED_LOCKED:
            raise HTTPException(422, 'Опубликованные и отменённые публикации не редактируются')
        if post['status'] not in EDITABLE:
            raise HTTPException(422, 'Редактировать можно только черновики (idea/draft/in_progress)')
        data = payload.model_dump(exclude_unset=True)
        if 'channel_id' in data:
            _ensure_channel(cur, workspace_id, data['channel_id'])
        if 'buttons' in data:
            data['buttons'] = json.dumps(_normalize_buttons(data['buttons']))
        fields, values = [], []
        for key in ('title', 'text', 'channel_id', 'scheduled_at', 'buttons'):
            if key in data:
                if key == 'buttons':
                    fields.append('buttons=%s::jsonb')
                else:
                    fields.append(f'{key}=%s')
                values.append(data[key])
        if not fields:
            return post
        old = post
        values.append(post_id)
        cur.execute(f"UPDATE cd_posts SET {','.join(fields)},updated_at=now() WHERE id=%s RETURNING *", values)
        updated = cur.fetchone()
        if 'text' in data and data['text'] != old['text']:
            _save_version(cur, post_id, updated['title'], updated['text'], user['id'])
        audit(cur, workspace_id, user['id'], 'post.updated', 'post', post_id)
        return updated


@router.post('/workspaces/{workspace_id}/posts/{post_id}/submit')
def submit_post(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if member['role'] == 'author' and post['created_by'] != user['id']:
            raise HTTPException(403, 'Автор может отправлять на согласование только свои публикации')
        if post['status'] not in {'draft', 'in_progress', 'changes_requested'}:
            raise HTTPException(422, 'Отправить на согласование можно только черновик')
        cur.execute("UPDATE cd_posts SET status='review',updated_at=now() WHERE id=%s RETURNING *", (post_id,))
        updated = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'post.submitted', 'post', post_id)
        return updated


@router.post('/workspaces/{workspace_id}/posts/{post_id}/approve')
def approve_post(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.review')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if post['status'] != 'review':
            raise HTTPException(422, 'Одобрить можно только публикацию на согласовании')
        cur.execute("UPDATE cd_posts SET status='approved',approved_by=%s,updated_at=now() WHERE id=%s RETURNING *",
                    (user['id'], post_id))
        updated = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'post.approved', 'post', post_id)
        return updated


@router.post('/workspaces/{workspace_id}/posts/{post_id}/request-changes')
def request_changes(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.review')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if post['status'] != 'review':
            raise HTTPException(422, 'Запросить изменения можно только у публикации на согласовании')
        cur.execute("UPDATE cd_posts SET status='changes_requested',updated_at=now() WHERE id=%s RETURNING *", (post_id,))
        updated = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'post.changes_requested', 'post', post_id)
        return updated


@router.post('/workspaces/{workspace_id}/posts/{post_id}/cancel')
def cancel_post(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if post['status'] in {'published', 'cancelled', 'publishing'}:
            raise HTTPException(422, 'Эту публикацию нельзя отменить')
        cur.execute("UPDATE cd_posts SET status='cancelled',updated_at=now() WHERE id=%s RETURNING *", (post_id,))
        updated = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'post.cancelled', 'post', post_id)
        return updated


@router.post('/workspaces/{workspace_id}/posts/{post_id}/schedule')
def schedule_post(workspace_id: int, post_id: int, payload: SchedulePayload, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.schedule')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if not post['channel_id']:
            raise HTTPException(422, 'Укажите канал перед планированием')
        # Планировать/публиковать можно:
        #  - одобренную публикацию;
        #  - уже запланированную (повторный «Опубликовать сейчас»);
        #  - упавшую (retry) или отменённую (возобновить);
        #  - черновик, если согласование выключено.
        reschedulable = {'approved', 'scheduled', 'failed', 'cancelled'}
        if post['status'] not in reschedulable:
            if post['status'] in {'draft', 'in_progress'} and not post['approval_required']:
                pass
            else:
                raise HTTPException(422, 'Опубликовать можно после одобрения: переведите пост на согласование и одобрьте его')
        scheduled_at = payload.scheduled_at or datetime.now(timezone.utc)
        # Сохраняем существующий publish_key (идемпотентность), сбрасываем счётчик попыток.
        publish_key = post.get('publish_key') or uuid.uuid4().hex
        cur.execute("""UPDATE cd_posts SET status='scheduled',scheduled_at=%s,publish_key=%s,
        last_error=NULL,attempt_count=0,updated_at=now() WHERE id=%s RETURNING *""",
                    (scheduled_at, publish_key, post_id))
        updated = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'post.scheduled', 'post', post_id, json.dumps({'scheduled_at': scheduled_at.isoformat()}))
        return updated


@router.post('/workspaces/{workspace_id}/posts/{post_id}/publish-now')
def publish_now(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    # Немедленная публикация = планирование на текущий момент: publisher-бот подхватит.
    return schedule_post(workspace_id, post_id, SchedulePayload(scheduled_at=None), user)


@router.post('/workspaces/{workspace_id}/posts/{post_id}/delete-from-telegram', status_code=202)
def request_delete_from_telegram(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    if member.get('role') == 'ad_manager':
        require_action(member, 'booking.manage')
    else:
        require_action(member, 'post.publish')
    with connect() as conn, conn.cursor() as cur:
        post = _get_post(cur, workspace_id, post_id)
        if post.get('status') != 'published' or not post.get('telegram_message_id') or not post.get('channel_id'):
            raise HTTPException(422, 'Удалить из Telegram можно только опубликованный пост с сообщением в канале')
        cur.execute('SELECT telegram_chat_id FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                    (post['channel_id'], workspace_id))
        channel = cur.fetchone()
        if not channel:
            raise HTTPException(422, 'Канал публикации не найден')
        cur.execute("""SELECT id,status FROM cd_telegram_delete_jobs
        WHERE post_id=%s AND status IN ('pending','processing') LIMIT 1""", (post_id,))
        existing = cur.fetchone()
        if existing:
            return {'id': existing['id'], 'status': existing['status'], 'message': 'Удаление уже стоит в очереди'}
        cur.execute("""INSERT INTO cd_telegram_delete_jobs(
            workspace_id,post_id,channel_id,telegram_chat_id,telegram_message_id,requested_by)
        VALUES(%s,%s,%s,%s,%s,%s) RETURNING id,status""",
                    (workspace_id, post_id, post['channel_id'], channel['telegram_chat_id'],
                     post['telegram_message_id'], user['id']))
        job = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'post.telegram_delete_requested', 'post', post_id)
    return {'id': job['id'], 'status': job['status'], 'message': 'Удаление будет выполнено ботом в ближайшем цикле'}


@router.get('/workspaces/{workspace_id}/posts/{post_id}/delete-from-telegram')
def delete_from_telegram_status(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        _get_post(cur, workspace_id, post_id)
        cur.execute("""SELECT id,status,error_text,created_at,completed_at
        FROM cd_telegram_delete_jobs WHERE workspace_id=%s AND post_id=%s
        ORDER BY created_at DESC LIMIT 1""", (workspace_id, post_id))
        job = cur.fetchone()
    return job or {'id': None, 'status': 'none', 'error_text': None, 'created_at': None, 'completed_at': None}


@router.get('/workspaces/{workspace_id}/posts/{post_id}/versions')
def post_versions(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        _get_post(cur, workspace_id, post_id)
        cur.execute('SELECT * FROM cd_post_versions WHERE post_id=%s ORDER BY created_at DESC', (post_id,))
        return cur.fetchall()


@router.get('/workspaces/{workspace_id}/posts/{post_id}/comments')
def post_comments(workspace_id: int, post_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        _get_post(cur, workspace_id, post_id)
        cur.execute("""SELECT cm.id,cm.post_id,cm.text,cm.created_at,u.username,u.first_name,u.last_name
        FROM cd_post_comments cm JOIN cd_users u ON u.id=cm.user_id
        WHERE cm.post_id=%s ORDER BY cm.created_at""", (post_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/posts/{post_id}/comments', status_code=201)
def add_comment(workspace_id: int, post_id: int, payload: CommentCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        _get_post(cur, workspace_id, post_id)
        cur.execute('INSERT INTO cd_post_comments(post_id,user_id,text) VALUES(%s,%s,%s) RETURNING *',
                    (post_id, user['id'], payload.text.strip()))
        return cur.fetchone()


# --- Шаблоны публикаций ---

@router.get('/workspaces/{workspace_id}/templates')
def list_templates(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM cd_post_templates WHERE workspace_id=%s ORDER BY name', (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/templates', status_code=201)
def create_template(workspace_id: int, payload: TemplateCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.create')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_post_templates(workspace_id,name,title,text,created_by)
        VALUES(%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace_id, payload.name.strip(), payload.title.strip(), payload.text, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'template.created', 'template', row['id'])
        return row


@router.delete('/workspaces/{workspace_id}/templates/{template_id}', status_code=204)
def delete_template(workspace_id: int, template_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM cd_post_templates WHERE id=%s AND workspace_id=%s', (template_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Шаблон не найден')
        cur.execute('DELETE FROM cd_post_templates WHERE id=%s', (template_id,))
        audit(cur, workspace_id, user['id'], 'template.deleted', 'template', template_id)
        return None
