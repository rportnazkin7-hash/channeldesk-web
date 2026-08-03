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


app = FastAPI(title='ChannelDesk API', version='0.10.0', lifespan=lifespan)
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-Telegram-Init-Data','X-Dev-Api-Key'])
app.include_router(workspaces_router)
app.include_router(channels_router)
app.include_router(posts_router)
app.include_router(assets_router)

@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'ChannelDesk API', 'version': '0.10.0'}


@app.get('/api/health/storage')
def health_storage():
    """Диагностика хранилища: настроены ли env и доступен ли Supabase Storage.
    Секреты не раскрываются — только статус."""
    import urllib.request
    url = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()
    if not url or not key:
        return {'configured': False, 'reason': 'SUPABASE_URL или SUPABASE_SERVICE_ROLE_KEY не заданы'}
    try:
        req = urllib.request.Request(f'{url}/storage/v1/bucket',
                                     headers={'Authorization': f'Bearer {key}'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {'configured': True, 'ok': True, 'status': resp.status}
    except Exception as exc:
        return {'configured': True, 'ok': False,
                'error': str(exc), 'errno': getattr(exc, 'errno', None)}
