from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['tasks'])

TASK_STATUSES = {'todo', 'in_progress', 'done', 'cancelled'}
PRIORITIES = {'low', 'normal', 'high', 'urgent'}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ''
    status: str = 'todo'
    priority: str = 'normal'
    assignee_id: int | None = None
    due_at: datetime | None = None
    remind_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee_id: int | None = None
    due_at: datetime | None = None
    remind_at: datetime | None = None


@router.get('/workspaces/{workspace_id}/tasks')
def list_tasks(workspace_id: int, status: str | None = None, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'task.view')
    sql = """SELECT t.*, u.username AS assignee_username, u.first_name AS assignee_first_name
             FROM cd_tasks t LEFT JOIN cd_users u ON u.id=t.assignee_id
             WHERE t.workspace_id=%s"""
    params: list = [workspace_id]
    if status:
        if status not in TASK_STATUSES:
            raise HTTPException(422, 'Неизвестный статус задачи')
        sql += ' AND t.status=%s'
        params.append(status)
    sql += ' ORDER BY t.due_at NULLS LAST, t.updated_at DESC'
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/tasks', status_code=201)
def create_task(workspace_id: int, payload: TaskCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'task.manage')
    if payload.status not in TASK_STATUSES:
        raise HTTPException(422, 'Неизвестный статус задачи')
    if payload.priority not in PRIORITIES:
        raise HTTPException(422, 'Неизвестный приоритет')
    with connect() as conn, conn.cursor() as cur:
        if payload.assignee_id is not None:
            cur.execute('SELECT id FROM cd_workspace_members WHERE workspace_id=%s AND user_id=%s AND status=%s',
                        (workspace_id, payload.assignee_id, 'active'))
            if not cur.fetchone():
                raise HTTPException(422, 'Исполнитель не является участником рабочего пространства')
        cur.execute("""INSERT INTO cd_tasks(workspace_id,title,description,status,priority,assignee_id,due_at,remind_at,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace_id, payload.title.strip(), payload.description, payload.status, payload.priority,
                     payload.assignee_id, payload.due_at, payload.remind_at, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'task.created', 'task', row['id'])
        return row


@router.patch('/workspaces/{workspace_id}/tasks/{task_id}')
def update_task(workspace_id: int, task_id: int, payload: TaskUpdate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'task.manage')
    if payload.status is not None and payload.status not in TASK_STATUSES:
        raise HTTPException(422, 'Неизвестный статус задачи')
    if payload.priority is not None and payload.priority not in PRIORITIES:
        raise HTTPException(422, 'Неизвестный приоритет')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    with connect() as conn, conn.cursor() as cur:
        if 'assignee_id' in data and data['assignee_id'] is not None:
            cur.execute('SELECT id FROM cd_workspace_members WHERE workspace_id=%s AND user_id=%s AND status=%s',
                        (workspace_id, data['assignee_id'], 'active'))
            if not cur.fetchone():
                raise HTTPException(422, 'Исполнитель не является участником рабочего пространства')
        fields, values = [], []
        for key in ('title', 'description', 'status', 'priority', 'assignee_id', 'due_at', 'remind_at'):
            if key in data:
                fields.append(f'{key}=%s')
                values.append(data[key])
        if 'status' in data and data['status'] == 'done':
            fields.append('completed_at=now()')
        values.extend([task_id, workspace_id])
        cur.execute(f"UPDATE cd_tasks SET {','.join(fields)},updated_at=now() WHERE id=%s AND workspace_id=%s RETURNING *",
                    values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Задача не найдена')
        audit(cur, workspace_id, user['id'], 'task.updated', 'task', task_id)
        return row


@router.post('/workspaces/{workspace_id}/tasks/{task_id}/done')
def complete_task(workspace_id: int, task_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'task.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE cd_tasks SET status='done',completed_at=now(),updated_at=now()
        WHERE id=%s AND workspace_id=%s RETURNING *""", (task_id, workspace_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Задача не найдена')
        audit(cur, workspace_id, user['id'], 'task.done', 'task', task_id)
        return row


@router.delete('/workspaces/{workspace_id}/tasks/{task_id}', status_code=204)
def delete_task(workspace_id: int, task_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'task.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM cd_tasks WHERE id=%s AND workspace_id=%s', (task_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Задача не найдена')
        cur.execute('DELETE FROM cd_tasks WHERE id=%s', (task_id,))
        audit(cur, workspace_id, user['id'], 'task.deleted', 'task', task_id)
        return None
