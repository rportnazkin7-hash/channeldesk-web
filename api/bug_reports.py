from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['bug-reports'])


class BugCreate(BaseModel):
    description: str = Field(min_length=3, max_length=10000)
    screen: str = Field(default='', max_length=160)
    severity: Literal['low', 'normal', 'high', 'critical'] = 'normal'
    app_version: str = Field(default='', max_length=32)
    context: dict = Field(default_factory=dict)


class BugUpdate(BaseModel):
    status: Literal['new', 'in_progress', 'fixed', 'closed'] | None = None
    resolution: str | None = Field(default=None, max_length=4000)


def _notify_admins(workspace_id: int, report: dict) -> None:
    try:
        from api.telegram import _get_json
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT u.telegram_id FROM cd_workspace_members m
            JOIN cd_users u ON u.id=m.user_id
            WHERE m.workspace_id=%s AND m.status='active' AND m.role IN ('owner','admin')""",
                        (workspace_id,))
            recipients = cur.fetchall() or []
        text = f"🐞 Новая ошибка #{report['id']}\n{report['description'][:700]}"
        if report.get('screen'):
            text += f"\nЭкран: {report['screen']}"
        text += f"\nПриоритет: {report['severity']}\nИсточник: {report['source']}"
        for recipient in recipients:
            _get_json('sendMessage', {'chat_id': recipient['telegram_id'], 'text': text})
    except Exception:
        return


@router.get('/workspaces/{workspace_id}/bug-reports')
def list_bug_reports(workspace_id: int, limit: int = 100, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    limit = max(1, min(limit, 200))
    can_view_all = member.get('role') in {'owner', 'admin', 'editor', 'analyst'}
    with connect() as conn, conn.cursor() as cur:
        if can_view_all:
            cur.execute("""SELECT * FROM cd_bug_reports WHERE workspace_id=%s
            ORDER BY created_at DESC,id DESC LIMIT %s""", (workspace_id, limit))
        else:
            cur.execute("""SELECT * FROM cd_bug_reports WHERE workspace_id=%s AND user_id=%s
            ORDER BY created_at DESC,id DESC LIMIT %s""", (workspace_id, user['id'], limit))
        return cur.fetchall() or []


@router.post('/workspaces/{workspace_id}/bug-reports', status_code=201)
def create_bug_report(workspace_id: int, payload: BugCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'bug.create')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_bug_reports(
            workspace_id,user_id,telegram_id,username,first_name,description,screen,severity,source,app_version,context)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'mini_app',%s,%s::jsonb) RETURNING *""",
                    (workspace_id, user['id'], user.get('telegram_id'), user.get('username'), user.get('first_name'),
                     payload.description.strip(), payload.screen.strip(), payload.severity, payload.app_version.strip(),
                     json.dumps(payload.context)))
        report = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'bug_report.created', 'bug_report', report['id'])
    _notify_admins(workspace_id, report)
    return report


@router.patch('/workspaces/{workspace_id}/bug-reports/{report_id}')
def update_bug_report(workspace_id: int, report_id: int, payload: BugUpdate,
                      user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'bug.manage')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    fields, values = [], []
    for key in ('status', 'resolution'):
        if key in data:
            fields.append(f'{key}=%s')
            values.append(data[key])
    if data.get('status') in {'fixed', 'closed'}:
        fields.append('resolved_at=now()')
    elif data.get('status'):
        fields.append('resolved_at=NULL')
    values.extend([report_id, workspace_id])
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"""UPDATE cd_bug_reports SET {','.join(fields)},updated_at=now()
        WHERE id=%s AND workspace_id=%s RETURNING *""", values)
        report = cur.fetchone()
        if not report:
            raise HTTPException(404, 'Ошибка не найдена')
        audit(cur, workspace_id, user['id'], 'bug_report.updated', 'bug_report', report_id)
    return report
