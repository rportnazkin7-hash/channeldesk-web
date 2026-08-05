from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['reports'])


class PublicReportCreate(BaseModel):
    expires_in_days: int = Field(default=30, ge=1, le=365)


class PublicFeedbackCreate(BaseModel):
    decision: Literal['approved', 'changes_requested']
    comment: str = Field(default='', max_length=4000)


def _digest(token: str) -> str:
    return hashlib.sha256(token.strip().encode()).hexdigest()


def _load_report(cur, token: str) -> dict:
    cur.execute("""SELECT r.id,r.workspace_id,r.advertiser_id,r.expires_at,
    a.name AS advertiser_name
    FROM cd_public_reports r JOIN cd_advertisers a ON a.id=r.advertiser_id
    WHERE r.token_hash=%s AND r.is_active=true""", (_digest(token),))
    report = cur.fetchone()
    if not report:
        raise HTTPException(404, 'Отчёт не найден или ссылка отключена')
    if report['expires_at'] <= datetime.now(timezone.utc):
        raise HTTPException(410, 'Срок действия ссылки истёк')
    return report


@router.post('/workspaces/{workspace_id}/advertisers/{advertiser_id}/public-report', status_code=201)
def create_public_report(workspace_id: int, advertiser_id: int, payload: PublicReportCreate,
                         user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'advertiser.manage')
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id,name FROM cd_advertisers WHERE id=%s AND workspace_id=%s AND is_active=true',
                    (advertiser_id, workspace_id))
        advertiser = cur.fetchone()
        if not advertiser:
            raise HTTPException(404, 'Рекламодатель не найден')
        cur.execute("""INSERT INTO cd_public_reports(workspace_id,advertiser_id,token_hash,expires_at,created_by)
        VALUES(%s,%s,%s,%s,%s) RETURNING id,expires_at""",
                    (workspace_id, advertiser_id, _digest(token), expires_at, user['id']))
        report = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'advertiser.report.created', 'public_report', report['id'])
    return {'id': report['id'], 'advertiser_name': advertiser['name'],
            'path': f'/public-report?token={token}', 'expires_at': report['expires_at']}


@router.delete('/workspaces/{workspace_id}/advertisers/{advertiser_id}/public-report', status_code=204)
def revoke_public_report(workspace_id: int, advertiser_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'advertiser.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_public_reports SET is_active=false
        WHERE workspace_id=%s AND advertiser_id=%s AND is_active=true""", (workspace_id, advertiser_id))
        audit(cur, workspace_id, user['id'], 'advertiser.report.revoked', 'advertiser', advertiser_id)
        return None


@router.get('/public/reports/{token}')
def get_public_report(token: str):
    now = datetime.now(timezone.utc)
    with connect() as conn, conn.cursor() as cur:
        report = _load_report(cur, token)
        cur.execute("""UPDATE cd_public_reports SET last_accessed_at=now() WHERE id=%s""", (report['id'],))
        cur.execute("""SELECT b.id,b.post_id,b.format,b.cost,b.currency,b.status,b.payment_status,
        b.publish_at,b.delete_at,c.title AS channel_title,p.title AS post_title,
        p.text AS post_text,p.status AS post_status
        FROM cd_ad_bookings b
        LEFT JOIN cd_channels c ON c.id=b.channel_id
        LEFT JOIN cd_posts p ON p.id=b.post_id
        WHERE b.workspace_id=%s AND b.advertiser_id=%s
        ORDER BY b.publish_at DESC NULLS LAST,b.id DESC""",
                    (report['workspace_id'], report['advertiser_id']))
        bookings = cur.fetchall() or []
        cur.execute("""SELECT l.id,l.name,l.url AS target_url,l.clicks,
        l.booking_id,c.title AS channel_title
        FROM cd_channel_links l
        JOIN cd_ad_bookings b ON b.id=l.booking_id
        LEFT JOIN cd_channels c ON c.id=l.channel_id
        WHERE l.workspace_id=%s AND b.advertiser_id=%s
          AND l.is_active=true AND l.tracking_token_hash IS NOT NULL
        ORDER BY l.created_at DESC,l.id DESC""",
                    (report['workspace_id'], report['advertiser_id']))
        links = cur.fetchall() or []
        cur.execute("""SELECT booking_id,decision,comment,created_at
        FROM cd_public_report_feedback WHERE report_id=%s ORDER BY created_at DESC""", (report['id'],))
        feedback = cur.fetchall() or []
    return {'advertiser_name': report['advertiser_name'], 'expires_at': report['expires_at'],
            'bookings': bookings, 'links': links, 'feedback': feedback, 'generated_at': now}


@router.post('/public/reports/{token}/bookings/{booking_id}/feedback', status_code=201)
def create_public_feedback(token: str, booking_id: int, payload: PublicFeedbackCreate):
    if payload.decision == 'changes_requested' and not payload.comment.strip():
        raise HTTPException(422, 'Напишите, какие изменения нужны')
    with connect() as conn, conn.cursor() as cur:
        report = _load_report(cur, token)
        cur.execute("""SELECT b.id,b.workspace_id,b.advertiser_id,b.post_id,p.status AS post_status
        FROM cd_ad_bookings b LEFT JOIN cd_posts p ON p.id=b.post_id
        WHERE b.id=%s AND b.workspace_id=%s AND b.advertiser_id=%s""",
                    (booking_id, report['workspace_id'], report['advertiser_id']))
        booking = cur.fetchone()
        if not booking:
            raise HTTPException(404, 'Размещение не найдено в этом отчёте')
        cur.execute("""INSERT INTO cd_public_report_feedback(
            report_id,workspace_id,advertiser_id,booking_id,post_id,decision,comment)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id,decision,comment,created_at""",
                    (report['id'], report['workspace_id'], report['advertiser_id'], booking_id,
                     booking['post_id'], payload.decision, payload.comment.strip()))
        feedback = cur.fetchone()
        if booking.get('post_id') and booking.get('post_status') == 'review':
            next_status = 'approved' if payload.decision == 'approved' else 'changes_requested'
            cur.execute("""UPDATE cd_posts SET status=%s,updated_at=now() WHERE id=%s""",
                        (next_status, booking['post_id']))
    return feedback
