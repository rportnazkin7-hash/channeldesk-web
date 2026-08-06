import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_workspace_snapshot_returns_all_workspace_data(monkeypatch):
    conn = patch_db(monkeypatch, [
        USER_ROW,
        MEMBER_ADMIN,
        [],  # pending
        [{'id': 5, 'title': 'Новости'}],  # channels
        [{'id': 7, 'status': 'draft'}],  # posts
        [{'id': 8, 'name': 'Шаблон'}],  # templates
        [{'id': 9, 'name': 'Рекламодатель'}],  # advertisers
        [{'id': 10, 'status': 'requested'}],  # bookings
        [{'id': 11, 'decision': 'approved'}],  # feedback
        [{'id': 12, 'name': 'Медиакит'}],  # media kits
        [{'id': 13, 'status': 'todo'}],  # tasks
        [{'id': 2, 'role': 'admin'}],  # members
        [{'type': 'income', 'total': 1000, 'cnt': 1}],  # finance summary
        [{'year': 2026, 'month': 8, 'income': 1000, 'expense': 0}],  # finance trend
    ])
    monkeypatch.setattr('api.snapshot.connect', lambda: conn)
    r = client.get('/api/workspaces/3/snapshot', headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['channels'][0]['title'] == 'Новости'
    assert body['posts'][0]['status'] == 'draft'
    assert body['finance_summary']['income'] == 1000
    assert len(body['tasks']) == 1
