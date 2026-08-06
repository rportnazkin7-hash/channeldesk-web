from __future__ import annotations
import os
import threading
import time
import psycopg
from fastapi import HTTPException

try:
    from psycopg_pool import ConnectionPool, PoolTimeout
except ImportError:  # локальная среда без optional pool dependency
    ConnectionPool = None
    PoolTimeout = TimeoutError

CONNECT_TIMEOUT = 4  # секунды; защита от зависания запросов к Supabase
CONNECT_RETRIES = 2
POOL_MIN_SIZE = 0
POOL_MAX_SIZE = 4
_pool = None
_pool_url = None
_pool_lock = threading.Lock()


def database_url() -> str:
    value = os.getenv('DATABASE_URL', '').strip()
    if not value:
        raise HTTPException(status_code=503, detail='DATABASE_URL is not configured')
    return value.replace('postgresql+psycopg://', 'postgresql://').replace('postgresql+asyncpg://', 'postgresql://')


def _pool_enabled() -> bool:
    raw = os.getenv('DB_POOL_ENABLED', 'true').strip().lower()
    return raw not in {'0', 'false', 'no', 'off'}


def _get_pool(url: str):
    global _pool, _pool_url
    if ConnectionPool is None:
        return None
    with _pool_lock:
        if _pool is None or _pool_url != url:
            if _pool is not None:
                try:
                    _pool.close()
                except Exception:
                    pass
            _pool = ConnectionPool(
                conninfo=url,
                kwargs={'row_factory': psycopg.rows.dict_row, 'connect_timeout': CONNECT_TIMEOUT},
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                timeout=CONNECT_TIMEOUT,
                open=True,
            )
            _pool_url = url
        return _pool


def connect():
    url = database_url()
    if _pool_enabled():
        pool = _get_pool(url)
        if pool is not None:
            try:
                # Возвращается context manager: with connect() вернёт соединение
                # в pool, а не создаст новый TCP-коннект на каждый запрос.
                return pool.connection(timeout=CONNECT_TIMEOUT)
            except (PoolTimeout, psycopg.Error) as exc:
                raise HTTPException(status_code=503,
                                    detail='База данных временно перегружена. Повторите через несколько секунд.') from exc

    for attempt in range(CONNECT_RETRIES):
        try:
            return psycopg.connect(url, row_factory=psycopg.rows.dict_row, connect_timeout=CONNECT_TIMEOUT)
        except psycopg.OperationalError:
            if attempt + 1 < CONNECT_RETRIES:
                time.sleep(0.15)
                continue
            raise HTTPException(status_code=503, detail='База данных временно недоступна. Повторите через несколько секунд.')
        except psycopg.Error:
            raise HTTPException(status_code=503, detail='База данных недоступна. Проверьте DATABASE_URL и подключение Supabase.')
    raise HTTPException(status_code=503, detail='База данных временно недоступна. Повторите через несколько секунд.')
