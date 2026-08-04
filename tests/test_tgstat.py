import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
CHANNEL_ROW = {'id': 5, 'workspace_id': 3, 'title': 'Новости', 'username': 'news_channel', 'is_active': True}
SNAPSHOT_ROW = {'id': 77}
RAW = {
    'id': 118, 'title': 'Новости', 'username': '@news_channel', 'participants_count': 15000,
    'avg_post_reach': 4200, 'daily_reach': 12000, 'posts_count': 800,
    'err_percent': 18.4, 'mentions_count': 42,
}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('TGSTAT_API_TOKEN', 'test-token')


def test_tgstat_sync(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, CHANNEL_ROW, SNAPSHOT_ROW])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    monkeypatch.setattr('api.tgstat.connect', lambda: conn)
    monkeypatch.setattr('api.tgstat._request', lambda channel_id: RAW)
    r = client.post('/api/workspaces/3/analytics/tgstat/sync', json={'channel_id': 5}, headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['source'] == 'tgstat'
    assert body['stats']['participants_count'] == 15000
    calls = [call for cur in conn.cursors for call in cur.calls]
    assert any('cd_channel_stats_snapshots' in sql for sql, _ in calls)
    assert any("source='tgstat'" in sql for sql, _ in calls)


def test_tgstat_requires_token(monkeypatch):
    monkeypatch.delenv('TGSTAT_API_TOKEN', raising=False)
    with pytest.raises(Exception) as error:
        from api.tgstat import _request
        _request('@news_channel')
    assert getattr(error.value, 'status_code', None) == 503


def test_tgstat_requires_username(monkeypatch):
    channel = dict(CHANNEL_ROW, username=None)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, channel])
    monkeypatch.setattr('api.analytics.connect', lambda: conn)
    monkeypatch.setattr('api.tgstat.connect', lambda: conn)
    r = client.post('/api/workspaces/3/analytics/tgstat/sync', json={'channel_id': 5}, headers=auth_headers())
    assert r.status_code == 422
    assert 'username' in r.json()['detail']
