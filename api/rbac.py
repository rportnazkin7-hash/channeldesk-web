from __future__ import annotations
from fastapi import HTTPException

# Централизованная матрица разрешений: действие -> набор допустимых ролей.
# Это единый источник истины для новых маршрутов (постепенная миграция
# со старых require_roles / ROLE_LEVEL).
MATRIX: dict[str, frozenset[str]] = {
    'workspace.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'workspace.manage': frozenset({'owner','admin'}),

    'members.view': frozenset({'owner','admin','editor','analyst'}),
    'members.manage': frozenset({'owner','admin'}),

    'invite.create': frozenset({'owner','admin'}),

    'channel.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'channel.connect': frozenset({'owner','admin'}),

    'audit.view': frozenset({'owner','admin','analyst'}),

    # Публикации (Этап B)
    'post.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'post.create': frozenset({'owner','admin','editor','author'}),
    'post.edit': frozenset({'owner','admin','editor','author'}),
    'post.review': frozenset({'owner','admin','editor'}),
    'post.schedule': frozenset({'owner','admin','editor','ad_manager'}),
    'post.publish': frozenset({'owner','admin','editor'}),

    # Реклама и финансы (Этап C)
    'advertiser.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'advertiser.manage': frozenset({'owner','admin','ad_manager'}),
    'booking.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'booking.manage': frozenset({'owner','admin','ad_manager'}),
    'finance.view': frozenset({'owner','admin','analyst','ad_manager'}),
    'finance.manage': frozenset({'owner','admin','ad_manager'}),

    # Аналитика каналов: Bot API даёт только часть данных, остальное вводится вручную.
    'analytics.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'analytics.manage': frozenset({'owner','admin','ad_manager','analyst'}),

    # Медиакиты (Этап C)
    'media_kit.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'media_kit.manage': frozenset({'owner','admin','ad_manager','designer'}),

    # Задачи (Этап C)
    'task.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'task.manage': frozenset({'owner','admin','editor'}),
}


def require_action(member: dict, action: str) -> None:
    allowed = MATRIX.get(action)
    if allowed is None:
        raise HTTPException(status_code=500, detail=f'Неизвестное действие: {action}')
    if member.get('role') not in allowed:
        raise HTTPException(status_code=403, detail='Недостаточно прав')
