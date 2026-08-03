import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_EDITOR = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'editor', 'status': 'active', 'channel_scope': []}
MEMBER_VIEWER = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'viewer', 'status': 'active', 'channel_scope': []}
TASK_ROW = {'id': 5, 'workspace_id': 3, 'title': 'Подготовить пост', 'description': 'Текст для канала',
            'status': 'todo', 'priority': 'normal', 'assignee_id': None, 'due_at': None, 'remind_at': None,
            'reminded': False, 'created_by': 1, 'completed_at': None, 'assignee_username': None,
            'assignee_first_name': None}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_task(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, TASK_ROW])
    monkeypatch.setattr('api.tasks.connect', lambda: conn)
    r = client.post('/api/workspaces/3/tasks',
                    json={'title': 'Подготовить пост', 'description': 'Текст для канала', 'priority': 'normal'},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['title'] == 'Подготовить пост'
    assert r.json()['status'] == 'todo'


def test_viewer_cannot_create_task(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.tasks.connect', lambda: conn)
    r = client.post('/api/workspaces/3/tasks', json={'title': 'X'}, headers=auth_headers())
    assert r.status_code == 403


def test_list_tasks(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, [TASK_ROW]])
    monkeypatch.setattr('api.tasks.connect', lambda: conn)
    r = client.get('/api/workspaces/3/tasks', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['title'] == 'Подготовить пост'


def test_complete_task(monkeypatch):
    done = dict(TASK_ROW, status='done')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, done])
    monkeypatch.setattr('api.tasks.connect', lambda: conn)
    r = client.post('/api/workspaces/3/tasks/5/done', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'done'
    calls = [call for cur in conn.cursors for call in cur.calls]
    assert any('completed_at=now()' in sql for sql, _ in calls)


def test_delete_task(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 5}])
    monkeypatch.setattr('api.tasks.connect', lambda: conn)
    r = client.delete('/api/workspaces/3/tasks/5', headers=auth_headers())
    assert r.status_code == 204
