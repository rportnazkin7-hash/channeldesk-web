from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['media_kits'])


class MediaKitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    channel_id: int | None = None
    description: str = ''
    audience: dict = Field(default_factory=dict)
    stats: dict = Field(default_factory=dict)
    pricing: list = Field(default_factory=list)
    contacts: dict = Field(default_factory=dict)


class MediaKitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    channel_id: int | None = None
    description: str | None = None
    audience: dict | None = None
    stats: dict | None = None
    pricing: list | None = None
    contacts: dict | None = None
    is_active: bool | None = None


@router.get('/workspaces/{workspace_id}/media-kits')
def list_media_kits(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'media_kit.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT mk.*, c.title AS channel_title
        FROM cd_media_kits mk LEFT JOIN cd_channels c ON c.id=mk.channel_id
        WHERE mk.workspace_id=%s ORDER BY mk.name""", (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/media-kits', status_code=201)
def create_media_kit(workspace_id: int, payload: MediaKitCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'media_kit.manage')
    with connect() as conn, conn.cursor() as cur:
        if payload.channel_id is not None:
            cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s',
                        (payload.channel_id, workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')
        cur.execute("""INSERT INTO cd_media_kits(workspace_id,name,channel_id,description,audience,stats,pricing,contacts,created_by)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s) RETURNING *""",
                    (workspace_id, payload.name.strip(), payload.channel_id, payload.description,
                     json.dumps(payload.audience), json.dumps(payload.stats),
                     json.dumps(payload.pricing), json.dumps(payload.contacts), user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'media_kit.created', 'media_kit', row['id'])
        return row


@router.patch('/workspaces/{workspace_id}/media-kits/{kit_id}')
def update_media_kit(workspace_id: int, kit_id: int, payload: MediaKitUpdate,
                     user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'media_kit.manage')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    with connect() as conn, conn.cursor() as cur:
        if 'channel_id' in data and data['channel_id'] is not None:
            cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s',
                        (data['channel_id'], workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')
        fields, values = [], []
        for key in ('name', 'channel_id', 'description', 'is_active'):
            if key in data:
                fields.append(f'{key}=%s')
                values.append(data[key])
        for key in ('audience', 'stats', 'pricing', 'contacts'):
            if key in data:
                fields.append(f'{key}=%s::jsonb')
                values.append(json.dumps(data[key]))
        values.extend([kit_id, workspace_id])
        cur.execute(f"UPDATE cd_media_kits SET {','.join(fields)},updated_at=now() WHERE id=%s AND workspace_id=%s RETURNING *",
                    values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Медиакит не найден')
        audit(cur, workspace_id, user['id'], 'media_kit.updated', 'media_kit', kit_id)
        return row


@router.delete('/workspaces/{workspace_id}/media-kits/{kit_id}', status_code=204)
def delete_media_kit(workspace_id: int, kit_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'media_kit.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM cd_media_kits WHERE id=%s AND workspace_id=%s', (kit_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Медиакит не найден')
        cur.execute('DELETE FROM cd_media_kits WHERE id=%s', (kit_id,))
        audit(cur, workspace_id, user['id'], 'media_kit.deleted', 'media_kit', kit_id)
        return None
