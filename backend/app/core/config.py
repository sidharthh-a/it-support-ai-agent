import os
from pathlib import Path
from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
try:
    # Prevents pydantic-settings from JSON-decoding complex fields (e.g. List[str]
    # BACKEND_CORS_ORIGINS) sourced from environment variables or .env files.
    # The comma-separated form is handled by the validator below; JSON form also works.
    from pydantic_settings import NoDecode
    from typing import Annotated
    CorsOrigins = Annotated[List[str], NoDecode]
except ImportError:  # pydantic-settings < 2.6 has no NoDecode annotation
    CorsOrigins = List[str]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent
ENV_FILES = [ROOT_DIR / ".env", BASE_DIR / ".env"]
LOAD_ENV_FILES = [str(f) for f in ENV_FILES if f.exists()] or [".env"]

DEFAULT_DEV_SECRET_KEY = "super-secret-development-key-change-in-prod"

VALID_ENVIRONMENTS = {"development", "staging", "production", "test"}
VALID_EMBEDDING_PROVIDERS = {"local", "openai"}


class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PROJECT_NAME: str = "IT Support AI Agent"
    VERSION: str = "1.1.0"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "127.0.0.1")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgrespassword")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "itsupport_db")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    DATABASE_URL: str | None = None

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # LLM & Embeddings
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY", None)
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY", None)
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")  # local or openai
    LOCAL_EMBEDDING_MODEL: str = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))

    # Security & CORS
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
    # No wildcard origins: explicit allow-list only (prod origins injected via env).
    BACKEND_CORS_ORIGINS: CorsOrigins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Rate limiting (requests per minute per client IP)
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_ENVIRONMENTS:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(VALID_ENVIRONMENTS)}, got '{v}'")
        return v

    @field_validator("EMBEDDING_PROVIDER")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_EMBEDDING_PROVIDERS:
            raise ValueError(f"EMBEDDING_PROVIDER must be one of {sorted(VALID_EMBEDDING_PROVIDERS)}, got '{v}'")
        return v

    @field_validator("EMBEDDING_DIMENSION")
    @classmethod
    def validate_embedding_dimension(cls, v: int) -> int:
        if v <= 0 or v > 4096:
            raise ValueError("EMBEDDING_DIMENSION must be a positive integer <= 4096")
        return v

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        # Accepts BOTH "a,b,c" (documented in .env.example / compose) and
        # JSON ["a","b"] forms, regardless of the source (env var, dotenv, init).
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                return json.loads(v)
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(f"Invalid CORS origins format: {v}")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        is_prod = self.ENVIRONMENT.lower() in ("production", "prod")
        if is_prod and self.SECRET_KEY == DEFAULT_DEV_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be explicitly set via environment variable in production mode and cannot use default dev key."
            )
        if is_prod and "*" in self.BACKEND_CORS_ORIGINS:
            raise ValueError("Wildcard CORS origin '*' is not allowed in production.")
        return self

    model_config = SettingsConfigDict(
        env_file=LOAD_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
