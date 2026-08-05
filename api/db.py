from __future__ import annotations
import os
import time
import psycopg
from fastapi import HTTPException

CONNECT_TIMEOUT = 4  # секунды; защита от зависания запросов к Supabase
CONNECT_RETRIES = 2


def database_url() -> str:
    value = os.getenv('DATABASE_URL', '').strip()
    if not value:
        raise HTTPException(status_code=503, detail='DATABASE_URL is not configured')
    return value.replace('postgresql+psycopg://', 'postgresql://').replace('postgresql+asyncpg://', 'postgresql://')


def connect():
    url = database_url()
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
