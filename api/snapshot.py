from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends

from api.ads import _as_decimal, _finance_period, _shift_month
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import MATRIX, require_action

router = APIRouter(prefix='/api', tags=['snapshot'])


def _allowed(member: dict, action: str) -> bool:
    return member.get('role') in MATRIX.get(action, frozenset())


def _finance_snapshot(cur, workspace_id: int) -> dict:
    year, month = _finance_period(None, None)
    start_year, start_month = _shift_month(year, month, -5)
    cur.execute("""SELECT type,COALESCE(SUM(amount),0) AS total,COUNT(*) AS cnt
    FROM cd_finance_transactions WHERE workspace_id=%s
      AND occurred_at>=make_date(%s,%s,1)
      AND occurred_at<make_date(%s,%s,1)+interval '1 month'
    GROUP BY type""", (workspace_id, year, month, year, month))
    summary_rows = cur.fetchall() or []
    cur.execute("""SELECT EXTRACT(YEAR FROM occurred_at)::int AS year,
    EXTRACT(MONTH FROM occurred_at)::int AS month,
    COALESCE(SUM(amount) FILTER (WHERE type='income'),0) AS income,
    COALESCE(SUM(amount) FILTER (WHERE type='expense'),0) AS expense
    FROM cd_finance_transactions
    WHERE workspace_id=%s
      AND occurred_at>=make_date(%s,%s,1)
      AND occurred_at<make_date(%s,%s,1)+interval '1 month'
    GROUP BY 1,2 ORDER BY 1,2""", (workspace_id, start_year, start_month, year, month))
    trend_rows = cur.fetchall() or []
    income = next((_as_decimal(row.get('total')) for row in summary_rows if row['type'] == 'income'), Decimal('0'))
    expense = next((_as_decimal(row.get('total')) for row in summary_rows if row['type'] == 'expense'), Decimal('0'))
    by_month = {(int(row['year']), int(row['month'])): row for row in trend_rows}
    trend = []
    for offset in range(6):
        trend_year, trend_month = _shift_month(start_year, start_month, offset)
        row = by_month.get((trend_year, trend_month), {})
        trend_income = _as_decimal(row.get('income'))
        trend_expense = _as_decimal(row.get('expense'))
        trend.append({
            'year': trend_year,
            'month': trend_month,
            'income': float(trend_income),
            'expense': float(trend_expense),
            'profit': float(trend_income - trend_expense),
        })
    return {
        'year': year,
        'month': month,
        'income': float(income),
        'expense': float(expense),
        'profit': float(income - expense),
        'count': sum(int(row.get('cnt') or 0) for row in summary_rows),
        'trend': trend,
    }


@router.get('/workspaces/{workspace_id}/snapshot')
def workspace_snapshot(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'workspace.view')
    with connect() as conn, conn.cursor() as cur:
        # Каналы, подключённые к архивному workspace, должны снова появиться
        # в pending, как и в отдельном endpoint каналов.
        cur.execute("""UPDATE cd_channel_connections cc
        SET status='pending',connected_channel_id=NULL,updated_at=now()
        WHERE cc.actor_telegram_id=%s AND cc.status='connected'
          AND (cc.connected_channel_id IS NULL OR EXISTS (
            SELECT 1 FROM cd_channels c JOIN cd_workspaces w ON w.id=c.workspace_id
            WHERE c.id=cc.connected_channel_id AND (c.is_active=false OR w.is_active=false)
          ))""", (user['telegram_id'],))
        cur.execute("""SELECT id,telegram_chat_id,title,username,bot_permissions,observed_at
        FROM cd_channel_connections WHERE actor_telegram_id=%s AND status='pending'
        ORDER BY updated_at DESC""", (user['telegram_id'],))
        pending = cur.fetchall() or []

        cur.execute('SELECT * FROM cd_channels WHERE workspace_id=%s AND is_active=true ORDER BY title', (workspace_id,))
        channels = cur.fetchall() or []
        cur.execute("""SELECT p.*,c.title AS channel_title,u.username AS author_username
        FROM cd_posts p LEFT JOIN cd_channels c ON c.id=p.channel_id
        LEFT JOIN cd_users u ON u.id=p.created_by
        WHERE p.workspace_id=%s ORDER BY p.updated_at DESC LIMIT 200""", (workspace_id,))
        posts = cur.fetchall() or []
        cur.execute('SELECT * FROM cd_post_templates WHERE workspace_id=%s ORDER BY name', (workspace_id,))
        templates = cur.fetchall() or []
        cur.execute('SELECT * FROM cd_advertisers WHERE workspace_id=%s ORDER BY name', (workspace_id,))
        advertisers = cur.fetchall() or []
        cur.execute("""SELECT b.*,a.name AS advertiser_name,c.title AS channel_title
        FROM cd_ad_bookings b LEFT JOIN cd_advertisers a ON a.id=b.advertiser_id
        LEFT JOIN cd_channels c ON c.id=b.channel_id
        WHERE b.workspace_id=%s ORDER BY b.publish_at NULLS LAST,b.id DESC""", (workspace_id,))
        bookings = cur.fetchall() or []
        cur.execute("""SELECT f.id,f.booking_id,f.post_id,f.decision,f.comment,f.created_at,
        a.name AS advertiser_name,b.format,b.publish_at,c.title AS channel_title,p.title AS post_title
        FROM cd_public_report_feedback f JOIN cd_advertisers a ON a.id=f.advertiser_id
        JOIN cd_ad_bookings b ON b.id=f.booking_id LEFT JOIN cd_channels c ON c.id=b.channel_id
        LEFT JOIN cd_posts p ON p.id=f.post_id WHERE f.workspace_id=%s
        ORDER BY f.created_at DESC LIMIT 200""", (workspace_id,))
        feedback = cur.fetchall() or []
        cur.execute("""SELECT mk.*,c.title AS channel_title FROM cd_media_kits mk
        LEFT JOIN cd_channels c ON c.id=mk.channel_id WHERE mk.workspace_id=%s ORDER BY mk.name""", (workspace_id,))
        media_kits = cur.fetchall() or []
        cur.execute("""SELECT t.*,u.username AS assignee_username,u.first_name AS assignee_first_name
        FROM cd_tasks t LEFT JOIN cd_users u ON u.id=t.assignee_id
        WHERE t.workspace_id=%s ORDER BY t.due_at NULLS LAST,t.updated_at DESC""", (workspace_id,))
        tasks = cur.fetchall() or []
        members = []
        if _allowed(member, 'members.view'):
            cur.execute("""SELECT m.id,m.role,m.status,m.channel_scope,m.joined_at,
            u.telegram_id,u.username,u.first_name,u.last_name
            FROM cd_workspace_members m JOIN cd_users u ON u.id=m.user_id
            WHERE m.workspace_id=%s ORDER BY m.joined_at""", (workspace_id,))
            members = cur.fetchall() or []
        finance_summary: dict[str, Any] | None = _finance_snapshot(cur, workspace_id) if _allowed(member, 'finance.view') else None
    return {
        'pending': pending,
        'channels': channels,
        'members': members,
        'posts': posts,
        'templates': templates,
        'advertisers': advertisers,
        'bookings': bookings,
        'feedback': feedback,
        'finance_summary': finance_summary,
        'media_kits': media_kits,
        'tasks': tasks,
    }
