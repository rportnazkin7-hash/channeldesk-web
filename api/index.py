from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.workspaces import router as workspaces_router
from api.channels import router as channels_router
from api.posts import router as posts_router
from api.assets import router as assets_router
from api.ads import router as ads_router
from api.media_kits import router as media_kits_router
from api.tasks import router as tasks_router
from api.analytics import router as analytics_router
from api.reports import router as reports_router
from api.tracking import router as tracking_router
from api.exports import router as exports_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """При холодном старте применяет миграции и создаёт storage bucket (идемпотентно)."""
    try:
        from api.migrate import apply_pending_migrations
        count = await asyncio.to_thread(apply_pending_migrations)
        if count:
            print(f'migrations applied at startup: {count}', flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f'migration check skipped: {exc}', flush=True)
    try:
        from api.assets import ensure_bucket
        await asyncio.to_thread(ensure_bucket)
    except Exception as exc:  # noqa: BLE001
        print(f'bucket check skipped: {exc}', flush=True)
    yield


app = FastAPI(title='ChannelDesk API', version='0.37.0', lifespan=lifespan)
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-Telegram-Init-Data','X-Dev-Api-Key'])
app.include_router(workspaces_router)
app.include_router(channels_router)
app.include_router(posts_router)
app.include_router(assets_router)
app.include_router(ads_router)
app.include_router(media_kits_router)
app.include_router(tasks_router)
app.include_router(analytics_router)
app.include_router(reports_router)
app.include_router(tracking_router)
app.include_router(exports_router)

@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'ChannelDesk API', 'version': '0.37.0'}


@app.get('/api/health/db-hash')
def health_db_hash():
    """Хэш DATABASE_URL со стороны Vercel — для сравнения с хэшем в /status бота."""
    import hashlib
    from api.db import database_url
    try:
        raw = database_url()
        return {'hash': hashlib.sha256(raw.encode()).hexdigest()[:10], 'host': raw.split('@')[-1]}
    except Exception as exc:
        return {'error': str(exc)}
@app.get('/api/health/migrations')
def health_migrations():
    """Список применённых миграций из schema_migrations (через БД — работает)."""
    try:
        from api.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT version, applied_at FROM schema_migrations ORDER BY applied_at')
            return {'ok': True, 'migrations': cur.fetchall()}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
@app.get('/api/health/storage')
def health_storage():
    """Диагностика хранилища (прямая загрузка из браузера).

    Сетевого запроса из Vercel не делаем — egress к supabase.co недоступен (EBUSY).
    Возвращаем host проекта (публичная информация) и что настроено/не настроено.
    """
    url = os.getenv('SUPABASE_URL', '').strip()
    anon = os.getenv('SUPABASE_ANON_KEY', '').strip()
    missing = []
    if not url:
        missing.append('SUPABASE_URL')
    if not anon:
        missing.append('SUPABASE_ANON_KEY')
    host = url.split('//')[-1] if url and '//' in url else (url or '')
    looks_like_key = bool(url) and ('_' in host or host.startswith('ey') or not url.startswith('https://'))
    return {'configured': not missing, 'missing': missing, 'host': host,
            'looks_like_key': looks_like_key,
            'mode': 'direct-browser-upload',
            'hint': 'Для прямой загрузки из браузера Supabase Storage должен разрешать CORS: '
                    'Supabase → Project Settings → API → Allowed Origins → добавить https://channeldesk.vercel.app (или *)'}
