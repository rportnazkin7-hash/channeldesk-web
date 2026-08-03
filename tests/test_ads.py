import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
MEMBER_VIEWER = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'viewer', 'status': 'active', 'channel_scope': []}
ADV_ROW = {'id': 1, 'workspace_id': 3, 'name': 'ООО Реклама', 'contact': {'telegram': '@ad'},
           'notes': '', 'is_active': True, 'created_by': 1}
BOOKING_ROW = {'id': 5, 'workspace_id': 3, 'advertiser_id': 1, 'channel_id': 9, 'post_id': None,
               'format': 'post', 'cost': 5000, 'currency': 'RUB', 'status': 'confirmed',
               'payment_status': 'unpaid', 'publish_at': None, 'delete_at': None, 'erid': 'ERID-1',
               'requisites': {}, 'materials_url': None, 'report_url': None, 'created_by': 1,
               'advertiser_name': 'ООО Реклама', 'channel_title': 'Канал'}
TX_ROW = {'id': 10, 'workspace_id': 3, 'booking_id': None, 'type': 'income', 'amount': 1000,
          'currency': 'RUB', 'category': 'other', 'description': '', 'occurred_at': '2026-08-01T00:00:00Z'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_advertiser(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, ADV_ROW])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/advertisers', json={'name': 'ООО Реклама', 'contact': {'telegram': '@ad'}},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['name'] == 'ООО Реклама'
    assert r.json()['contact'] == {'telegram': '@ad'}


def test_viewer_cannot_create_advertiser(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/advertisers', json={'name': 'X'}, headers=auth_headers())
    assert r.status_code == 403


def test_list_advertisers(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [ADV_ROW]])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.get('/api/workspaces/3/advertisers', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_create_booking(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 1}, {'id': 9}, BOOKING_ROW])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings',
                    json={'advertiser_id': 1, 'channel_id': 9, 'format': 'post', 'cost': 5000,
                          'status': 'confirmed', 'payment_status': 'unpaid'},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['cost'] == 5000
    assert r.json()['advertiser_id'] == 1


def test_create_booking_invalid_advertiser(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, None])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings', json={'advertiser_id': 999, 'cost': 10}, headers=auth_headers())
    assert r.status_code == 422
    assert 'Рекламодатель' in r.json()['detail']


def test_create_booking_no_erid_required(monkeypatch):
    booking_no_erid = dict(BOOKING_ROW, erid=None, erid_required=False)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 1}, {'id': 9}, booking_no_erid])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings',
                    json={'advertiser_id': 1, 'channel_id': 9, 'cost': 5000, 'erid_required': False},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['erid_required'] is False
    assert r.json()['erid'] is None


def test_update_booking_erid_required(monkeypatch):
    updated = dict(BOOKING_ROW, erid_required=False)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, updated])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/bookings/5', json={'erid_required': False}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['erid_required'] is False


def test_list_bookings(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [BOOKING_ROW]])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.get('/api/workspaces/3/bookings', headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body[0]['advertiser_name'] == 'ООО Реклама'
    assert body[0]['channel_title'] == 'Канал'


def test_mark_paid_creates_income(monkeypatch):
    paid = dict(BOOKING_ROW, payment_status='paid')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, BOOKING_ROW, paid])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings/5/pay', json={'payment_status': 'paid'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['payment_status'] == 'paid'
    # должна быть создана транзакция дохода
    calls = [call for cur in conn.cursors for call in cur.calls]
    inserts = [(sql, params) for sql, params in calls if 'cd_finance_transactions' in sql and 'INSERT' in sql]
    assert inserts
    sql, params = inserts[0]
    assert "'income'" in sql  # тип — константа в запросе
    assert params[2] == 5000  # amount
    assert params[3] == 'RUB'  # currency


def test_finance_summary(monkeypatch):
    rows = [{'type': 'income', 'total': 5000, 'cnt': 1}, {'type': 'expense', 'total': 1200, 'cnt': 2}]
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, rows])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.get('/api/workspaces/3/finance/summary', headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['income'] == 5000
    assert body['expense'] == 1200
    assert body['profit'] == 3800


def test_create_expense(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, TX_ROW])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/finance/transactions',
                    json={'type': 'income', 'amount': 1000, 'description': 'Оплата'}, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['type'] == 'income'


def test_viewer_cannot_view_finance(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.get('/api/workspaces/3/finance/summary', headers=auth_headers())
    assert r.status_code == 403


def test_mark_paid_confirms_future_booking(monkeypatch):
    """Оплата будущей брони переводит её в confirmed."""
    from datetime import datetime, timedelta, timezone
    future = dict(BOOKING_ROW, status='requested', payment_status='unpaid',
                  publish_at=datetime.now(timezone.utc) + timedelta(days=5))
    paid = dict(future, status='confirmed', payment_status='paid')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, future, paid])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings/5/pay', json={'payment_status': 'paid'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'confirmed'
    assert r.json()['payment_status'] == 'paid'


def test_mark_paid_activates_started_booking(monkeypatch):
    """Оплата брони, чья дата уже наступила, делает её активной."""
    from datetime import datetime, timedelta, timezone
    started = dict(BOOKING_ROW, status='requested', payment_status='unpaid',
                   publish_at=datetime.now(timezone.utc) - timedelta(days=1))
    paid = dict(started, status='active', payment_status='paid')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, started, paid])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings/5/pay', json={'payment_status': 'paid'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'active'


def test_create_booking_creates_scheduled_post(monkeypatch):
    """Бронь с каналом и датой авто-создаёт scheduled-пост для публикации."""
    from datetime import datetime, timedelta, timezone
    booking_row = {'id': 5, 'workspace_id': 3, 'advertiser_id': 1, 'channel_id': 9, 'post_id': 77,
                   'format': 'post', 'cost': 5000, 'currency': 'RUB', 'status': 'requested',
                   'payment_status': 'unpaid', 'publish_at': datetime.now(timezone.utc) + timedelta(days=1),
                   'delete_at': None, 'erid': 'erid:1', 'erid_required': True, 'requisites': {},
                   'materials_url': None, 'created_by': 1}
    post_row = {'id': 77}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 1}, {'id': 9}, booking_row, {'name': 'ООО Реклама'}, post_row])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings',
                    json={'advertiser_id': 1, 'channel_id': 9, 'cost': 5000,
                          'publish_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
                    headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['post_id'] == 77
    calls = [call for cur in conn.cursors for call in cur.calls]
    assert any('INSERT INTO cd_posts' in sql for sql, _ in calls)
    assert any('scheduled' in sql and 'publish_key' in sql for sql, _ in calls)




def test_mark_paid_confirms_future_booking(monkeypatch):
    """Оплата будущей брони переводит её в confirmed."""
    from datetime import datetime, timedelta, timezone
    future = dict(BOOKING_ROW, status='requested', payment_status='unpaid',
                  publish_at=datetime.now(timezone.utc) + timedelta(days=5))
    paid = dict(future, status='confirmed', payment_status='paid')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, future, paid])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings/5/pay', json={'payment_status': 'paid'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'confirmed'
    assert r.json()['payment_status'] == 'paid'


def test_mark_paid_activates_started_booking(monkeypatch):
    """Оплата брони, чья дата уже наступила, делает её активной."""
    from datetime import datetime, timedelta, timezone
    started = dict(BOOKING_ROW, status='requested', payment_status='unpaid',
                   publish_at=datetime.now(timezone.utc) - timedelta(days=1))
    paid = dict(started, status='active', payment_status='paid')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, started, paid])
    monkeypatch.setattr('api.ads.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bookings/5/pay', json={'payment_status': 'paid'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'active'


