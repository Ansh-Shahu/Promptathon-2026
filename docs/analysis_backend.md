# HVAC Predictive Maintenance — Deep File & Folder Analysis: Backend

> **Generated:** 2026-05-26
> **Scope:** `backend/`

---

## 1. Backend Infrastructure (`backend/`)

The backend is a **FastAPI** application serving as the ML inference API, telemetry persistence layer, and dashboard data provider.

### `backend/.env`
- **Purpose:** Environment-specific configuration mappings.
- **Why it exists:** Separates secrets and environment configurations from code per the 12-factor app methodology, allowing the same codebase to run in dev, staging, and production securely.
- **What and why it uses:** Simple key-value pairs parsed by `python-dotenv` (via Pydantic).
- **Error Resilience:** Used in tandem with Pydantic Settings in `config.py` to ensure variables are present and typed correctly before the app boots.
- **Anomaly:** `SECRET_KEY` is set to a hardcoded placeholder string. This is a **P0 security issue** for production.
- **Future Scope / Improvements:** Add an `.env.example` file to the repository so new developers know exactly what variables are required without guessing.

### `backend/config.py`
- **Purpose:** Centralised, type-safe configuration singleton.
- **Why it exists:** Prevents scattered `os.getenv()` calls across the codebase, ensuring config is validated exactly once at startup.
- **What and why it uses:** `pydantic_settings.BaseSettings` for strict type enforcement and automatic environment variable injection.
- **Error Resilience:** Fails fast. Any misconfiguration (e.g., missing database URL, invalid log level) raises a `ValidationError` before the first HTTP request is served.
- **Future Scope / Improvements:** Add validation for `DATABASE_URL` to ensure it uses the correct driver prefix (e.g., `postgresql+psycopg2://`).

### `backend/database.py`
- **Purpose:** Database engine, session factory, and Dependency Injection setup.
- **Why it exists:** Encapsulates the SQLAlchemy connection lifecycle so the rest of the app doesn't deal with engine mechanics.
- **What and why it uses:** `SQLAlchemy` for ORM capabilities and connection pooling.
- **Error Resilience:** The `get_db()` dependency uses a strict `try...finally` block to yield sessions. This guarantees the connection is returned to the pool even if a fatal exception occurs during the request, preventing connection starvation.
- **Future Scope / Improvements:** Add `pool_pre_ping=True` to the engine creation to automatically handle dropped connections from the database server. 

### `backend/models.py`
- **Purpose:** SQLAlchemy ORM definitions mapping Python classes to database tables.
- **Why it exists:** Defines the structure of the `sensor_logs` table where all telemetry and ML inferences are stored.
- **What and why it uses:** Flat (denormalised) schema design. Since the primary access pattern is reading time-series data chronologically for charts, avoiding `JOIN` operations improves read latency.
- **Error Resilience:** Enforces `nullable=False` on all sensor metrics, preventing partial data rows from corrupting the time-series analysis.
- **Future Scope / Improvements:** Introduce table indexes on `timestamp` and `is_anomalous` to drastically speed up the `/history` and `/stats` endpoint queries as the table grows.

### `backend/schemas.py`
- **Purpose:** Pydantic models for HTTP request and response payloads.
- **Why it exists:** Acts as the authoritative API contract. Provides automatic validation, type coercion, and OpenAPI (Swagger) documentation generation.
- **What and why it uses:** `pydantic` v2 validators.
- **Error Resilience:** Highly resilient. It incorporates physical bounds checking (e.g., temps not exceeding physically possible limits) and thermodynamic cross-validation (e.g., suction pressure must be lower than discharge pressure). `extra="forbid"` drops requests with typos in field names.
- **Future Scope / Improvements:** Export these schemas as TypeScript interfaces automatically using a tool like `datamodel-code-generator` to keep the frontend `api.ts` perfectly in sync.

### `backend/crud.py`
- **Purpose:** The Data Access Object (DAO) layer handling raw database operations.
- **Why it exists:** Enforces the Single Responsibility Principle. Keeps SQL/ORM logic entirely separate from HTTP routing and ML logic.
- **What and why it uses:** SQLAlchemy `Session` objects to execute `INSERT` and `SELECT` statements.
- **Error Resilience:** Uses explicit `add -> commit -> refresh` sequences rather than passive flushing. If an insert fails, an explicit `db.rollback()` is caught and logged, preventing the session from becoming poisoned.
- **Future Scope / Improvements:** Implement asynchronous database queries via `sqlalchemy.ext.asyncio` to further improve throughput under heavy load.

### `backend/main.py`
- **Purpose:** The core FastAPI orchestrator.
- **Why it exists:** Mounts the routes, middleware, and ML model into a runnable web server.
- **What and why it uses:** `FastAPI` for routing, `joblib` for model loading. Uses `BackgroundTasks` to offload database writes.
- **Error Resilience:** 
  - Employs a robust `lifespan` context manager to load the ML model safely. If the model fails to load, it gracefully falls back to a mock mode (ISO 10816 heuristic) rather than crashing the server.
  - Database persistence is async: if the SQLite write fails, the client still receives their ML prediction, and the failure is logged server-side.
- **Future Scope / Improvements:** Split this file. Move the `POST /predict` and `GET /history` routes into a dedicated `routes/` directory using `APIRouter` to maintain readability as the API expands.

### `backend/model.pkl`
- **Purpose:** The serialised scikit-learn model artifact.
- **Why it exists:** Carries the mathematical weights of the Random Forest from the ML pipeline into the backend server.
- **Future Scope / Improvements:** Do not commit this file to Git. Use a model registry (like MLflow) or Git LFS.

### `backend/Makefile`
- **Purpose:** Command aliases for common developer tasks (`run`, `test`, `clean`, `check`).
- **Why it exists:** Standardises workflows so developers don't have to memorise complex shell commands.
- **Anomaly:** The `clean` target relies on Unix `find` commands, which will fail natively on Windows CMD/PowerShell.
- **Future Scope / Improvements:** Refactor the `clean` target using cross-platform tools (e.g., `python -c "import shutil... "`) or separate Linux/Windows targets.

### `backend/requirements.txt`
- **Purpose:** Pinned dependencies for the backend.
- **Anomaly:** `scikit-learn==1.8.0` clashes with the ML pipeline's `1.6.1`.
- **Future Scope / Improvements:** Align the versions to prevent deserialization bugs. Migrate to `pyproject.toml` for modern dependency management.

---

## 2. Tests (`backend/tests/`)

### `backend/tests/test_api.py`
- **Purpose:** Comprehensive integration test suite (121 tests, 3,144 lines).
- **Why it exists:** Guarantees that refactoring the backend or updating dependencies does not break the API contract or validation logic.
- **What and why it uses:** `pytest` and FastAPI `TestClient`.
- **Error Resilience:** Patches the ML inference function (`_mock_predict`) to guarantee deterministic responses. Tests physical edge cases, thermodynamic impossibilities, and malformed JSON payloads.
- **Future Scope / Improvements:** Split this massive file into smaller, targeted test files (e.g., `test_predict.py`, `test_validation.py`, `test_crud.py`). Add a fixtures file (`conftest.py`) if one does not exist or is missing.
