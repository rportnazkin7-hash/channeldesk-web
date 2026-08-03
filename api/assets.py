from __future__ import annotations
import os
import uuid
from pathlib import Path
import httpx
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


def ensure_bucket() -> None:
    """Идемпотентно создаёт публичный bucket (пропускает, если env не настроены)."""
    try:
        url, key = storage_config()
    except HTTPException:
        return
    try:
        with httpx.Client(timeout=15) as client:
            client.post(f'{url}/storage/v1/bucket',
                        headers={'Authorization': f'Bearer {key}'},
                        json={'name': BUCKET, 'public': True})
            # 400 «already exists» — допустимо; другие ошибки игнорируем,
            # т.к. первый upload всё равно покажет точную причину.
    except Exception:
        pass


@router.post('/workspaces/{workspace_id}/assets', status_code=201)
async def upload_asset(workspace_id: int,
                       file: UploadFile = File(...),
                       post_id: int | None = Form(default=None),
                       user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    data = await file.read()
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
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(f'{url}/storage/v1/object/{BUCKET}/{storage_path}',
                               headers={'Authorization': f'Bearer {key}',
                                        'Content-Type': file.content_type or 'application/octet-stream'},
                               content=data)
    except Exception as exc:
        raise HTTPException(503, f'Ошибка загрузки в хранилище: {exc}')
    if resp.status_code not in (200, 201):
        raise HTTPException(502, f'Хранилище вернуло ошибку {resp.status_code}: {resp.text[:200]}')
    file_url = public_file_url(url, storage_path)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_content_assets(workspace_id,post_id,file_name,file_type,file_url,size_bytes,uploaded_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace_id, post_id, file.filename or 'file', file.content_type or 'application/octet-stream',
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
                with httpx.Client(timeout=30) as client:
                    client.delete(f'{url}/storage/v1/object/{BUCKET}/{path}',
                                  headers={'Authorization': f'Bearer {key}'})
            except Exception:
                pass  # удаляем запись, даже если storage недоступен
        cur.execute('DELETE FROM cd_content_assets WHERE id=%s', (asset_id,))
        audit(cur, asset['workspace_id'], user['id'], 'asset.deleted', 'asset', asset_id)
        return None
