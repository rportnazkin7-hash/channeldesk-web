from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer', 'last_name': None, 'is_blocked': False}
MEMBER_ADMIN = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
CHANNEL = {'id': 5, 'title': 'Новости'}
PAGE = {'id': 8, 'channel_title': 'Новости'}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_create_slot_page(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ADMIN, CHANNEL, PAGE])
    monkeypatch.setattr('api.slots.connect', lambda: conn)
    r = client.post('/api/workspaces/3/channels/5/public-slots', json={'default_cost': 15000}, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['path'].startswith('/public-slots?token=')


def test_get_public_slot_page(monkeypatch):
    page = {'id': 8, 'workspace_id': 3, 'channel_id': 5, 'title': 'Размещения', 'description': '',
            'default_cost': 15000, 'currency': 'RUB', 'channel_title': 'Новости', 'username': 'news', 'busy': []}
    conn = patch_db(monkeypatch, [page, []])
    monkeypatch.setattr('api.slots.connect', lambda: conn)
    r = client.get('/api/public/slots/some-token')
    assert r.status_code == 200
    assert r.json()['channel_title'] == 'Новости'


def test_public_slot_rejects_reversed_dates(monkeypatch):
    page = {'id': 8, 'workspace_id': 3, 'channel_id': 5, 'title': 'Размещения', 'description': '',
            'default_cost': 15000, 'currency': 'RUB', 'channel_title': 'Новости'}
    conn = patch_db(monkeypatch, [page])
    monkeypatch.setattr('api.slots.connect', lambda: conn)
    r = client.post('/api/public/slots/token/request', json={
        'contact_name': 'Реклама', 'start_date': '2026-08-20', 'end_date': '2026-08-19',
    })
    assert r.status_code == 422
