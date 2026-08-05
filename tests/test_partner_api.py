import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
API_KEY_ROW = {'id': 9, 'workspace_id': 3, 'name': 'Сайт', 'scopes': ['drafts:create', 'posts:read', 'channels:read'],
               'created_by': 1, 'expires_at': None, 'workspace_name': 'Агентство'}
POST_ROW = {'id': 77, 'workspace_id': 3, 'channel_id': 5, 'title': 'Новость', 'text': 'Текст', 'status': 'draft',
            'approval_required': True, 'created_by': 1, 'buttons': [], 'source': 'website',
            'source_url': 'https://example.com/news/1', 'external_id': 'news-1', 'created_at': '2026-08-05T00:00:00Z'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


def partner_headers():
    return {'Authorization': 'Bearer cd_live_test_key_123456789'}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_api_key_returns_secret_once(monkeypatch):
    created = {'id': 10, 'name': 'Сайт', 'key_prefix': 'cd_live_test', 'scopes': ['drafts:create'],
               'expires_at': None, 'created_at': '2026-08-05T00:00:00Z'}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, created])
    monkeypatch.setattr('api.partner_api.connect', lambda: conn)
    r = client.post('/api/workspaces/3/api-keys', json={'name': 'Сайт', 'scopes': ['drafts:create']}, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['token'].startswith('cd_live_')
    assert r.json()['scopes'] == ['drafts:create']


def test_partner_channels(monkeypatch):
    conn = patch_db(monkeypatch, [API_KEY_ROW, [{'id': 5, 'title': 'Новости', 'username': 'news', 'telegram_chat_id': -1005}]])
    monkeypatch.setattr('api.partner_api.connect', lambda: conn)
    r = client.get('/api/v1/workspaces/3/channels', headers=partner_headers())
    assert r.status_code == 200
    assert r.json()['channels'][0]['title'] == 'Новости'


def test_partner_create_draft(monkeypatch):
    conn = patch_db(monkeypatch, [API_KEY_ROW, {'id': 5}, POST_ROW, [], []])
    monkeypatch.setattr('api.partner_api.connect', lambda: conn)
    r = client.post('/api/v1/workspaces/3/drafts', headers=partner_headers(), json={
        'title': 'Новость', 'text': '<b>Текст</b>', 'channel_id': 5,
        'source': 'website', 'source_url': 'https://example.com/news/1', 'external_id': 'news-1',
    })
    assert r.status_code == 201
    assert r.json()['post']['id'] == 77
    assert r.json()['post']['status'] == 'draft'
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'cd_api_idempotency_keys' not in sql
    assert 'source_url' in sql


def test_partner_get_post(monkeypatch):
    asset = {'id': 1, 'file_name': 'photo.jpg', 'file_type': 'image/jpeg', 'file_url': 'https://example.com/photo.jpg'}
    conn = patch_db(monkeypatch, [API_KEY_ROW, POST_ROW, [asset]])
    monkeypatch.setattr('api.partner_api.connect', lambda: conn)
    r = client.get('/api/v1/workspaces/3/posts/77', headers=partner_headers())
    assert r.status_code == 200
    assert r.json()['post']['title'] == 'Новость'
    assert r.json()['assets'][0]['file_name'] == 'photo.jpg'


def test_partner_rejects_unknown_scope(monkeypatch):
    key = dict(API_KEY_ROW, scopes=['posts:read'])
    conn = patch_db(monkeypatch, [key])
    monkeypatch.setattr('api.partner_api.connect', lambda: conn)
    r = client.post('/api/v1/workspaces/3/drafts', headers=partner_headers(), json={'text': 'x'})
    assert r.status_code == 403
    assert 'drafts:create' in r.json()['detail']


def test_webhook_create_returns_secret(monkeypatch):
    created = {'id': 4, 'name': 'CRM', 'url': 'https://example.com/hook', 'events': ['post.created'],
               'is_active': True, 'created_at': '2026-08-05T00:00:00Z'}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, created])
    monkeypatch.setattr('api.partner_api.connect', lambda: conn)
    r = client.post('/api/workspaces/3/webhooks', headers=auth_headers(), json={
        'name': 'CRM', 'url': 'https://example.com/hook', 'events': ['post.created'],
    })
    assert r.status_code == 201
    assert r.json()['secret'].startswith('whsec_')
