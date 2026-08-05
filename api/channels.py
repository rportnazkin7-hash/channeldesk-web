from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.telegram import verify_bot_permissions
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['channels'])


class ConnectChannel(BaseModel):
    connection_id: int


def _release_stale_connections(cur, actor_telegram_id: int) -> None:
    """Возвращает в список ожидания связи от удалённых/архивных рабочих пространств.

    Удаление рабочего пространства сейчас мягкое (is_active=false), поэтому
    старое событие my_chat_member может остаться со статусом connected. Канал
    при этом уже нельзя подключить к новому рабочему пространству без очистки.
    """
    cur.execute("""UPDATE cd_channel_connections cc
    SET status='pending',connected_channel_id=NULL,updated_at=now()
    WHERE cc.actor_telegram_id=%s AND cc.status='connected'
      AND (
        cc.connected_channel_id IS NULL
        OR EXISTS (
          SELECT 1
          FROM cd_channels c
          JOIN cd_workspaces w ON w.id=c.workspace_id
          WHERE c.id=cc.connected_channel_id
            AND (c.is_active=false OR w.is_active=false)
        )
      )""", (actor_telegram_id,))


@router.get('/channel-connections/pending')
def pending_connections(user: dict = Depends(current_user)):
    with connect() as conn, conn.cursor() as cur:
        _release_stale_connections(cur, user['telegram_id'])
        cur.execute("""SELECT id,telegram_chat_id,title,username,bot_permissions,observed_at
        FROM cd_channel_connections WHERE actor_telegram_id=%s AND status='pending' ORDER BY updated_at DESC""",
                    (user['telegram_id'],))
        return cur.fetchall()


@router.get('/workspaces/{workspace_id}/channels')
def list_channels(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'channel.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM cd_channels WHERE workspace_id=%s AND is_active=true ORDER BY title', (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/channels/connect', status_code=201)
def connect_channel(workspace_id: int, payload: ConnectChannel, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'channel.connect')
    with connect() as conn, conn.cursor() as cur:
        _release_stale_connections(cur, user['telegram_id'])
        cur.execute("""SELECT * FROM cd_channel_connections WHERE id=%s AND actor_telegram_id=%s AND status='pending' FOR UPDATE""",
                    (payload.connection_id, user['telegram_id']))
        pending = cur.fetchone()
        if not pending:
            raise HTTPException(404, 'Канал не найден. Переустановите права бота в канале')

        # Live-проверка прав непосредственно перед подключением (Этап A).
        permissions = dict(pending.get('bot_permissions') or {})
        live = verify_bot_permissions(pending['telegram_chat_id'])
        if live is None:
            # Проверка недоступна (dev-режим без BOT_TOKEN или сбой Telegram) —
            # доверяем правам, сохранённым при событии my_chat_member.
            if not permissions.get('can_post_messages'):
                raise HTTPException(422, 'Боту не выдано право публикации сообщений')
        else:
            if not live['is_admin']:
                raise HTTPException(422, 'Бот не является администратором канала. Добавьте бота в администраторы и попробуйте снова.')
            if not live['can_post_messages']:
                raise HTTPException(422, 'Боту не выдано право публикации сообщений')
            permissions = live['permissions']

        cur.execute("""SELECT c.id,c.workspace_id,c.is_active,w.is_active AS workspace_active
        FROM cd_channels c JOIN cd_workspaces w ON w.id=c.workspace_id
        WHERE c.telegram_chat_id=%s FOR UPDATE""", (pending['telegram_chat_id'],))
        existing = cur.fetchone()
        if existing and existing['workspace_id'] != workspace_id:
            if not existing['workspace_active']:
                # Старое рабочее пространство удалено мягко. Освобождаем его
                # канал, чтобы тот же Telegram-канал можно было подключить заново.
                cur.execute('DELETE FROM cd_channels WHERE id=%s', (existing['id'],))
                existing = None
            else:
                raise HTTPException(409, 'Канал уже подключён к другому рабочему пространству')
        if existing:
            cur.execute("""UPDATE cd_channels SET title=%s,username=%s,bot_permissions=%s::jsonb,is_connected=true,is_active=true,
            connected_by=%s,connected_at=now(),updated_at=now() WHERE id=%s RETURNING *""",
                        (pending['title'], pending['username'], json.dumps(permissions), user['id'], existing['id']))
        else:
            cur.execute("""INSERT INTO cd_channels(workspace_id,telegram_chat_id,title,username,bot_permissions,is_connected,connected_by,connected_at)
            VALUES(%s,%s,%s,%s,%s::jsonb,true,%s,now()) RETURNING *""",
                        (workspace_id, pending['telegram_chat_id'], pending['title'], pending['username'],
                         json.dumps(permissions), user['id']))
        channel = cur.fetchone()
        cur.execute("UPDATE cd_channel_connections SET status='connected',connected_channel_id=%s,updated_at=now() WHERE id=%s",
                    (channel['id'], pending['id']))
        cur.execute("""INSERT INTO cd_audit_log(workspace_id,user_id,action,entity_type,entity_id,details)
        VALUES(%s,%s,'channel.connected','channel',%s,%s::jsonb)""",
                    (workspace_id, user['id'], channel['id'], '{}'))
        return channel


@router.delete('/workspaces/{workspace_id}/channels/{channel_id}', status_code=204)
def delete_channel(workspace_id: int, channel_id: int, user: dict = Depends(current_user)):
    """Убирает канал из рабочего пространства без удаления самого Telegram-канала."""
    member = membership(user['id'], workspace_id)
    require_action(member, 'channel.connect')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,telegram_chat_id,title
        FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true FOR UPDATE""",
                    (channel_id, workspace_id))
        channel = cur.fetchone()
        if not channel:
            raise HTTPException(404, 'Канал не найден в этом рабочем пространстве')

        audit(cur, workspace_id, user['id'], 'channel.deleted', 'channel', channel_id,
              json.dumps({'telegram_chat_id': channel['telegram_chat_id']}))
        cur.execute("""UPDATE cd_channel_connections
        SET status='pending',connected_channel_id=NULL,updated_at=now()
        WHERE connected_channel_id=%s""", (channel_id,))
        # Мягкое удаление сохраняет связанные посты/размещения и позволяет
        # подключить этот же канал обратно в это рабочее пространство.
        cur.execute("""UPDATE cd_channels
        SET is_connected=false,is_active=false,updated_at=now()
        WHERE id=%s AND workspace_id=%s""", (channel_id, workspace_id))
    return None
