from functools import lru_cache
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Playbook Tools API"
    environment: str = "dev"
    log_level: str = "info"

    openai_api_key: str | None = None

    # Root data directory — all sub-paths are derived from this.
    # Override via DATA_DIR env var so nothing is hardcoded in route files.
    data_dir: Path = Path("/repo/.data")

    # Allowed CORS origins.
    # In prod, set CORS_ORIGINS=["https://yourdomain.com"] in your .env.
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost"]

    # Postgres connection string.
    # The +asyncpg prefix tells SQLAlchemy to use the async driver.
    # Default points at the Docker service name "postgres".
    database_url: str = "postgresql+asyncpg://playbook:playbook@postgres:5432/playbook"

    # Secret key for signing JWTs. Must be long and random in production.
    # Generate a safe key: python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str = "change-me-in-production-use-secrets-token-hex-32"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    # --- Derived paths (properties, not env vars) ---

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def faiss_dir(self) -> Path:
        return self.data_dir / "faiss"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    # Why AsyncOpenAI: FastAPI is async. Calling the synchronous client inside
    # an async route handler blocks the event loop, stalling all other concurrent
    # requests until the network call returns. The async client yields control
    # back to the event loop while waiting for the response.
    #
    # Why lru_cache: AsyncOpenAI manages an internal connection pool. Creating a
    # new instance on every request throws that pool away. One cached instance
    # means connections are reused — lower latency, fewer TLS handshakes.
    return AsyncOpenAI(api_key=get_settings().openai_api_key)
