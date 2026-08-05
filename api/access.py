from __future__ import annotations

import os
import time
from fastapi import HTTPException

from api.telegram import required_channel_subscription

DEFAULT_REQUIRED_CHANNEL = '@thechanneldesk'
DEFAULT_REQUIRED_CHANNEL_URL = 'https://t.me/thechanneldesk'
SUBSCRIPTION_CACHE_TTL = 30.0
_subscription_cache: dict[tuple[int, str], tuple[float, bool | None]] = {}


def required_channel() -> str:
    return os.getenv('REQUIRED_CHANNEL', DEFAULT_REQUIRED_CHANNEL).strip() or DEFAULT_REQUIRED_CHANNEL


def required_channel_url() -> str:
    return os.getenv('REQUIRED_CHANNEL_URL', DEFAULT_REQUIRED_CHANNEL_URL).strip() or DEFAULT_REQUIRED_CHANNEL_URL


def admin_ids() -> set[int]:
    return {
        int(raw.strip())
        for raw in os.getenv('ADMIN_IDS', '').split(',')
        if raw.strip().isdigit()
    }


def is_admin(user_id: int) -> bool:
    return user_id in admin_ids()


def zbt_enabled() -> bool:
    """ЗБТ включён по умолчанию, чтобы закрытие не забыли при деплое."""
    raw = os.getenv('ZBT_ENABLED', 'true').strip().lower()
    return raw not in {'0', 'false', 'no', 'off'}


def _subscription_status(user_id: int) -> bool | None:
    channel = required_channel()
    key = (user_id, channel)
    now = time.monotonic()
    cached = _subscription_cache.get(key)
    if cached and now - cached[0] < SUBSCRIPTION_CACHE_TTL:
        return cached[1]
    status = required_channel_subscription(user_id, channel)
    _subscription_cache[key] = (now, status)
    return status


def require_access(user_id: int) -> None:
    """Закрывает все приватные API для неподписанных и обычных пользователей ЗБТ."""
    # ADMIN_IDS — единый белый список владельца/администраторов для бота и Mini App.
    if is_admin(user_id):
        return

    subscribed = _subscription_status(user_id)
    if subscribed is None:
        raise HTTPException(
            status_code=503,
            detail='Не удалось проверить подписку через Telegram. Попробуйте ещё раз через несколько секунд.',
        )
    if not subscribed:
        raise HTTPException(
            status_code=403,
            detail=f'Чтобы пользоваться ChannelDesk, подпишитесь на канал {required_channel_url()}.',
        )
    if zbt_enabled():
        raise HTTPException(
            status_code=423,
            detail=f'Бот в разработке. Следите за обновлениями в нашем канале: {required_channel_url()}',
        )
