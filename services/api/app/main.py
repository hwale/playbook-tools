from fastapi import FastAPI, Depends
from app.core.config import Settings, get_settings
from app.routes.schemas import router as schemas_router
from app.routes.documents import router as documents_router
from app.routes.query import router as query_router

app = FastAPI(title="Playbook Tools API", version="0.1.0")

app.include_router(schemas_router)
app.include_router(documents_router)
app.include_router(query_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/config")
def read_config(settings: Settings = Depends(get_settings)):
    # Don't ever return secrets here in real life.
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "log_level": settings.log_level,
        "has_openai_key": bool(settings.openai_api_key),
    }