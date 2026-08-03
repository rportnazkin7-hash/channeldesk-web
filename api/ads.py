from __future__ import annotations
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.workspaces import audit

router = APIRouter(prefix='/api', tags=['ads'])

BOOKING_STATUSES = {'requested', 'confirmed', 'active', 'done', 'cancelled', 'overdue'}
PAYMENT_STATUSES = {'unpaid', 'partially_paid', 'paid'}


class AdvertiserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact: dict = Field(default_factory=dict)
    notes: str = ''


class AdvertiserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact: dict | None = None
    notes: str | None = None
    is_active: bool | None = None


class BookingCreate(BaseModel):
    advertiser_id: int
    channel_id: int | None = None
    post_id: int | None = None
    format: str = 'post'
    cost: float = Field(default=0, ge=0)
    currency: str = 'RUB'
    status: str = 'requested'
    payment_status: str = 'unpaid'
    publish_at: datetime | None = None
    delete_at: datetime | None = None
    erid: str | None = None
    erid_required: bool = True
    requisites: dict = Field(default_factory=dict)
    materials_url: str | None = None


class BookingUpdate(BaseModel):
    advertiser_id: int | None = None
    channel_id: int | None = None
    post_id: int | None = None
    format: str | None = None
    cost: float | None = Field(default=None, ge=0)
    currency: str | None = None
    status: str | None = None
    payment_status: str | None = None
    publish_at: datetime | None = None
    delete_at: datetime | None = None
    erid: str | None = None
    erid_required: bool | None = None
    requisites: dict | None = None
    materials_url: str | None = None
    report_url: str | None = None


class TransactionCreate(BaseModel):
    type: str
    amount: float = Field(ge=0)
    currency: str = 'RUB'
    category: str = 'other'
    description: str = ''
    booking_id: int | None = None
    occurred_at: datetime | None = None


# --- Рекламодатели ---

@router.get('/workspaces/{workspace_id}/advertisers')
def list_advertisers(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'advertiser.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM cd_advertisers WHERE workspace_id=%s ORDER BY name', (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/advertisers', status_code=201)
def create_advertiser(workspace_id: int, payload: AdvertiserCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'advertiser.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_advertisers(workspace_id,name,contact,notes,created_by)
        VALUES(%s,%s,%s::jsonb,%s,%s) RETURNING *""",
                    (workspace_id, payload.name.strip(), json.dumps(payload.contact), payload.notes, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'advertiser.created', 'advertiser', row['id'])
        return row


@router.patch('/workspaces/{workspace_id}/advertisers/{advertiser_id}')
def update_advertiser(workspace_id: int, advertiser_id: int, payload: AdvertiserUpdate,
                      user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'advertiser.manage')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    fields, values = [], []
    for key in ('name', 'notes', 'is_active'):
        if key in data:
            fields.append(f'{key}=%s')
            values.append(data[key])
    if 'contact' in data:
        fields.append('contact=%s::jsonb')
        values.append(json.dumps(data['contact']))
    values.extend([workspace_id, advertiser_id])
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"""UPDATE cd_advertisers SET {','.join(fields)},updated_at=now()
        WHERE id=%s AND workspace_id=%s RETURNING *""", values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Рекламодатель не найден')
        audit(cur, workspace_id, user['id'], 'advertiser.updated', 'advertiser', advertiser_id)
        return row


@router.delete('/workspaces/{workspace_id}/advertisers/{advertiser_id}', status_code=204)
def delete_advertiser(workspace_id: int, advertiser_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'advertiser.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM cd_advertisers WHERE id=%s AND workspace_id=%s', (advertiser_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Рекламодатель не найден')
        cur.execute('DELETE FROM cd_advertisers WHERE id=%s', (advertiser_id,))
        audit(cur, workspace_id, user['id'], 'advertiser.deleted', 'advertiser', advertiser_id)
        return None


# --- Бронирования ---

def _validate_booking(cur, workspace_id: int, payload) -> None:
    if payload.advertiser_id is not None:
        cur.execute('SELECT id FROM cd_advertisers WHERE id=%s AND workspace_id=%s', (payload.advertiser_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(422, 'Рекламодатель не принадлежит этому рабочему пространству')
    if payload.channel_id is not None:
        cur.execute('SELECT id FROM cd_channels WHERE id=%s AND workspace_id=%s AND is_active=true',
                    (payload.channel_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(422, 'Канал не принадлежит этому рабочему пространству')
    if payload.post_id is not None:
        cur.execute('SELECT id FROM cd_posts WHERE id=%s AND workspace_id=%s', (payload.post_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(422, 'Публикация не принадлежит этому рабочему пространству')


@router.get('/workspaces/{workspace_id}/bookings')
def list_bookings(workspace_id: int, status: str | None = None, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.view')
    sql = """SELECT b.*, a.name AS advertiser_name, c.title AS channel_title
             FROM cd_ad_bookings b
             LEFT JOIN cd_advertisers a ON a.id=b.advertiser_id
             LEFT JOIN cd_channels c ON c.id=b.channel_id
             WHERE b.workspace_id=%s"""
    params: list = [workspace_id]
    if status:
        if status not in BOOKING_STATUSES:
            raise HTTPException(422, 'Неизвестный статус брони')
        sql += ' AND b.status=%s'
        params.append(status)
    sql += ' ORDER BY b.publish_at NULLS LAST, b.id DESC'
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/bookings', status_code=201)
def create_booking(workspace_id: int, payload: BookingCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    if payload.status not in BOOKING_STATUSES:
        raise HTTPException(422, 'Неизвестный статус брони')
    if payload.payment_status not in PAYMENT_STATUSES:
        raise HTTPException(422, 'Неизвестный статус оплаты')
    with connect() as conn, conn.cursor() as cur:
        _validate_booking(cur, workspace_id, payload)
        cur.execute("""INSERT INTO cd_ad_bookings(workspace_id,advertiser_id,channel_id,post_id,format,cost,currency,
        status,payment_status,publish_at,delete_at,erid,erid_required,requisites,materials_url,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING *""",
                    (workspace_id, payload.advertiser_id, payload.channel_id, payload.post_id, payload.format,
                     payload.cost, payload.currency, payload.status, payload.payment_status,
                     payload.publish_at, payload.delete_at, payload.erid, payload.erid_required,
                     json.dumps(payload.requisites), payload.materials_url, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'booking.created', 'booking', row['id'])
        return row


@router.patch('/workspaces/{workspace_id}/bookings/{booking_id}')
def update_booking(workspace_id: int, booking_id: int, payload: BookingUpdate,
                   user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    if payload.status is not None and payload.status not in BOOKING_STATUSES:
        raise HTTPException(422, 'Неизвестный статус брони')
    if payload.payment_status is not None and payload.payment_status not in PAYMENT_STATUSES:
        raise HTTPException(422, 'Неизвестный статус оплаты')
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, 'Нет данных для обновления')
    with connect() as conn, conn.cursor() as cur:
        _validate_booking(cur, workspace_id, payload)
        fields, values = [], []
        for key in ('advertiser_id', 'channel_id', 'post_id', 'format', 'cost', 'currency', 'status',
                    'payment_status', 'publish_at', 'delete_at', 'erid', 'erid_required', 'materials_url', 'report_url'):
            if key in data:
                fields.append(f'{key}=%s')
                values.append(data[key])
        if 'requisites' in data:
            fields.append('requisites=%s::jsonb')
            values.append(json.dumps(data['requisites']))
        values.extend([booking_id, workspace_id])
        cur.execute(f"UPDATE cd_ad_bookings SET {','.join(fields)},updated_at=now() WHERE id=%s AND workspace_id=%s RETURNING *",
                    values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Бронь не найдена')
        audit(cur, workspace_id, user['id'], 'booking.updated', 'booking', booking_id)
        return row


@router.delete('/workspaces/{workspace_id}/bookings/{booking_id}', status_code=204)
def delete_booking(workspace_id: int, booking_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM cd_ad_bookings WHERE id=%s AND workspace_id=%s', (booking_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404, 'Бронь не найдена')
        cur.execute('DELETE FROM cd_ad_bookings WHERE id=%s', (booking_id,))
        audit(cur, workspace_id, user['id'], 'booking.deleted', 'booking', booking_id)
        return None


@router.post('/workspaces/{workspace_id}/bookings/{booking_id}/pay', status_code=200)
def mark_paid(workspace_id: int, booking_id: int, payload: BookingUpdate, user: dict = Depends(current_user)):
    """Отмечает бронь оплаченной и создаёт транзакцию дохода."""
    member = membership(user['id'], workspace_id)
    require_action(member, 'booking.manage')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM cd_ad_bookings WHERE id=%s AND workspace_id=%s', (booking_id, workspace_id))
        booking = cur.fetchone()
        if not booking:
            raise HTTPException(404, 'Бронь не найдена')
        if payload.payment_status not in PAYMENT_STATUSES:
            raise HTTPException(422, 'Неизвестный статус оплаты')
        # При оплате бронь подтверждается; если дата начала уже наступила — сразу активна.
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        publish_at = booking.get('publish_at')
        if payload.payment_status in ('paid', 'partially_paid'):
            new_status = 'active' if publish_at and publish_at <= now else 'confirmed'
            cur.execute("""UPDATE cd_ad_bookings SET payment_status=%s,status=%s,updated_at=now()
            WHERE id=%s RETURNING *""", (payload.payment_status, new_status, booking_id))
        else:
            cur.execute("UPDATE cd_ad_bookings SET payment_status=%s,updated_at=now() WHERE id=%s RETURNING *",
                        (payload.payment_status, booking_id))
        updated = cur.fetchone()
        # создаём транзакцию дохода только если оплата (не возврат)
        if payload.payment_status in ('paid', 'partially_paid'):
            cur.execute("""INSERT INTO cd_finance_transactions(workspace_id,booking_id,type,amount,currency,
            category,description,created_by)
            VALUES(%s,%s,'income',%s,%s,'advertising',%s,%s)""",
                        (workspace_id, booking_id, booking['cost'], booking['currency'],
                         f'Оплата брони #{booking_id}', user['id']))
        audit(cur, workspace_id, user['id'], 'booking.paid', 'booking', booking_id,
              json.dumps({'payment_status': payload.payment_status}))
        return updated


# --- Финансы ---

@router.get('/workspaces/{workspace_id}/finance/transactions')
def list_transactions(workspace_id: int, limit: int = 100, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'finance.view')
    limit = max(1, min(limit, 300))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT * FROM cd_finance_transactions WHERE workspace_id=%s
        ORDER BY occurred_at DESC, id DESC LIMIT %s""", (workspace_id, limit))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/finance/transactions', status_code=201)
def create_transaction(workspace_id: int, payload: TransactionCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'finance.manage')
    if payload.type not in ('income', 'expense'):
        raise HTTPException(422, 'Тип транзакции: income или expense')
    with connect() as conn, conn.cursor() as cur:
        if payload.booking_id is not None:
            cur.execute('SELECT id FROM cd_ad_bookings WHERE id=%s AND workspace_id=%s',
                        (payload.booking_id, workspace_id))
            if not cur.fetchone():
                raise HTTPException(422, 'Бронь не принадлежит этому рабочему пространству')
        cur.execute("""INSERT INTO cd_finance_transactions(workspace_id,booking_id,type,amount,currency,
        category,description,occurred_at,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,now()),%s) RETURNING *""",
                    (workspace_id, payload.booking_id, payload.type, payload.amount, payload.currency,
                     payload.category, payload.description, payload.occurred_at, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'finance.created', 'transaction', row['id'])
        return row


@router.get('/workspaces/{workspace_id}/finance/summary')
def finance_summary(workspace_id: int, year: int | None = None, month: int | None = None,
                    user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'finance.view')
    now = datetime.utcnow()
    y = year or now.year
    m = month or now.month
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT type, COALESCE(SUM(amount),0) AS total, COUNT(*) AS cnt
        FROM cd_finance_transactions
        WHERE workspace_id=%s AND date_trunc('month', occurred_at)=date_trunc('month', make_date(%s,%s,1))
        GROUP BY type""", (workspace_id, y, m))
        rows = cur.fetchall()
    income = next((r['total'] for r in rows if r['type'] == 'income'), 0)
    expense = next((r['total'] for r in rows if r['type'] == 'expense'), 0)
    return {'year': y, 'month': m,
            'income': float(income), 'expense': float(expense), 'profit': float(income - expense),
            'count': sum(r['cnt'] for r in rows)}
