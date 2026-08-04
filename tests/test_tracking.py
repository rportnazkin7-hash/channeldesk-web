import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
LINK_ROW = {'id': 7, 'name': 'Кампания', 'target_url': 'https://example.com/landing', 'clicks': 0}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_tracking_link(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 5}, LINK_ROW])
    monkeypatch.setattr('api.tracking.connect', lambda: conn)
    r = client.post('/api/workspaces/3/tracking-links', json={
        'channel_id': 5, 'name': 'Кампания', 'target_url': 'https://example.com/landing',
    }, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['path'].startswith('/api/r/')


def test_tracking_redirect_counts_click(monkeypatch):
    conn = patch_db(monkeypatch, [{'id': 7, 'target_url': 'https://example.com/landing'}])
    monkeypatch.setattr('api.tracking.connect', lambda: conn)
    r = client.get('/api/r/test-token', follow_redirects=False)
    assert r.status_code == 307
    assert r.headers['location'] == 'https://example.com/landing'
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'clicks=clicks+1' in sql


def test_tracking_rejects_invalid_target(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN])
    monkeypatch.setattr('api.tracking.connect', lambda: conn)
    r = client.post('/api/workspaces/3/tracking-links', json={
        'channel_id': 5, 'name': 'Кампания', 'target_url': '@not-a-url',
    }, headers=auth_headers())
    assert r.status_code == 422
