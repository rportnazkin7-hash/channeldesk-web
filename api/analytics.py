from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['analytics'])

METRIC_SOURCES = {'manual', 'bot_api', 'mtproto'}


class MetricCreate(BaseModel):
    channel_id: int
    metric_date: date
    subscribers: int = Field(default=0, ge=0)
    views: int = Field(default=0, ge=0)
    reach: int = Field(default=0, ge=0)
    reactions: int = Field(default=0, ge=0)
    forwards: int = Field(default=0, ge=0)
    posts_count: int = Field(default=0, ge=0)
    source: str = 'manual'
    notes: str = Field(default='', max_length=2000)


class MetricUpdate(BaseModel):
    channel_id: int | None = None
    metric_date: date | None = None
    subscribers: int | None = Field(default=None, ge=0)
    views: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    reactions: int | None = Field(default=None, ge=0)
    forwards: int | None = Field(default=None, ge=0)
    posts_count: int | None = Field(default=None, ge=0)
    source: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


class LinkCreate(BaseModel):
    channel_id: int
    name: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=1, max_length=2048)
    clicks: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    notes: str = Field(default='', max_length=2000)


class LinkUpdate(BaseModel):
    channel_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    clicks: int | None = Field(default=None, ge=0)
    conversions: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class TgstatSyncRequest(BaseModel):
    channel_id: int


def _date_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    end = to_date or date.today()
    start = from_date or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, 'Начало периода не может быть позже окончания')
    if (end - start).days > 366:
        raise HTTPException(422, 'Период аналитики не может быть больше года')
    return start, end


def _validate_source(source: str) -> None:
    if source not in METRIC_SOURCES:
        raise HTTPException(422, 'Источник метрики: manual или bot_api')


def _validate_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(422, 'Ссылка должна начинаться с http:// или https://')
    return url


def _validate_channel(cur, workspace_id: int, channel_id: int) -> None:
    cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                (channel_id, workspace_id))
    if not cur.fetchone():
        raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')


def _metric_summary(rows: list[dict]) -> dict:
    latest_by_channel: dict[int, dict] = {}
    series_by_date: dict[str, dict] = {}
    totals = {'views': 0, 'reach': 0, 'reactions': 0, 'forwards': 0, 'posts_count': 0}
    for row in rows:
        channel_id = row['channel_id']
        if channel_id not in latest_by_channel:
            latest_by_channel[channel_id] = row
        for key in totals:
            totals[key] += int(row.get(key) or 0)
        metric_date = str(row['metric_date'])
        point = series_by_date.setdefault(metric_date,
                                          {'date': metric_date, 'subscribers': 0, 'views': 0,
                                           'reach': 0, 'reactions': 0, 'forwards': 0, 'posts_count': 0})
        for key in ('subscribers', 'views', 'reach', 'reactions', 'forwards', 'posts_count'):
            point[key] += int(row.get(key) or 0)
    totals['subscribers'] = sum(int(row.get('subscribers') or 0) for row in latest_by_channel.values())
    return {**totals, 'channels': len(latest_by_channel),
            'series': [series_by_date[key] for key in sorted(series_by_date)]}


@router.get('/workspaces/{workspace_id}/analytics')
def analytics_overview(workspace_id: int, channel_id: int | None = None,
                       from_date: date | None = None, to_date: date | None = None,
                       user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.view')
    start, end = _date_range(from_date, to_date)
    metric_params: list = [workspace_id, start, end]
    metric_sql = """SELECT m.*, c.title AS channel_title
                    FROM cd_channel_metrics m
                    JOIN cd_channels c ON c.id=m.channel_id
                    WHERE m.workspace_id=%s AND m.metric_date BETWEEN %s AND %s"""
    if channel_id is not None:
        metric_sql += ' AND m.channel_id=%s'
        metric_params.append(channel_id)
    metric_sql += ' ORDER BY m.metric_date, m.channel_id'
    link_params: list = [workspace_id]
    link_sql = """SELECT l.*, c.title AS channel_title
                 FROM cd_channel_links l
                 JOIN cd_channels c ON c.id=l.channel_id
                 WHERE l.workspace_id=%s AND l.is_active=true"""
    if channel_id is not None:
        link_sql += ' AND l.channel_id=%s'
        link_params.append(channel_id)
    link_sql += ' ORDER BY l.created_at DESC, l.id DESC'
    stats_params: list = [workspace_id, start, end]
    stats_sql = """SELECT DISTINCT ON (s.channel_id) s.*, c.title AS channel_title
                  FROM cd_channel_stats_snapshots s
                  JOIN cd_channels c ON c.id=s.channel_id
                  WHERE s.workspace_id=%s AND s.captured_at >= %s AND s.captured_at < (%s + interval '1 day')"""
    if channel_id is not None:
        stats_sql += ' AND s.channel_id=%s'
        stats_params.append(channel_id)
    stats_sql += ' ORDER BY s.channel_id, s.captured_at DESC'
    with connect() as conn, conn.cursor() as cur:
        cur.execute(metric_sql, metric_params)
        metrics = cur.fetchall() or []
        cur.execute(link_sql, link_params)
        links = cur.fetchall() or []
        cur.execute(stats_sql, stats_params)
        mtproto = cur.fetchall() or []
    link_summary = {
        'clicks': sum(int(row.get('clicks') or 0) for row in links),
        'conversions': sum(int(row.get('conversions') or 0) for row in links),
        'links': len(links),
    }
    return {'from_date': start, 'to_date': end, 'metrics': metrics, 'links': links, 'mtproto': mtproto,
            'summary': {**_metric_summary(metrics), **link_summary}}


@router.get('/workspaces/{workspace_id}/analytics/metrics')
def list_metrics(workspace_id: int, channel_id: int | None = None,
                 from_date: date | None = None, to_date: date | None = None,
                 user: dict = Depends(current_user)):
    result = analytics_overview(workspace_id, channel_id, from_date, to_date, user)
    return result['metrics']


@router.get('/workspaces/{workspace_id}/analytics/mtproto')
def list_mtproto_snapshots(workspace_id: int, channel_id: int | None = None,
                           from_date: date | None = None, to_date: date | None = None,
                           user: dict = Depends(current_user)):
    result = analytics_overview(workspace_id, channel_id, from_date, to_date, user)
    return result['mtproto']


@router.post('/workspaces/{workspace_id}/analytics/tgstat/sync', status_code=201)
def sync_tgstat(workspace_id: int, payload: TgstatSyncRequest, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    from api.tgstat import sync_channel
    return sync_channel(workspace_id, payload.channel_id, user)


@router.post('/workspaces/{workspace_id}/analytics/metrics', status_code=201)
def upsert_metric(workspace_id: int, payload: MetricCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    _validate_source(payload.source)
    with connect() as conn, conn.cursor() as cur:
        _validate_channel(cur, workspace_id, payload.channel_id)
        cur.execute("""INSERT INTO cd_channel_metrics(
            workspace_id,channel_id,metric_date,subscribers,views,reach,reactions,forwards,posts_count,source,notes,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(workspace_id,channel_id,metric_date) DO UPDATE SET
            subscribers=excluded.subscribers,views=excluded.views,reach=excluded.reach,
            reactions=excluded.reactions,forwards=excluded.forwards,posts_count=excluded.posts_count,
            source=excluded.source,notes=excluded.notes,updated_at=now()
        RETURNING *""", (workspace_id, payload.channel_id, payload.metric_date, payload.subscribers,
                          payload.views, payload.reach, payload.reactions, payload.forwards,
                          payload.posts_count, payload.source, payload.notes.strip(), user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'analytics.metric.upserted', 'channel_metric', row['id'])
        return row


@router.patch('/workspaces/{workspace_id}/analytics/metrics/{metric_id}')
def update_metric(workspace_id: int, metric_id: int, payload: MetricUpdate,
                  user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    if 'source' in data:
        _validate_source(data['source'])
    with connect() as conn, conn.cursor() as cur:
        if 'channel_id' in data:
            _validate_channel(cur, workspace_id, data['channel_id'])
        fields, values = [], []
        for key in ('channel_id', 'metric_date', 'subscribers', 'views', 'reach', 'reactions', 'forwards', 'posts_count', 'source', 'notes'):
            if key in data:
                fields.append(f'{key}=%s')
                values.append(data[key])
        values.extend([metric_id, workspace_id])
        cur.execute(f"""UPDATE cd_channel_metrics SET {','.join(fields)},updated_at=now()
        WHERE id=%s AND workspace_id=%s RETURNING *""", values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Метрика не найдена')
        audit(cur, workspace_id, user['id'], 'analytics.metric.updated', 'channel_metric', metric_id)
        return row


@router.delete('/workspaces/{workspace_id}/analytics/metrics/{metric_id}', status_code=204)
def delete_metric(workspace_id: int, metric_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM cd_channel_metrics WHERE id=%s AND workspace_id=%s RETURNING id',
                    (metric_id, workspace_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Метрика не найдена')
        audit(cur, workspace_id, user['id'], 'analytics.metric.deleted', 'channel_metric', metric_id)
        return None


@router.get('/workspaces/{workspace_id}/analytics/links')
def list_links(workspace_id: int, channel_id: int | None = None,
               user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.view')
    params: list = [workspace_id]
    sql = """SELECT l.*, c.title AS channel_title FROM cd_channel_links l
             JOIN cd_channels c ON c.id=l.channel_id
             WHERE l.workspace_id=%s AND l.is_active=true"""
    if channel_id is not None:
        sql += ' AND l.channel_id=%s'
        params.append(channel_id)
    sql += ' ORDER BY l.created_at DESC, l.id DESC'
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/analytics/links', status_code=201)
def create_link(workspace_id: int, payload: LinkCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    url = _validate_url(payload.url)
    with connect() as conn, conn.cursor() as cur:
        _validate_channel(cur, workspace_id, payload.channel_id)
        cur.execute("""INSERT INTO cd_channel_links(workspace_id,channel_id,name,url,clicks,conversions,notes,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace_id, payload.channel_id, payload.name.strip(), url, payload.clicks,
                     payload.conversions, payload.notes.strip(), user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'analytics.link.created', 'channel_link', row['id'])
        return row


@router.patch('/workspaces/{workspace_id}/analytics/links/{link_id}')
def update_link(workspace_id: int, link_id: int, payload: LinkUpdate,
                user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    if 'url' in data:
        data['url'] = _validate_url(data['url'])
    with connect() as conn, conn.cursor() as cur:
        if 'channel_id' in data:
            _validate_channel(cur, workspace_id, data['channel_id'])
        fields, values = [], []
        for key in ('channel_id', 'name', 'url', 'clicks', 'conversions', 'notes', 'is_active'):
            if key in data:
                fields.append(f'{key}=%s')
                values.append(data[key])
        values.extend([link_id, workspace_id])
        cur.execute(f"""UPDATE cd_channel_links SET {','.join(fields)},updated_at=now()
        WHERE id=%s AND workspace_id=%s RETURNING *""", values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Ссылка не найдена')
        audit(cur, workspace_id, user['id'], 'analytics.link.updated', 'channel_link', link_id)
        return row


@router.delete('/workspaces/{workspace_id}/analytics/links/{link_id}', status_code=204)
def delete_link(workspace_id: int, link_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('UPDATE cd_channel_links SET is_active=false,updated_at=now() WHERE id=%s AND workspace_id=%s RETURNING id',
                    (link_id, workspace_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Ссылка не найдена')
        audit(cur, workspace_id, user['id'], 'analytics.link.deleted', 'channel_link', link_id)
        return None
