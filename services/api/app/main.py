from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.query import router as query_router
from app.routes.schemas import router as schemas_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data directories exist before any request is served.
    # Doing this here (not at module import time) keeps side effects explicit
    # and makes the app easier to test — you can override get_settings() before
    # the lifespan runs.
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.faiss_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown: nothing to clean up yet.


app = FastAPI(title="Playbook Tools API", version="0.1.0", lifespan=lifespan)

# --- CORS ---
# Why: without this, browsers block cross-origin requests from non-same-origin
# clients (mobile apps, different subdomains, Postman with CORS mode).
# Currently not required because Nginx proxies everything under one domain,
# but cheap insurance as the project grows.
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schemas_router)
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def read_config(settings: Settings = Depends(get_settings)):
    # Gate to non-production environments.
    # Even without secrets, exposing app_name + environment tells an attacker
    # exactly what stack they're targeting and that it's a dev/staging instance.
    if settings.environment == "production":
        return {"detail": "Not available in production."}
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "log_level": settings.log_level,
        "has_openai_key": bool(settings.openai_api_key),
    }
