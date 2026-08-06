from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)


def test_health_version():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['version'] == '0.47.0'


def test_health_migrations_route(monkeypatch):
    conn = patch_db(monkeypatch, [[{'version': '019_bot_api_analytics'}]])
    monkeypatch.setattr('api.db.connect', lambda: conn)
    r = client.get('/api/health/migrations')
    assert r.status_code == 200
    assert r.json()['ok'] is True
    assert r.json()['migrations'][0]['version'] == '019_bot_api_analytics'


def test_health_storage_route(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'anon-test')
    r = client.get('/api/health/storage')
    assert r.status_code == 200
    assert r.json()['configured'] is True
    assert r.json()['mode'] == 'direct-browser-upload'
