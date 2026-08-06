import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
REPORT = {'id': 4, 'workspace_id': 3, 'user_id': 1, 'description': 'Кнопка не нажимается',
          'screen': 'Интеграции', 'severity': 'high', 'status': 'new', 'source': 'mini_app'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_bug_report(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, REPORT])
    monkeypatch.setattr('api.bug_reports.connect', lambda: conn)
    r = client.post('/api/workspaces/3/bug-reports', headers=auth_headers(), json={
        'description': 'Кнопка не нажимается', 'screen': 'Интеграции', 'severity': 'high', 'app_version': 'v0.47.0',
    })
    assert r.status_code == 201
    assert r.json()['id'] == 4


def test_list_bug_reports(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [REPORT]])
    monkeypatch.setattr('api.bug_reports.connect', lambda: conn)
    r = client.get('/api/workspaces/3/bug-reports', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()[0]['description'] == 'Кнопка не нажимается'


def test_update_bug_report(monkeypatch):
    updated = dict(REPORT, status='fixed')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, updated])
    monkeypatch.setattr('api.bug_reports.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/bug-reports/4', headers=auth_headers(), json={'status': 'fixed'})
    assert r.status_code == 200
    assert r.json()['status'] == 'fixed'
