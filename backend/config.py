# backend/config.py

"""
config.py
─────────────────────────────────────────────────────────────────────────────
Centralised, type-safe configuration management for the HVAC Chiller
Predictive Maintenance API.

Pydantic Settings loads variables from the `.env` file, validates their
types, and exposes them as a single `settings` singleton imported throughout
the application. This replaces scattered `os.getenv()` calls with a single
authoritative source of truth that fails fast at startup — a misconfigured
environment raises a `ValidationError` before the first request is served,
rather than a `KeyError` at the moment a misconfigured variable is first
accessed in a request handler.

Usage
─────
  from config import settings

  app = FastAPI(title=settings.PROJECT_NAME)
  engine = create_engine(settings.DATABASE_URL)
"""

import json
import os
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables and `.env`.

    All fields are strictly typed. Pydantic Settings resolves values in this
    priority order (highest to lowest):
      1. Actual environment variables set in the shell / container runtime
      2. Variables defined in the `.env` file
      3. Default values declared on each field

    This priority order means `.env` values are always overridable by the
    deployment environment without changing the file — correct 12-factor
    app behaviour.
    """

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        # Silently ignore extra variables present in the .env file that are
        # not declared as fields — prevents startup errors when the .env file
        # contains variables intended for other services in the same repo.
        extra="ignore",
    )

    # ── Environment ───────────────────────────────────────────────────────────

    ENVIRONMENT: str = Field(
        default="development",
        description=(
            "Deployment environment identifier. "
            "Controls behaviour such as debug mode, log verbosity, and "
            "whether detailed error responses are returned to clients. "
            "Expected values: 'development', 'staging', 'production'."
        ),
    )

    # ── Database ──────────────────────────────────────────────────────────────

    DATABASE_URL: str = Field(
        ...,
        description=(
            "SQLAlchemy database connection string. "
            "SQLite for local development; swap for a PostgreSQL DSN in "
            "production without any application code changes."
        ),
    )

    # ── API ───────────────────────────────────────────────────────────────────

    API_V1_STR: str = Field(
        default="/api/v1",
        description="URL prefix for all v1 API routes.",
    )

    PROJECT_NAME: str = Field(
        default="HVAC Predictive Maintenance API",
        description="Human-readable application name surfaced in OpenAPI metadata.",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────

    FRONTEND_CORS_ORIGINS: str = Field(
        ...,
        description=(
            "JSON-encoded list of allowed CORS origins. "
            "Stored as a raw string in the .env file to avoid shell quoting "
            "issues with list syntax. Parsed into List[str] via the "
            "`cors_origins_list` property at runtime."
        ),
    )

    # ── Security ──────────────────────────────────────────────────────────────

    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description=(
            "Cryptographic secret used for signing tokens and session state. "
            "Must be at least 32 characters. Generate a safe value with: "
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        ),
    )

    # ── Logging ───────────────────────────────────────────────────────────────

    LOG_LEVEL: str = Field(
        default="INFO",
        description=(
            "Python logging level for the application logger. "
            "Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
            "Defaults to INFO so production deployments are never accidentally "
            "left in DEBUG mode if the variable is omitted from the environment."
        ),
    )

    # ── ML Model ──────────────────────────────────────────────────────────────

    MODEL_PATH: str = Field(
        default="./model.pkl",
        description=(
            "Filesystem path to the serialised Scikit-Learn Random Forest "
            "model artifact. Relative paths are resolved from the working "
            "directory in which uvicorn is launched."
        ),
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("LOG_LEVEL")
    @classmethod
    def log_level_must_be_valid(cls, v: str) -> str:
        """
        Validate that LOG_LEVEL is one of Python's standard logging level
        names and normalise it to uppercase.

        Rationale
        ─────────
        Python's `logging.getLevelName()` is case-sensitive: passing "info"
        instead of "INFO" returns `None` in Python < 3.11 and raises a
        `ValueError` at the point the logger is configured — well after
        startup, and potentially mid-request. Validating and normalising here
        ensures the application fails immediately at boot with a clear message
        if an invalid level is set, rather than silently falling back to
        WARNING (the root logger default) and hiding diagnostic output.

        Parameters
        ----------
        v : str
            Raw LOG_LEVEL string from the environment or .env file.

        Returns
        -------
        str
            Uppercased, validated logging level name.

        Raises
        ------
        ValueError
            If the value is not one of the five standard Python logging levels.
        """
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalised = v.upper()
        if normalised not in allowed_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {sorted(allowed_levels)}; "
                f"received {v!r}."
            )
        return normalised

    # ── Computed Properties ───────────────────────────────────────────────────

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Parse the raw `FRONTEND_CORS_ORIGINS` JSON string into a typed list.

        The .env format stores the origins as a JSON array string:
            FRONTEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

        This property performs the JSON decode at access time so the rest of
        the application works with a clean `List[str]` rather than a raw JSON
        string, without requiring a Pydantic validator that would complicate
        the .env serialisation format.

        Returns
        -------
        List[str]
            Parsed list of allowed CORS origin strings.

        Raises
        ------
        ValueError
            If `FRONTEND_CORS_ORIGINS` is not valid JSON or does not decode
            to a list, surfacing the misconfiguration with a clear message.
        """
        try:
            parsed = json.loads(self.FRONTEND_CORS_ORIGINS)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"FRONTEND_CORS_ORIGINS must be a valid JSON array string. "
                f"Received: {self.FRONTEND_CORS_ORIGINS!r}. "
                f"JSON error: {exc}"
            ) from exc

        if not isinstance(parsed, list):
            raise ValueError(
                f"FRONTEND_CORS_ORIGINS must decode to a JSON array; "
                f"got {type(parsed).__name__!r}."
            )

        return parsed


# ══════════════════════════════════════════════════════════════════════════════
#  GLOBAL SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

settings = Settings()
"""
Application-wide configuration singleton.

Import this instance — not the `Settings` class — throughout the codebase:

    from config import settings

    engine = create_engine(settings.DATABASE_URL)
    app    = FastAPI(title=settings.PROJECT_NAME)

Instantiating `Settings()` once at module load time means:
  • The .env file is read and validated exactly once per process lifetime.
  • Any misconfiguration raises a Pydantic `ValidationError` at import time,
    preventing the application from starting in a broken state.
  • All modules share the same validated object — no repeated disk I/O or
    redundant os.getenv() calls scattered across the codebase.
"""