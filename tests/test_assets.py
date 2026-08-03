import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    captured = {}

    def fake_storage_post(url, key, bucket, path, content_type, data):
        captured['url'] = url
        captured['key'] = key
        captured['bucket'] = bucket
        captured['path'] = path
        captured['content_type'] = content_type
        captured['data'] = data

    monkeypatch.setattr('api.assets._storage_post_object', fake_storage_post)
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
    assert captured['url'] == 'https://project.supabase.co'
    assert captured['bucket'] == 'channeldesk-assets'
    assert captured['path'].startswith('3/')
    assert captured['data'] == b'\x89PNG\r\n'
    assert captured['content_type'] == 'image/png'


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


def test_upload_storage_http_error(monkeypatch):
    def boom(*a, **k):
        import urllib.error
        raise urllib.error.HTTPError('url', 400, 'Bad Request', None, None)

    monkeypatch.setattr('api.assets._storage_post_object', boom)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets',
                    files={'file': ('a.txt', b'data', 'text/plain')}, headers=auth_headers())
    assert r.status_code == 502
    assert '400' in r.json()['detail']


def test_list_assets(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, [ASSET_ROW]])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.get('/api/workspaces/3/assets?post_id=10', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['file_name'] == 'pic.png'


def test_delete_asset(monkeypatch):
    deleted = []

    def fake_storage_delete(url, key, bucket, path):
        deleted.append((bucket, path))

    monkeypatch.setattr('api.assets._storage_delete_object', fake_storage_delete)
    conn = patch_db(monkeypatch, [USER_ROW, ASSET_ROW, {'role': 'editor'}, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.delete('/api/assets/7', headers=auth_headers())
    assert r.status_code == 204
    assert ('channeldesk-assets', '3/abc.png') in deleted


class _Handler(BaseHTTPRequestHandler):
    """Локальный HTTP-сервер, имитирующий Supabase Storage: принимает POST/DELETE."""
    received: list = []

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        type(self).received.append((self.path, self.headers.get('Authorization'), self.headers.get('Content-Type'), body))
        self.send_response(200)
        self.end_headers()

    def do_DELETE(self):
        type(self).received.append((self.path, self.headers.get('Authorization'), None, b''))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture()
def storage_server():
    server = HTTPServer(('127.0.0.1', 0), _Handler)
    _Handler.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()


def test_upload_real_http_to_storage(storage_server, monkeypatch):
    """Интеграционный тест: реальный urllib-запрос к локальному HTTP-серверу.
    Проверяет, что загрузка работает без httpx и без temp-файлов (чистые байты)."""
    monkeypatch.setenv('SUPABASE_URL', storage_server)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 10}, ASSET_ROW])
    monkeypatch.setattr('api.assets.connect', lambda: conn)

    payload = b'\x89PNG\r\n' + b'x' * 200000  # 200 КБ
    r = client.post('/api/workspaces/3/assets',
                    files={'file': ('big.png', payload, 'image/png')},
                    data={'post_id': '10'}, headers=auth_headers())
    assert r.status_code == 201
    path, auth, content_type, body = _Handler.received[0]
    assert path.startswith('/storage/v1/object/channeldesk-assets/3/')
    assert auth == 'Bearer svc-key'
    assert content_type == 'image/png'
    assert body == payload  # байты переданы без изменений


def test_delete_real_http_to_storage(storage_server, monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', storage_server)
    conn = patch_db(monkeypatch, [USER_ROW, ASSET_ROW, {'role': 'editor'}, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.delete('/api/assets/7', headers=auth_headers())
    assert r.status_code == 204
    assert _Handler.received[0][0] == '/storage/v1/object/channeldesk-assets/3/abc.png'
