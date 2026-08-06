import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
PAGE_ROW = {'id': 8, 'workspace_id': 3, 'channel_id': 5, 'title': 'Предложить новость',
            'description': 'Отправьте материал редакции', 'channel_title': 'Новости'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    monkeypatch.setenv('SUPABASE_URL', 'https://project.supabase.co')
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'anon-test')


def test_create_public_news_page(monkeypatch):
    created = {'id': 8, 'title': 'Предложить новость', 'description': 'Описание', 'channel_id': 5}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, {'id': 5, 'title': 'Новости'}, created])
    monkeypatch.setattr('api.public_news.connect', lambda: conn)
    r = client.post('/api/workspaces/3/public-news-pages', headers=auth_headers(), json={
        'channel_id': 5, 'title': 'Предложить новость', 'description': 'Описание',
    })
    assert r.status_code == 201
    assert r.json()['path'].startswith('/public-news?token=')


def test_get_public_news_page(monkeypatch):
    conn = patch_db(monkeypatch, [PAGE_ROW])
    monkeypatch.setattr('api.public_news.connect', lambda: conn)
    r = client.get('/api/public-news/public-token')
    assert r.status_code == 200
    assert r.json()['channel_title'] == 'Новости'


def test_submit_public_news_creates_draft(monkeypatch):
    post = {'id': 77}
    request = {'id': 41}
    conn = patch_db(monkeypatch, [PAGE_ROW, {'cnt': 0}, post, request, []])
    monkeypatch.setattr('api.public_news.connect', lambda: conn)
    r = client.post('/api/public-news/public-token/submit', json={
        'title': 'Новость от читателя',
        'text': 'На улице открыли новую площадку.',
        'contact_telegram': '@reader',
        'source_url': 'https://example.com/news',
    })
    assert r.status_code == 201
    assert r.json()['post_id'] == 77
    assert r.json()['request_id'] == 41
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'source,source_url' in sql
    assert 'INSERT INTO cd_public_news_requests' in sql


def test_public_news_rate_limit(monkeypatch):
    conn = patch_db(monkeypatch, [PAGE_ROW, {'cnt': 20}])
    monkeypatch.setattr('api.public_news.connect', lambda: conn)
    r = client.post('/api/public-news/public-token/submit', json={'text': 'Спам'})
    assert r.status_code == 429


def test_public_news_upload_ticket(monkeypatch):
    conn = patch_db(monkeypatch, [PAGE_ROW, {'id': 5}])
    monkeypatch.setattr('api.public_news.connect', lambda: conn)
    r = client.post('/api/public-news/public-token/upload-url', json={
        'file_name': 'photo.jpg', 'content_type': 'image/jpeg', 'size': 1200,
    })
    assert r.status_code == 201
    assert r.json()['asset_id'] == 5
    assert '/storage/v1/object/channeldesk-assets/' in r.json()['upload_url']


def test_public_news_unknown_page(monkeypatch):
    conn = patch_db(monkeypatch, [None])
    monkeypatch.setattr('api.public_news.connect', lambda: conn)
    r = client.get('/api/public-news/unknown')
    assert r.status_code == 404
