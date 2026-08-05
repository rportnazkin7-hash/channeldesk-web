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


def test_sanitize_telegram_html_allows_formatting_and_drops_scripts():
    from api.posts import sanitize_telegram_html
    value = sanitize_telegram_html('<b>Жирный</b><script>alert(1)</script><a href="https://example.com">Ссылка</a>')
    assert '<b>Жирный</b>' in value
    assert '<a href="https://example.com">Ссылка</a>' in value
    assert 'script' not in value


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


def test_update_scheduled_ad_post(monkeypatch):
    scheduled = dict(POST_ROW, status='scheduled', approval_required=False, scheduled_at='2026-08-04T10:00:00Z')
    updated = dict(scheduled, title='Рекламный заголовок', text='Полный рекламный текст')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, scheduled, updated])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.patch('/api/workspaces/3/posts/10',
                     json={'title': 'Рекламный заголовок', 'text': 'Полный рекламный текст'},
                     headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'scheduled'
    assert r.json()['text'] == 'Полный рекламный текст'


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


def test_request_delete_from_telegram(monkeypatch):
    published = dict(POST_ROW, status='published', telegram_message_id=555)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, published, {'telegram_chat_id': -100123}, None, {'id': 7, 'status': 'pending'}])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/delete-from-telegram', headers=auth_headers())
    assert r.status_code == 202
    assert r.json()['status'] == 'pending'
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'cd_telegram_delete_jobs' in sql


def test_delete_from_telegram_status(monkeypatch):
    job = {'id': 7, 'status': 'processing', 'error_text': None, 'created_at': None, 'completed_at': None}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, POST_ROW, job])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.get('/api/workspaces/3/posts/10/delete-from-telegram', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'processing'


def test_schedule_requires_channel(monkeypatch):
    no_channel = dict(POST_ROW, channel_id=None, status='approved')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, no_channel])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/schedule', json={}, headers=auth_headers())
    assert r.status_code == 422
    assert 'канал' in r.json()['detail'].lower()


def test_reschedule_from_scheduled_allowed(monkeypatch):
    scheduled = dict(POST_ROW, status='scheduled', publish_key='abc123')
    rescheduled = dict(POST_ROW, status='scheduled', publish_key='abc123', scheduled_at='2026-08-04T11:00:00Z')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, scheduled, rescheduled])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/schedule',
                    json={'scheduled_at': '2026-08-04T11:00:00Z'}, headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'scheduled'
    assert r.json()['publish_key'] == 'abc123'  # ключ сохраняется


def test_reschedule_from_failed_allowed(monkeypatch):
    failed = dict(POST_ROW, status='failed', publish_key='key1', attempt_count=5, last_error='HTTP 400')
    rescheduled = dict(POST_ROW, status='scheduled', publish_key='key1', attempt_count=0, last_error=None)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, failed, rescheduled])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/publish-now', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'scheduled'
    assert r.json()['attempt_count'] == 0


def test_reschedule_from_cancelled_allowed(monkeypatch):
    cancelled = dict(POST_ROW, status='cancelled')
    rescheduled = dict(POST_ROW, status='scheduled', publish_key='newkey')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, cancelled, rescheduled])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/publish-now', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'scheduled'


def test_schedule_from_review_rejected(monkeypatch):
    review = dict(POST_ROW, status='review')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, review])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/publish-now', headers=auth_headers())
    assert r.status_code == 422
    assert 'одобрени' in r.json()['detail']


def test_draft_without_approval_can_schedule(monkeypatch):
    draft = dict(POST_ROW, status='draft', approval_required=False)
    scheduled = dict(POST_ROW, status='scheduled', publish_key='dkey')
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, draft, scheduled])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/publish-now', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()['status'] == 'scheduled'


def test_draft_with_approval_rejected(monkeypatch):
    draft = dict(POST_ROW, status='draft', approval_required=True)
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, draft])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts/10/publish-now', headers=auth_headers())
    assert r.status_code == 422
    assert 'одобрени' in r.json()['detail']


def test_create_post_with_buttons(monkeypatch):
    created = dict(POST_ROW, status='draft', buttons=[[{'text': 'Открыть', 'url': 'https://x.ru'}]])
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, {'id': 5}, created])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts',
                    json={'title': 'Кнопки', 'text': 'текст', 'channel_id': 5,
                          'buttons': [[{'text': 'Открыть', 'url': 'https://x.ru'}]]},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['buttons'] == [[{'text': 'Открыть', 'url': 'https://x.ru'}]]
    # кнопки записаны json-ом в INSERT
    calls = [call for cur in conn.cursors for call in cur.calls]
    insert = next(sql for sql, _ in calls if 'INSERT INTO cd_posts' in sql)
    assert 'buttons' in insert


def test_create_post_button_without_url_rejected(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, {'id': 5}])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts',
                    json={'title': 'x', 'text': 'y', 'buttons': [[{'text': 'Без ссылки'}]]},
                    headers=auth_headers())
    assert r.status_code == 422
    assert 'url' in r.json()['detail'].lower()


def test_create_post_button_invalid_url_rejected(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/posts',
                    json={'title': 'x', 'text': 'y', 'buttons': [[{'text': 'Бот', 'url': '@channel_desk_bot'}]]},
                    headers=auth_headers())
    assert r.status_code == 422
    assert 'https://' in r.json()['detail']


def test_templates_crud(monkeypatch):
    template = {'id': 1, 'workspace_id': 3, 'name': 'Анонс', 'title': 'Заголовок', 'text': 'Текст анонса'}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, template])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.post('/api/workspaces/3/templates', json={'name': 'Анонс', 'text': 'Текст анонса'},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['name'] == 'Анонс'


def test_list_posts_calendar_filter(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_OWNER, [POST_ROW]])
    monkeypatch.setattr('api.posts.connect', lambda: conn)
    r = client.get('/api/workspaces/3/posts',
                   params={'date_from': '2026-08-01T00:00:00Z', 'date_to': '2026-08-31T23:59:59Z'},
                   headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    calls = [call for cur in conn.cursors for call in cur.calls]
    select = next(sql for sql, _ in calls if 'FROM cd_posts' in sql)
    assert 'scheduled_at >= %s' in select and 'scheduled_at <= %s' in select


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
