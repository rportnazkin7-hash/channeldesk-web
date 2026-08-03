from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['assets'])

BUCKET = 'channeldesk-assets'
MAX_SIZE = 50 * 1024 * 1024  # 50 МБ на файл


def storage_config() -> tuple[str, str]:
    url = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()
    if not url or not key:
        raise HTTPException(503, 'Хранилище не настроено: добавьте SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в переменные окружения Vercel')
    return url, key


def public_file_url(supabase_url: str, path: str) -> str:
    return f'{supabase_url}/storage/v1/object/public/{BUCKET}/{path}'


def storage_path_from_url(file_url: str) -> str | None:
    marker = f'/object/public/{BUCKET}/'
    if marker in file_url:
        return file_url.split(marker, 1)[1]
    return None


def _storage_post_object(url: str, key: str, bucket: str, path: str, content_type: str, data: bytes) -> None:
    """Загрузка файла в Supabase Storage. Только байты в памяти — без temp-файлов."""
    req = urllib.request.Request(
        f'{url}/storage/v1/object/{bucket}/{path}',
        data=data,
        method='POST',
        headers={'Authorization': f'Bearer {key}',
                 'Content-Type': content_type,
                 'Content-Length': str(len(data))},
    )
    with urllib.request.urlopen(req, timeout=120):
        pass


def _storage_delete_object(url: str, key: str, bucket: str, path: str) -> None:
    req = urllib.request.Request(
        f'{url}/storage/v1/object/{bucket}/{path}',
        method='DELETE',
        headers={'Authorization': f'Bearer {key}'},
    )
    with urllib.request.urlopen(req, timeout=30):
        pass


def _storage_create_bucket(url: str, key: str) -> None:
    body = json.dumps({'name': BUCKET, 'public': True}).encode('utf-8')
    req = urllib.request.Request(
        f'{url}/storage/v1/bucket',
        data=body,
        method='POST',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=15):
        pass


def ensure_bucket() -> None:
    """Идемпотентно создаёт публичный bucket (пропускает, если env не настроены)."""
    try:
        url, key = storage_config()
    except HTTPException:
        return
    try:
        _storage_create_bucket(url, key)
    except Exception:
        pass  # «already exists» и прочие ошибки не критичны — upload покажет точную причину


@router.post('/workspaces/{workspace_id}/assets', status_code=201)
async def upload_asset(workspace_id: int,
                       file: UploadFile = File(...),
                       post_id: int | None = Form(default=None),
                       user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    data = await file.read()
    await file.close()  # освобождаем spooled-файл сразу, не дожидаясь GC
    if not data:
        raise HTTPException(422, 'Пустой файл')
    if len(data) > MAX_SIZE:
        raise HTTPException(413, 'Файл больше 50 МБ')
    url, key = storage_config()
    if post_id is not None:
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT id FROM cd_posts WHERE id=%s AND workspace_id=%s', (post_id, workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Публикация не принадлежит этому рабочему пространству')
    ext = Path(file.filename or 'file').suffix.lower() or ''
    storage_path = f'{workspace_id}/{uuid.uuid4().hex}{ext}'
    content_type = file.content_type or 'application/octet-stream'
    try:
        _storage_post_object(url, key, BUCKET, storage_path, content_type, data)
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode('utf-8', 'replace')
        raise HTTPException(502, f'Хранилище вернуло ошибку {exc.code}: {body}')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(503, f'Сеть до хранилища недоступна: {exc}')
    file_url = public_file_url(url, storage_path)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_content_assets(workspace_id,post_id,file_name,file_type,file_url,size_bytes,uploaded_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace_id, post_id, file.filename or 'file', content_type,
                     file_url, len(data), user['id']))
        row = cur.fetchone()
        if post_id:
            audit(cur, workspace_id, user['id'], 'asset.uploaded', 'asset', row['id'])
        return row


@router.get('/workspaces/{workspace_id}/assets')
def list_assets(workspace_id: int, post_id: int | None = None, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.view')
    with connect() as conn, conn.cursor() as cur:
        if post_id is not None:
            cur.execute('SELECT * FROM cd_content_assets WHERE workspace_id=%s AND post_id=%s ORDER BY created_at',
                        (workspace_id, post_id))
        else:
            cur.execute('SELECT * FROM cd_content_assets WHERE workspace_id=%s ORDER BY created_at DESC', (workspace_id,))
        return cur.fetchall()


@router.delete('/assets/{asset_id}', status_code=204)
def delete_asset(asset_id: int, user: dict = Depends(current_user)):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT a.*, wm.workspace_id FROM cd_content_assets a
        JOIN cd_workspace_members wm ON wm.workspace_id=a.workspace_id AND wm.user_id=%s AND wm.status='active'
        WHERE a.id=%s""", (user['id'], asset_id))
        asset = cur.fetchone()
        if not asset:
            raise HTTPException(404, 'Вложение не найдено')
        cur.execute('SELECT role FROM cd_workspace_members WHERE workspace_id=%s AND user_id=%s AND status=%s',
                    (asset['workspace_id'], user['id'], 'active'))
        role_row = cur.fetchone()
        require_action({'role': role_row['role']}, 'post.edit')
        path = storage_path_from_url(asset['file_url'])
        if path:
            try:
                url, key = storage_config()
                _storage_delete_object(url, key, BUCKET, path)
            except Exception:
                pass  # удаляем запись, даже если storage недоступен
        cur.execute('DELETE FROM cd_content_assets WHERE id=%s', (asset_id,))
        audit(cur, asset['workspace_id'], user['id'], 'asset.deleted', 'asset', asset_id)
        return None
