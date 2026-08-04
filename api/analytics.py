from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action

router = APIRouter(prefix='/api', tags=['analytics'])


def _date_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    end = to_date or date.today()
    start = from_date or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, 'Начало периода не может быть позже окончания')
    if (end - start).days > 366:
        raise HTTPException(422, 'Период аналитики не может быть больше года')
    return start, end


def _summary(rows: list[dict]) -> dict:
    latest_by_channel: dict[int, dict] = {}
    series_by_date: dict[str, dict] = {}
    posts_count = 0
    reactions = 0
    for row in rows:
        channel_id = row['channel_id']
        if channel_id not in latest_by_channel:
            latest_by_channel[channel_id] = row
        posts_count += int(row.get('posts_count') or 0)
        reactions += int(row.get('reactions') or 0)
        metric_date = str(row['metric_date'])
        point = series_by_date.setdefault(metric_date, {
            'date': metric_date, 'subscribers': 0, 'posts_count': 0, 'reactions': 0,
        })
        point['subscribers'] += int(row.get('subscribers') or 0)
        point['posts_count'] += int(row.get('posts_count') or 0)
        point['reactions'] += int(row.get('reactions') or 0)
    return {
        'subscribers': sum(int(row.get('subscribers') or 0) for row in latest_by_channel.values()),
        'posts_count': posts_count,
        'reactions': reactions,
        'channels': len(latest_by_channel),
        'series': [series_by_date[key] for key in sorted(series_by_date)],
        'available': ['subscribers', 'posts_count', 'reactions'],
        'unavailable': ['views', 'reach', 'forwards'],
    }


@router.get('/workspaces/{workspace_id}/analytics')
def analytics_overview(workspace_id: int, channel_id: int | None = None,
                       from_date: date | None = None, to_date: date | None = None,
                       user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'analytics.view')
    start, end = _date_range(from_date, to_date)
    params: list = [workspace_id, start, end]
    sql = """SELECT m.*, c.title AS channel_title
             FROM cd_channel_metrics m
             JOIN cd_channels c ON c.id=m.channel_id
             WHERE m.workspace_id=%s AND m.source='bot_api'
               AND m.metric_date BETWEEN %s AND %s"""
    if channel_id is not None:
        sql += ' AND m.channel_id=%s'
        params.append(channel_id)
    sql += ' ORDER BY m.metric_date, m.channel_id'
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        metrics = cur.fetchall() or []
    return {
        'from_date': start,
        'to_date': end,
        'metrics': metrics,
        'summary': _summary(metrics),
        'data_source': 'telegram_bot_api',
    }


@router.get('/workspaces/{workspace_id}/analytics/metrics')
def list_metrics(workspace_id: int, channel_id: int | None = None,
                 from_date: date | None = None, to_date: date | None = None,
                 user: dict = Depends(current_user)):
    result = analytics_overview(workspace_id, channel_id, from_date, to_date, user)
    return result['metrics']
