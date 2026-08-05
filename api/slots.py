from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import date, datetime, time, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['public_slots'])
BLOCKING = ('requested', 'confirmed', 'active')
FORMATS = {'post', 'mention', 'repost', 'other'}


class SlotPageCreate(BaseModel):
    title: str = Field(default='Рекламные размещения', min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    default_cost: float = Field(default=0, ge=0)
    currency: str = Field(default='RUB', min_length=1, max_length=8)


class SlotRequestCreate(BaseModel):
    contact_name: str = Field(min_length=1, max_length=160)
    contact_telegram: str = Field(default='', max_length=160)
    contact_email: str = Field(default='', max_length=255)
    target_url: str = Field(default='', max_length=2048)
    format: str = 'post'
    start_date: date
    end_date: date
    comment: str = Field(default='', max_length=4000)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _target_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ''
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(422, 'Ссылка должна начинаться с https:// или http://')
    return value


def _dates(start: date, end: date) -> tuple[datetime, datetime]:
    start_at = datetime.combine(start, time(12, 0), tzinfo=timezone.utc)
    end_at = datetime.combine(end, time(12, 0), tzinfo=timezone.utc)
    if end_at < start_at:
        raise HTTPException(422, 'Дата окончания не может быть раньше даты начала')
    return start_at, end_at


@router.post('/workspaces/{workspace_id}/channels/{channel_id}/public-slots', status_code=201)
def create_slot_page(workspace_id: int, channel_id: int, payload: SlotPageCreate,
                     user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    token = secrets.token_urlsafe(28)
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id,title FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                    (channel_id, workspace_id))
        channel = cur.fetchone()
        if not channel:
            raise HTTPException(404, 'Канал не найден')
        cur.execute("""INSERT INTO cd_public_slot_pages(
            workspace_id,channel_id,token_hash,title,description,default_cost,currency,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (workspace_id, channel_id, _hash(token), payload.title.strip(), payload.description.strip(),
                     payload.default_cost, payload.currency.upper(), user['id']))
        page = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'public_slots.created', 'public_slot_page', page['id'])
    return {'id': page['id'], 'channel_title': channel['title'], 'path': f'/public-slots?token={token}'}


@router.delete('/workspaces/{workspace_id}/public-slots/{page_id}', status_code=204)
def revoke_slot_page(workspace_id: int, page_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('UPDATE cd_public_slot_pages SET is_active=false,updated_at=now() WHERE id=%s AND workspace_id=%s RETURNING id',
                    (page_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Витрина не найдена')
        audit(cur, workspace_id, user['id'], 'public_slots.revoked', 'public_slot_page', page_id)
        return None


@router.get('/public/slots/{token}')
def get_slot_page(token: str):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.id,p.workspace_id,p.channel_id,p.title,p.description,p.default_cost,p.currency,
        c.title AS channel_title,c.username
        FROM cd_public_slot_pages p JOIN cd_channels c ON c.id=p.channel_id
        WHERE p.token_hash=%s AND p.is_active=true AND c.is_active=true""", (_hash(token),))
        page = cur.fetchone()
        if not page:
            raise HTTPException(404, 'Витрина не найдена или отключена')
        cur.execute("""SELECT publish_at,delete_at,status FROM cd_ad_bookings
        WHERE workspace_id=%s AND channel_id=%s AND status IN ('requested','confirmed','active')
        AND publish_at IS NOT NULL ORDER BY publish_at""", (page['workspace_id'], page['channel_id']))
        busy = cur.fetchall() or []
    return {**page, 'busy': busy, 'formats': ['post', 'mention', 'repost']}


@router.post('/public/slots/{token}/request', status_code=201)
def create_slot_request(token: str, payload: SlotRequestCreate):
    if payload.format not in FORMATS:
        raise HTTPException(422, 'Неизвестный формат размещения')
    start_at, end_at = _dates(payload.start_date, payload.end_date)
    target = _target_url(payload.target_url)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.*,c.title AS channel_title FROM cd_public_slot_pages p
        JOIN cd_channels c ON c.id=p.channel_id
        WHERE p.token_hash=%s AND p.is_active=true AND c.is_active=true""", (_hash(token),))
        page = cur.fetchone()
        if not page:
            raise HTTPException(404, 'Витрина не найдена или отключена')
        cur.execute("""SELECT b.id,a.name AS advertiser_name FROM cd_ad_bookings b
        LEFT JOIN cd_advertisers a ON a.id=b.advertiser_id
        WHERE b.workspace_id=%s AND b.channel_id=%s AND b.status IN ('requested','confirmed','active')
          AND b.publish_at IS NOT NULL AND b.publish_at < %s
          AND COALESCE(b.delete_at,b.publish_at+interval '7 days') > %s LIMIT 1""",
                    (page['workspace_id'], page['channel_id'], end_at, start_at))
        if cur.fetchone():
            raise HTTPException(409, 'Выбранный период уже занят. Обновите страницу и выберите другие даты.')
        contact = {'telegram': payload.contact_telegram.strip(), 'email': payload.contact_email.strip()}
        cur.execute("""SELECT id FROM cd_advertisers WHERE workspace_id=%s AND name=%s AND is_active=true LIMIT 1""",
                    (page['workspace_id'], payload.contact_name.strip()))
        advertiser = cur.fetchone()
        if advertiser:
            advertiser_id = advertiser['id']
        else:
            cur.execute("""INSERT INTO cd_advertisers(workspace_id,name,contact,notes,is_active)
            VALUES(%s,%s,%s::jsonb,%s,true) RETURNING id""",
                        (page['workspace_id'], payload.contact_name.strip(), json.dumps(contact), 'Заявка с публичной витрины'))
            advertiser_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO cd_ad_bookings(
            workspace_id,advertiser_id,channel_id,format,cost,currency,status,payment_status,publish_at,delete_at,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,'requested','unpaid',%s,%s,NULL) RETURNING id""",
                    (page['workspace_id'], advertiser_id, page['channel_id'], payload.format,
                     page['default_cost'], page['currency'], start_at, end_at))
        booking_id = cur.fetchone()['id']
        publish_key = uuid.uuid4().hex
        cur.execute("""INSERT INTO cd_posts(workspace_id,channel_id,title,text,status,approval_required,scheduled_at,publish_key)
        VALUES(%s,%s,%s,%s,'draft',false,%s,%s) RETURNING id""",
                    (page['workspace_id'], page['channel_id'], f'Реклама: {payload.contact_name.strip()}',
                     f'Рекламный пост для {payload.contact_name.strip()}\n{target}', start_at, publish_key))
        post_id = cur.fetchone()['id']
        cur.execute('UPDATE cd_ad_bookings SET post_id=%s WHERE id=%s', (post_id, booking_id))
        cur.execute("""INSERT INTO cd_public_slot_requests(
            page_id,workspace_id,channel_id,booking_id,contact_name,contact_telegram,contact_email,target_url,format,comment)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (page['id'], page['workspace_id'], page['channel_id'], booking_id, payload.contact_name.strip(),
                     payload.contact_telegram.strip(), payload.contact_email.strip(), target, payload.format, payload.comment.strip()))
        request_id = cur.fetchone()['id']
    return {'request_id': request_id, 'booking_id': booking_id, 'post_id': post_id,
            'message': 'Заявка отправлена. Менеджер свяжется с вами.'}
