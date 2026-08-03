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
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'anon-public-key')


def test_create_upload_url(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 10}, ASSET_ROW])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets/upload-url',
                    json={'post_id': 10, 'file_name': 'pic.png', 'content_type': 'image/png', 'size': 100},
                    headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['asset_id'] == 7
    assert body['bucket'] == 'channeldesk-assets'
    assert body['upload_url'].startswith('https://project.supabase.co/storage/v1/object/channeldesk-assets/3/')
    assert body['file_url'].startswith('https://project.supabase.co/storage/v1/object/public/channeldesk-assets/3/')
    assert body['anon_key'] == 'anon-public-key'
    # upload_url содержит путь, но НЕ '/public/' (это endpoint загрузки, не публичный)
    assert '/public/' not in body['upload_url']


def test_create_upload_url_no_anon_key(monkeypatch):
    monkeypatch.delenv('SUPABASE_ANON_KEY')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 10}, ASSET_ROW])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets/upload-url',
                    json={'post_id': 10, 'file_name': 'a.txt', 'content_type': 'text/plain', 'size': 5},
                    headers=auth_headers())
    assert r.status_code == 503
    assert 'SUPABASE_ANON_KEY' in r.json()['detail']


def test_create_upload_url_no_supabase_url(monkeypatch):
    monkeypatch.delenv('SUPABASE_URL')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 10}, ASSET_ROW])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets/upload-url',
                    json={'post_id': 10, 'file_name': 'a.txt', 'content_type': 'text/plain', 'size': 5},
                    headers=auth_headers())
    assert r.status_code == 503
    assert 'SUPABASE_URL' in r.json()['detail']


def test_create_upload_url_key_instead_of_url(monkeypatch):
    """SUPABASE_URL содержит publishable-ключ (sb_publishable_...) вместо URL — ловим 503."""
    monkeypatch.setenv('SUPABASE_URL', 'https://sb_publishable_AbCdEf.supabase.co')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, {'id': 10}, ASSET_ROW])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets/upload-url',
                    json={'post_id': 10, 'file_name': 'a.txt', 'content_type': 'text/plain', 'size': 5},
                    headers=auth_headers())
    assert r.status_code == 503
    assert 'ключ' in r.json()['detail'].lower()


def test_create_upload_url_oversize(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets/upload-url',
                    json={'post_id': 10, 'file_name': 'big.mp4', 'content_type': 'video/mp4',
                          'size': 51 * 1024 * 1024}, headers=auth_headers())
    assert r.status_code == 413


def test_create_upload_url_wrong_post(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, None])  # пост не найден
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.post('/api/workspaces/3/assets/upload-url',
                    json={'post_id': 999, 'file_name': 'a.txt', 'content_type': 'text/plain', 'size': 5},
                    headers=auth_headers())
    assert r.status_code == 422
    assert 'Публикация' in r.json()['detail']


def test_list_assets(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_EDITOR, [ASSET_ROW]])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.get('/api/workspaces/3/assets?post_id=10', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['file_name'] == 'pic.png'


def test_delete_asset_removes_storage_object(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, ASSET_ROW, {'role': 'editor'}, MEMBER_EDITOR])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.delete('/api/assets/7', headers=auth_headers())
    assert r.status_code == 204
    # объект удалён из storage.objects (имя передано параметром) + запись удалена
    calls = [call for cur in conn.cursors for call in cur.calls]
    storage_deletes = [(sql, params) for sql, params in calls
                       if sql.startswith('DELETE') and 'storage.objects' in sql]
    assert storage_deletes
    sql, params = storage_deletes[0]
    assert 'channeldesk-assets' in params
    assert '3/abc.png' in params
    assert any(sql.startswith('DELETE') and 'cd_content_assets' in sql for sql, _ in calls)


def test_attach_asset_to_post(monkeypatch):
    attached = dict(ASSET_ROW, post_id=10)
    conn = patch_db(monkeypatch, [USER_ROW, ASSET_ROW, {'role': 'editor'}, {'id': 10}, attached])
    monkeypatch.setattr('api.assets.connect', lambda: conn)
    r = client.patch('/api/assets/7/post', json={'post_id': 10}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['post_id'] == 10


def test_ensure_bucket_creates_bucket_and_policy(monkeypatch):
    """Проверяем, что ensure_bucket выполняет SQL (bucket + RLS политика) через psycopg."""
    executed = []

    class FakeCur:
        def execute(self, sql, params=None):
            executed.append(sql)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCur()

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost/db')
    monkeypatch.setattr('api.assets.psycopg.connect', lambda *a, **k: FakeConn())

    from api.assets import ensure_bucket
    ensure_bucket()
    joined = '\n'.join(executed)
    assert 'storage.buckets' in joined and 'channeldesk-assets' in joined
    assert 'CREATE POLICY' in joined
    assert 'cd_anon_upload' in joined
