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
MK_ROW = {'id': 1, 'workspace_id': 3, 'name': 'Медиакит канала', 'channel_id': 5, 'channel_title': 'Канал',
          'description': 'Описание', 'audience': {'age': '18-45'}, 'stats': {'subscribers': 15000},
          'pricing': [{'format': 'post', 'price': 5000}], 'contacts': {'telegram': '@media'},
          'is_active': True, 'created_by': 1}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_media_kit(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 5}, MK_ROW])
    monkeypatch.setattr('api.media_kits.connect', lambda: conn)
    r = client.post('/api/workspaces/3/media-kits',
                    json={'name': 'Медиакит канала', 'channel_id': 5, 'description': 'Описание',
                          'stats': {'subscribers': 15000}, 'pricing': [{'format': 'post', 'price': 5000}]},
                    headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['name'] == 'Медиакит канала'
    assert body['channel_title'] == 'Канал'


def test_viewer_cannot_create(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_VIEWER])
    monkeypatch.setattr('api.media_kits.connect', lambda: conn)
    r = client.post('/api/workspaces/3/media-kits', json={'name': 'X'}, headers=auth_headers())
    assert r.status_code == 403


def test_list_media_kits(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, [MK_ROW]])
    monkeypatch.setattr('api.media_kits.connect', lambda: conn)
    r = client.get('/api/workspaces/3/media-kits', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['stats']['subscribers'] == 15000


def test_update_media_kit(monkeypatch):
    updated = dict(MK_ROW, name='Новое имя')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, updated])
    monkeypatch.setattr('api.media_kits.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/media-kits/1', json={'name': 'Новое имя'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['name'] == 'Новое имя'


def test_delete_media_kit(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 1}, MK_ROW])
    monkeypatch.setattr('api.media_kits.connect', lambda: conn)
    r = client.delete('/api/workspaces/3/media-kits/1', headers=auth_headers())
    assert r.status_code == 204
