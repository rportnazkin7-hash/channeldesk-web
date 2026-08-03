import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_EDITOR = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'editor', 'status': 'active', 'channel_scope': []}
ASSET_ROW = {'id': 7, 'workspace_id': 3, 'post_id': 10, 'file_name': 'pic.png', 'file_type': 'image/png',
             'file_url': 'https://x.supabase.co/storage/v1/object/public/channeldesk-assets/3/abc.png',
             'size_bytes': 100, 'uploaded_by': 1}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    monkeypatch.setenv('SUPABASE_URL', 'https://project.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'svc-key')


def test_upload_asset(monkeypatch):
    class FakeResp:
        status_code = 200
        text = 'ok'

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, content=None, json=None):
            assert url.startswith('https://project.supabase.co/storage/v1/object/channeldesk-assets/3/')
            return FakeResp()

    monkeypatch.setattr('api.assets.httpx.Client', FakeClient)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 10}, ASSET_ROW])
    monkeypatch.setattr('api.assets.connect', lambda: conn)

    r = client.post('/api/workspaces/3/assets',
                    files={'file': ('pic.png', b'\x89PNG\r\n', 'image/png')},
                    data={'post_id': '10'}, headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['file_name'] == 'pic.png'
    assert body['file_type'] == 'image/png'
    assert 'channeldesk-assets/3/' in body['file_url']


def test_upload_asset_no_storage_env(monkeypatch):
    monkeypatch.delenv('SUPABASE_URL')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets',
                    files={'file': ('a.txt', b'data', 'text/plain')}, headers=auth_headers())
    assert r.status_code == 503
    assert 'Хранилище не настроено' in r.json()['detail']


def test_upload_empty_file_rejected(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets',
                    files={'file': ('empty.txt', b'', 'text/plain')}, headers=auth_headers())
    assert r.status_code == 422


def test_list_assets(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, [ASSET_ROW]])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.get('/api/workspaces/3/assets?post_id=10', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['file_name'] == 'pic.png'


def test_delete_asset(monkeypatch):
    deleted = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def delete(self, url, headers=None):
            deleted.append(url)
            return type('R', (), {'status_code': 200})()

    monkeypatch.setattr('api.assets.httpx.Client', FakeClient)
    conn = patch_db(monkeypatch, [USER_ROW, ASSET_ROW, {'role': 'editor'}, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.delete('/api/assets/7', headers=auth_headers())
    assert r.status_code == 204
    assert any('channeldesk-assets/3/abc.png' in u for u in deleted)
