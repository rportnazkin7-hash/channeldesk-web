from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
ADVERTISER = {'id': 4, 'name': 'ООО Реклама'}
REPORT_ROW = {'id': 9, 'expires_at': datetime.now(timezone.utc) + timedelta(days=30)}
BOOKING = {'id': 10, 'format': 'post', 'cost': 5000, 'currency': 'RUB', 'status': 'done',
           'payment_status': 'paid', 'publish_at': None, 'delete_at': None, 'channel_title': 'Новости'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_public_report(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, ADVERTISER, REPORT_ROW])
    monkeypatch.setattr('api.reports.connect', lambda: conn)
    r = client.post('/api/workspaces/3/advertisers/4/public-report', json={'expires_in_days': 30}, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['path'].startswith('/public-report?token=')
    assert r.json()['advertiser_name'] == 'ООО Реклама'


def test_get_public_report(monkeypatch):
    conn = patch_db(monkeypatch, [REPORT_ROW | {'workspace_id': 3, 'advertiser_id': 4, 'advertiser_name': 'ООО Реклама'}, [BOOKING]])
    monkeypatch.setattr('api.reports.connect', lambda: conn)
    r = client.get('/api/public/reports/valid-token')
    assert r.status_code == 200
    assert r.json()['advertiser_name'] == 'ООО Реклама'
    assert r.json()['bookings'][0]['channel_title'] == 'Новости'


def test_public_report_expired(monkeypatch):
    expired = REPORT_ROW | {'workspace_id': 3, 'advertiser_id': 4, 'advertiser_name': 'ООО Реклама',
                             'expires_at': datetime.now(timezone.utc) - timedelta(days=1)}
    conn = patch_db(monkeypatch, [expired])
    monkeypatch.setattr('api.reports.connect', lambda: conn)
    r = client.get('/api/public/reports/expired-token')
    assert r.status_code == 410
