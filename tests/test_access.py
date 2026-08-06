import pytest
from fastapi import HTTPException

import api.access as access


@pytest.fixture(autouse=True)
def reset_access_cache():
    access._subscription_cache.clear()
    yield
    access._subscription_cache.clear()


def test_admin_bypasses_subscription_and_zbt(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '42')
    monkeypatch.setenv('ZBT_ENABLED', 'true')
    monkeypatch.setattr(access, 'required_channel_subscription', lambda *_args: False)
    access.require_access(42)


def test_unsubscribed_user_is_rejected(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '999')
    monkeypatch.setattr(access, 'required_channel_subscription', lambda *_args: False)
    with pytest.raises(HTTPException) as exc:
        access.require_access(42)
    assert exc.value.status_code == 403
    assert 'подпишитесь' in exc.value.detail


def test_subscribed_user_sees_zbt(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '999')
    monkeypatch.setenv('ZBT_ENABLED', 'true')
    monkeypatch.setattr(access, 'required_channel_subscription', lambda *_args: True)
    with pytest.raises(HTTPException) as exc:
        access.require_access(42)
    assert exc.value.status_code == 423
    assert 'Бот в разработке' in exc.value.detail


def test_subscribed_user_can_enter_when_zbt_disabled(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '999')
    monkeypatch.setenv('BETA_TESTER_IDS', '')
    monkeypatch.setenv('ZBT_ENABLED', 'false')
    monkeypatch.setattr(access, 'required_channel_subscription', lambda *_args: True)
    access.require_access(42)


def test_beta_tester_can_enter_during_zbt(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '999')
    monkeypatch.setenv('BETA_TESTER_IDS', '42')
    monkeypatch.setenv('ZBT_ENABLED', 'true')
    monkeypatch.setattr(access, 'required_channel_subscription', lambda *_args: True)
    access.require_access(42)
