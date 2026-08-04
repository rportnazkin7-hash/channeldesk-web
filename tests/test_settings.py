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


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_get_workspace_settings(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'settings': {'overdue_cancel_days': 7}}])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.get('/api/workspaces/3/settings', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['overdue_cancel_days'] == 7


def test_update_workspace_settings(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'settings': {'overdue_cancel_days': 3}}])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/settings', json={'overdue_cancel_days': 14}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['overdue_cancel_days'] == 14
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'settings=%s::jsonb' in sql


def test_settings_days_range(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/settings', json={'overdue_cancel_days': 31}, headers=auth_headers())
    assert r.status_code == 422


def test_viewer_cannot_update_settings(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/settings', json={'overdue_cancel_days': 5}, headers=auth_headers())
    assert r.status_code == 403
