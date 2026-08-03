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
CHANNEL_ROW = {'id': 5, 'workspace_id': 3, 'title': 'Новости', 'is_active': True}
METRIC_ROW = {'id': 11, 'workspace_id': 3, 'channel_id': 5, 'channel_title': 'Новости',
              'metric_date': date(2026, 8, 3), 'subscribers': 15000, 'views': 80000,
              'reach': 50000, 'reactions': 1200, 'forwards': 300, 'posts_count': 4,
              'source': 'manual', 'notes': ''}
LINK_ROW = {'id': 21, 'workspace_id': 3, 'channel_id': 5, 'channel_title': 'Новости',
            'name': 'Лид-форма', 'url': 'https://example.com/lead', 'clicks': 120,
            'conversions': 18, 'notes': '', 'is_active': True}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_analytics_overview(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [METRIC_ROW], [LINK_ROW]])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.get('/api/workspaces/3/analytics?from_date=2026-08-01&to_date=2026-08-03', headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['summary']['views'] == 80000
    assert body['summary']['reach'] == 50000
    assert body['summary']['subscribers'] == 15000
    assert body['summary']['clicks'] == 120
    assert body['summary']['series'][0]['date'] == '2026-08-03'


def test_analytics_rejects_period_longer_than_year(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.get('/api/workspaces/3/analytics?from_date=2024-01-01&to_date=2026-08-03', headers=auth_headers())
    assert r.status_code == 422
    assert 'года' in r.json()['detail']


def test_upsert_metric(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, CHANNEL_ROW, METRIC_ROW])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.post('/api/workspaces/3/analytics/metrics', json={
        'channel_id': 5, 'metric_date': '2026-08-03', 'subscribers': 15000,
        'views': 80000, 'reach': 50000, 'reactions': 1200,
    }, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['id'] == 11
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'ON CONFLICT(workspace_id,channel_id,metric_date)' in sql


def test_viewer_cannot_write_metric(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.post('/api/workspaces/3/analytics/metrics', json={
        'channel_id': 5, 'metric_date': '2026-08-03', 'views': 1,
    }, headers=auth_headers())
    assert r.status_code == 403


def test_create_analytics_link(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, CHANNEL_ROW, LINK_ROW])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.post('/api/workspaces/3/analytics/links', json={
        'channel_id': 5, 'name': 'Лид-форма', 'url': 'https://example.com/lead',
        'clicks': 120, 'conversions': 18,
    }, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['name'] == 'Лид-форма'


def test_create_analytics_link_rejects_invalid_url(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    r = client.post('/api/workspaces/3/analytics/links', json={
        'channel_id': 5, 'name': 'Плохая', 'url': 'not-a-url',
    }, headers=auth_headers())
    assert r.status_code == 422
    assert 'http' in r.json()['detail']
