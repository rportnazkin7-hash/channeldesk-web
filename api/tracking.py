from __future__ import annotations

import hashlib
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['tracking'])


class TrackingLinkCreate(BaseModel):
    channel_id: int
    booking_id: int | None = None
    name: str = Field(min_length=1, max_length=160)
    target_url: str = Field(min_length=1, max_length=2048)
    notes: str = Field(default='', max_length=2000)


def _target_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(422, 'Целевая ссылка должна начинаться с https:// или http://')
    return url


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get('/workspaces/{workspace_id}/tracking-links')
def list_tracking_links(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT l.id,l.name,l.url AS target_url,l.clicks,l.notes,l.is_active,
        l.channel_id,l.booking_id,c.title AS channel_title,a.name AS advertiser_name
        FROM cd_channel_links l
        JOIN cd_channels c ON c.id=l.channel_id
        LEFT JOIN cd_ad_bookings b ON b.id=l.booking_id
        LEFT JOIN cd_advertisers a ON a.id=b.advertiser_id
        WHERE l.workspace_id=%s AND l.is_active=true AND l.tracking_token_hash IS NOT NULL
        ORDER BY l.created_at DESC,l.id DESC""", (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/tracking-links', status_code=201)
def create_tracking_link(workspace_id: int, payload: TrackingLinkCreate,
                         user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    target = _target_url(payload.target_url)
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                    (payload.channel_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')
        if payload.booking_id is not None:
            cur.execute('SELECT id,channel_id FROM cd_ad_bookings WHERE id=%s AND workspace_id=%s',
                        (payload.booking_id, workspace_id))
            booking = cur.fetchone()
            if not booking:
                raise HTTPException(422, 'Бронь не принадлежит этому рабочему пространству')
            if booking.get('channel_id') and booking['channel_id'] != payload.channel_id:
                raise HTTPException(422, 'Канал ссылки не совпадает с каналом брони')
        token = secrets.token_urlsafe(24)
        cur.execute("""INSERT INTO cd_channel_links(
            workspace_id,channel_id,booking_id,name,url,notes,tracking_token_hash,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,name,url AS target_url,clicks""",
                    (workspace_id, payload.channel_id, payload.booking_id, payload.name.strip(), target,
                     payload.notes.strip(), _hash(token), user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'tracking_link.created', 'channel_link', row['id'])
    return {**row, 'path': f'/api/r/{token}', 'source': 'channel_desk'}


@router.delete('/workspaces/{workspace_id}/tracking-links/{link_id}', status_code=204)
def deactivate_tracking_link(workspace_id: int, link_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_channel_links SET is_active=false,updated_at=now()
        WHERE id=%s AND workspace_id=%s AND tracking_token_hash IS NOT NULL RETURNING id""",
                    (link_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Ссылка не найдена')
        audit(cur, workspace_id, user['id'], 'tracking_link.deactivated', 'channel_link', link_id)
        return None


@router.get('/r/{token}')
def redirect_tracking_link(token: str):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,url AS target_url FROM cd_channel_links
        WHERE tracking_token_hash=%s AND is_active=true AND tracking_token_hash IS NOT NULL""",
                    (_hash(token),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Ссылка не найдена или отключена')
        cur.execute('UPDATE cd_channel_links SET clicks=clicks+1,updated_at=now() WHERE id=%s', (row['id'],))
    return RedirectResponse(row['target_url'], status_code=307)
