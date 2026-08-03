from __future__ import annotations
import os
import uuid
from pathlib import Path
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import current_user
from api.db import connect, database_url
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['assets'])

BUCKET = 'channeldesk-assets'
MAX_SIZE = 50 * 1024 * 1024  # 50 МБ


class UploadUrlRequest(BaseModel):
    post_id: int | None = None
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = 'application/octet-stream'
    size: int = Field(default=0, ge=0)


class AttachAssetRequest(BaseModel):
    post_id: int


def storage_base_url() -> str:
    url = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    if not url:
        raise HTTPException(503, 'SUPABASE_URL не задан на Vercel (Settings → Environment Variables)')
    return url


def anon_key() -> str:
    key = os.getenv('SUPABASE_ANON_KEY', '').strip()
    if not key:
        raise HTTPException(503, 'SUPABASE_ANON_KEY не задан на Vercel — публичный anon-ключ из Supabase → Settings → API')
    return key


def public_file_url(path: str) -> str:
    return f'{storage_base_url()}/storage/v1/object/public/{BUCKET}/{path}'


def ensure_bucket() -> None:
    """Создаёт bucket и RLS-политику для прямой загрузки из браузера.

    Работает через БД (psycopg) — Storage API из Vercel недоступен ([Errno 16] EBUSY).
    Политики разрешают только INSERT анонимам в этот bucket; список/удаление
    идут через backend (который проверяет права).
    """
    try:
        url = database_url()
    except Exception:
        return
    statements = [
        "INSERT INTO storage.buckets (id, name, public) VALUES ('channeldesk-assets','channeldesk-assets',true) "
        "ON CONFLICT (id) DO NOTHING",
        "ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY",
        """DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects'
                         AND policyname='cd_anon_upload') THEN
            CREATE POLICY "cd_anon_upload" ON storage.objects FOR INSERT TO anon
            WITH CHECK (bucket_id = 'channeldesk-assets');
          END IF;
        END $$;""",
    ]
    try:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
    except Exception:
        pass  # не критично при старте; конкретный upload покажет точную причину


@router.post('/workspaces/{workspace_id}/assets/upload-url', status_code=201)
def create_upload_url(workspace_id: int, payload: UploadUrlRequest, user: dict = Depends(current_user)):
    """Выдаёт клиенту адрес для прямой загрузки в Supabase Storage (из браузера)."""
    member = membership(user['id'], workspace_id)
    require_action(member, 'post.edit')
    if payload.size > MAX_SIZE:
        raise HTTPException(413, 'Файл больше 50 МБ')
    if payload.post_id is not None:
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT id FROM cd_posts WHERE id=%s AND workspace_id=%s', (payload.post_id, workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Публикация не принадлежит этому рабочему пространству')
    ext = Path(payload.file_name).suffix.lower() or ''
    path = f'{workspace_id}/{uuid.uuid4().hex}{ext}'
    file_url = public_file_url(path)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_content_assets(workspace_id,post_id,file_name,file_type,file_url,size_bytes,uploaded_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace_id, payload.post_id, payload.file_name, payload.content_type,
                     file_url, payload.size, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'asset.upload_started', 'asset', row['id'])
    return {
        'asset_id': row['id'],
        'file_url': file_url,
        'upload_url': f"{storage_base_url()}/storage/v1/object/{BUCKET}/{path}",
        'anon_key': anon_key(),
        'bucket': BUCKET,
    }


@router.patch('/assets/{asset_id}/post', status_code=200)
def attach_asset(asset_id: int, payload: AttachAssetRequest, user: dict = Depends(current_user)):
    """Привязывает ранее созданное вложение к посту (если post_id не был указан при создании)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT a.*, wm.workspace_id FROM cd_content_assets a
        JOIN cd_workspace_members wm ON wm.workspace_id=a.workspace_id AND wm.user_id=%s AND wm.status='active'
        WHERE a.id=%s""", (user['id'], asset_id))
        asset = cur.fetchone()
        if not asset:
            raise HTTPException(404, 'Вложение не найдено')
        cur.execute('SELECT role FROM cd_workspace_members WHERE workspace_id=%s AND user_id=%s AND status=%s',
                    (asset['workspace_id'], user['id'], 'active'))
        require_action({'role': cur.fetchone()['role']}, 'post.edit')
        cur.execute('SELECT id FROM cd_posts WHERE id=%s AND workspace_id=%s', (payload.post_id, asset['workspace_id']))
        if not cur.fetchone():
            raise HTTPException(422, 'Публикация не принадлежит этому рабочему пространству')
        cur.execute('UPDATE cd_content_assets SET post_id=%s WHERE id=%s RETURNING *', (payload.post_id, asset_id))
        return cur.fetchone()


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
    """Удаляет запись и объект из storage (через БД — Storage API из Vercel недоступен)."""
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
        marker = f'/object/public/{BUCKET}/'
        if marker in asset['file_url']:
            path = asset['file_url'].split(marker, 1)[1]
            try:
                cur.execute("DELETE FROM storage.objects WHERE bucket_id=%s AND name=%s", (BUCKET, path))
            except Exception:
                pass  # удаляем запись, даже если объект не удалился
        cur.execute('DELETE FROM cd_content_assets WHERE id=%s', (asset_id,))
        audit(cur, asset['workspace_id'], user['id'], 'asset.deleted', 'asset', asset_id)
        return None
