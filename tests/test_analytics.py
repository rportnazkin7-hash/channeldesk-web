from datetime import date

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
METRIC_ROW = {'id': 11, 'workspace_id': 3, 'channel_id': 5, 'channel_title': 'Новости',
              'metric_date': date(2026, 8, 3), 'subscribers': 15000, 'views': 0,
              'reach': 0, 'reactions': 12, 'forwards': 0, 'posts_count': 4,
              'source': 'bot_api', 'notes': 'Сбор Bot API'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_analytics_overview_uses_bot_api_data(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [METRIC_ROW]])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.get('/api/workspaces/3/analytics?from_date=2026-08-01&to_date=2026-08-03', headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['data_source'] == 'telegram_bot_api'
    assert body['summary']['subscribers'] == 15000
    assert body['summary']['posts_count'] == 4
    assert body['summary']['reactions'] == 12
    assert body['summary']['unavailable'] == ['views', 'reach', 'forwards']
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert "source='bot_api'" in sql


def test_analytics_rejects_period_longer_than_year(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.get('/api/workspaces/3/analytics?from_date=2024-01-01&to_date=2026-08-03', headers=auth_headers())
    assert r.status_code == 422
    assert 'года' in r.json()['detail']


def test_viewer_can_view_bot_api_analytics(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER, []])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.get('/api/workspaces/3/analytics', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['summary']['available'] == ['subscribers', 'posts_count', 'reactions']
