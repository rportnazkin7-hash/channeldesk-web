from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.workspaces import router as workspaces_router
from api.channels import router as channels_router
from api.posts import router as posts_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """При холодном старте применяет неприменённые миграции (идемпотентно)."""
    try:
        from api.migrate import apply_pending_migrations
        count = await asyncio.to_thread(apply_pending_migrations)
        if count:
            print(f'migrations applied at startup: {count}', flush=True)
    except Exception as exc:  # noqa: BLE001 — не даём упасть API при недоступной БД
        print(f'migration check skipped: {exc}', flush=True)
    yield


app = FastAPI(title='ChannelDesk API', version='0.8.0', lifespan=lifespan)
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-Telegram-Init-Data','X-Dev-Api-Key'])
app.include_router(workspaces_router)
app.include_router(channels_router)
app.include_router(posts_router)

@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'ChannelDesk API', 'version': '0.8.0'}
