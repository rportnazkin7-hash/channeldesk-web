import io

import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
POST_ROW = {'id': 1, 'title': 'Пост', 'text': 'текст', 'status': 'published', 'scheduled_at': None,
            'published_at': None, 'last_error': None, 'channel_title': 'Канал'}
BOOKING_ROW = {'id': 5, 'advertiser_name': 'ООО Реклама', 'channel_title': 'Канал', 'format': 'post',
               'cost': 5000, 'currency': 'RUB', 'status': 'confirmed', 'payment_status': 'paid',
               'publish_at': None, 'erid': 'erid:1', 'erid_required': True}
TX_ROW = {'id': 10, 'type': 'income', 'amount': 1000, 'currency': 'RUB', 'category': 'advertising',
          'description': 'Оплата', 'occurred_at': None}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_export_posts_csv(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [POST_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/posts?format=csv', headers=auth_headers())
    assert r.status_code == 200
    assert 'text/csv' in r.headers['content-type']
    body = r.content.decode('utf-8-sig')
    assert 'Пост' in body and 'published' in body


def test_export_posts_xlsx(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [POST_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/posts?format=xlsx', headers=auth_headers())
    assert r.status_code == 200
    assert 'spreadsheetml' in r.headers['content-type']
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.active['A1'].value == 'ID'


def test_export_posts_pdf(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [POST_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/posts?format=pdf', headers=auth_headers())
    assert r.status_code == 200
    assert 'application/pdf' in r.headers['content-type']
    assert r.content[:4] == b'%PDF'


def test_export_bookings_csv(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [BOOKING_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/bookings?format=csv', headers=auth_headers())
    assert r.status_code == 200
    assert 'ООО Реклама' in r.content.decode('utf-8-sig')


def test_export_bookings_xlsx(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [BOOKING_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/bookings?format=xlsx', headers=auth_headers())
    assert r.status_code == 200
    assert 'spreadsheetml' in r.headers['content-type']


def test_export_finance_xlsx(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [TX_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/finance?format=xlsx', headers=auth_headers())
    assert r.status_code == 200
    assert 'spreadsheetml' in r.headers['content-type']
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.active['B1'].value == 'Тип'


def test_export_finance_csv(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [TX_ROW]])
    monkeypatch.setattr('api.exports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/export/finance?format=csv', headers=auth_headers())
    assert r.status_code == 200
    assert 'Доход' in r.content.decode('utf-8-sig')
