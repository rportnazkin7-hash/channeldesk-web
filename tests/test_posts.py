import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_OWNER = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'owner', 'status': 'active', 'channel_scope': []}
MEMBER_VIEWER = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'viewer', 'status': 'active', 'channel_scope': []}
MEMBER_AUTHOR = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'author', 'status': 'active', 'channel_scope': []}
POST_ROW = {'id': 10, 'workspace_id': 3, 'channel_id': 5, 'title': 'Новости дня', 'text': '<b>Привет</b>',
            'status': 'draft', 'scheduled_at': None, 'publish_key': None, 'telegram_message_id': None,
            'approval_required': True, 'created_by': 1, 'approved_by': None, 'attempt_count': 0,
            'last_error': None, 'published_at': None, 'channel_title': 'Тестовый канал', 'author_username': 'dev'}
VERSION_ROW = {'id': 1, 'post_id': 10, 'title': 'Новости дня', 'text': '<b>Привет</b>', 'created_by': 1}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_post(monkeypatch):
    created = dict(POST_ROW, status='draft')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, {'id': 5}, created])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts',
                    json={'title': 'Новости дня', 'text': '<b>Привет</b>', 'channel_id': 5},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['title'] == 'Новости дня'
    assert r.json()['status'] == 'draft'


def test_viewer_cannot_create_post(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts', json={'title': 'x', 'text': 'y'}, headers=auth_headers())
    assert r.status_code == 403


def test_create_post_invalid_status(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts', json={'title': 'x', 'text': 'y', 'status': 'published'},
                    headers=auth_headers())
    assert r.status_code == 422


def test_list_posts(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, [POST_ROW]])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.get('/api/workspaces/3/posts', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['status'] == 'draft'


def test_get_post(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, POST_ROW, VERSION_ROW])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.get('/api/workspaces/3/posts/10', headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['post']['id'] == 10
    assert body['latest_version']['text'] == '<b>Привет</b>'


def test_update_post_saves_version(monkeypatch):
    updated = dict(POST_ROW, text='<b>Новый текст</b>', status='draft')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, POST_ROW, updated])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/posts/10', json={'text': '<b>Новый текст</b>'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['text'] == '<b>Новый текст</b>'
    # должна быть сохранена версия
    calls = [call for cur in conn.cursors for call in cur.calls]
    assert any('INSERT INTO cd_post_versions' in sql for sql, _ in calls)


def test_author_cannot_edit_foreign_post(monkeypatch):
    foreign = dict(POST_ROW, created_by=999)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_AUTHOR, foreign])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/posts/10', json={'title': 'чужое'}, headers=auth_headers())
    assert r.status_code == 403


def test_workflow_submit_approve_schedule(monkeypatch):
    submitted = dict(POST_ROW, status='review')
    approved = dict(POST_ROW, status='approved', approved_by=1)
    scheduled = dict(POST_ROW, status='scheduled', publish_key='abc123', scheduled_at='2026-08-04T10:00:00Z')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, POST_ROW, submitted,  # submit
                                  USER_ROW, MEMBER_OWNER, submitted, approved,  # approve
                                  USER_ROW, MEMBER_OWNER, approved, scheduled])  # schedule
    monkeypatch.setattr('api.posts.connect', lambda: conn)

    r = client.post('/api/workspaces/3/posts/10/submit', headers=auth_headers())
    assert r.status_code == 200 and r.json()['status'] == 'review'

    r = client.post('/api/workspaces/3/posts/10/approve', headers=auth_headers())
    assert r.status_code == 200 and r.json()['status'] == 'approved'

    r = client.post('/api/workspaces/3/posts/10/schedule',
                    json={'scheduled_at': '2026-08-04T10:00:00Z'}, headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'scheduled'
    assert body['publish_key']


def test_schedule_requires_channel(monkeypatch):
    no_channel = dict(POST_ROW, channel_id=None, status='approved')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, no_channel])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/schedule', json={}, headers=auth_headers())
    assert r.status_code == 422
    assert 'канал' in r.json()['detail'].lower()


def test_publish_now_sets_scheduled(monkeypatch):
    approved = dict(POST_ROW, status='approved')
    scheduled = dict(POST_ROW, status='scheduled', publish_key='nowkey', scheduled_at=None)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, approved, scheduled])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/publish-now', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'scheduled'
    assert r.json()['publish_key']


def test_comments(monkeypatch):
    comment = {'id': 1, 'post_id': 10, 'text': 'Проверьте заголовок', 'created_at': '2026-08-03T00:00:00Z',
               'username': 'dev', 'first_name': 'Dev', 'last_name': None}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, POST_ROW, comment])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/comments', json={'text': 'Проверьте заголовок'},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['text'] == 'Проверьте заголовок'
