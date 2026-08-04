from __future__ import annotations

import json
import os
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from api.db import connect
from api.workspaces import audit

TGSTAT_API = 'https://api.tgstat.ru'


def _number(value, integer: bool = False):
    try:
        parsed = float(value or 0)
        return int(round(parsed)) if integer else parsed
    except (TypeError, ValueError):
        return 0 if integer else 0.0


def _request(channel_id: str) -> dict:
    token = os.getenv('TGSTAT_API_TOKEN', '').strip()
    if not token:
        raise HTTPException(503, 'TGSTAT_API_TOKEN не настроен на Vercel')
    query = urlencode({'token': token, 'channelId': channel_id})
    request = Request(f'{TGSTAT_API}/channels/stat?{query}', headers={'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raise HTTPException(502, f'TGStat не ответил: HTTP {exc.code}') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(502, 'TGStat временно недоступен') from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(502, 'TGStat вернул некорректный ответ') from exc
    if payload.get('status') != 'ok' or not isinstance(payload.get('response'), dict):
        message = str(payload.get('error') or payload.get('message') or 'неизвестная ошибка')[:240]
        raise HTTPException(502, f'TGStat: {message}')
    return payload['response']


def sync_channel(workspace_id: int, channel_id: int, user: dict) -> dict:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id,title,username,is_active
        FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true""", (channel_id, workspace_id))
        channel = cur.fetchone()
    if not channel:
        raise HTTPException(404, 'Канал не найден')
    username = (channel.get('username') or '').strip()
    if not username:
        raise HTTPException(422, 'У канала нет публичного username — TGStat не сможет его найти')
    tgstat_channel_id = username if username.startswith('@') else f'@{username}'
    raw = _request(tgstat_channel_id)
    captured = date.today()
    followers = _number(raw.get('participants_count'), integer=True)
    avg_reach = _number(raw.get('avg_post_reach'))
    daily_reach = _number(raw.get('daily_reach'))
    posts_count = _number(raw.get('posts_count'), integer=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_channel_stats_snapshots(
            workspace_id,channel_id,period_end,followers_current,views_per_post,raw,source)
        VALUES(%s,%s,%s,%s,%s,%s::jsonb,'tgstat') RETURNING id""",
                    (workspace_id, channel_id, captured, followers, avg_reach,
                     json.dumps(raw, ensure_ascii=False)))
        snapshot = cur.fetchone()
        cur.execute("""INSERT INTO cd_channel_metrics(
            workspace_id,channel_id,metric_date,subscribers,views,reach,posts_count,source,notes)
        VALUES(%s,%s,%s,%s,%s,%s,%s,'tgstat',%s)
        ON CONFLICT(workspace_id,channel_id,metric_date) DO UPDATE SET
            subscribers=excluded.subscribers,views=excluded.views,reach=excluded.reach,
            posts_count=excluded.posts_count,source='tgstat',notes=excluded.notes,updated_at=now()""",
                    (workspace_id, channel_id, captured, followers, int(round(avg_reach)),
                     int(round(daily_reach)), posts_count, 'Синхронизация TGStat Free'))
        audit(cur, workspace_id, user['id'], 'analytics.tgstat.synced', 'channel', channel_id,
              json.dumps({'snapshot_id': snapshot['id'], 'channel': tgstat_channel_id}))
    return {'snapshot_id': snapshot['id'], 'channel_id': channel_id, 'channel_title': channel['title'],
            'source': 'tgstat', 'captured_at': captured, 'stats': raw}
