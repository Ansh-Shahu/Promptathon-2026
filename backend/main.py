# backend/main.py

"""
main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application entry point for the HVAC Chiller Predictive Maintenance
platform.

Execution
─────────
  Recommended (hot-reload for development):
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

  Alternative (direct Python execution):
    python main.py

API Contract
────────────
  POST /api/v1/predict
    Request  → schemas.SensorPayload
    Response → schemas.PredictionResponse

  GET  /api/v1/history
    Response → list[dict] — most recent 100 sensor + prediction log entries

  GET  /api/v1/health
    Response → liveness/readiness probe with uptime and model state

Mock Prediction Strategy
────────────────────────
  The Random Forest model is not yet trained. Until model.pkl is available,
  the prediction endpoint applies a deterministic ISO 10816 vibration
  threshold (4.5 mm/s) combined with random.uniform() score sampling to
  simulate realistic ML output variance. This allows the frontend team to
  build and test the dashboard against a live API immediately.

  Replace the block marked ── REPLACE WITH ML INFERENCE ── with:
    model.predict_proba(feature_vector)[0][1]
  when the trained model artifact is available.

Async Write Architecture
────────────────────────
  Database persistence is handled via FastAPI's BackgroundTasks mechanism.
  The HTTP response is returned to the client immediately after ML inference
  completes; the database write is dispatched as a non-blocking background
  task. This architecture guarantees:

    • P99 response latency is bounded by ML inference time only — SQLite I/O
      jitter (fsync latency, WAL checkpoint stalls) never appears in the
      client-facing latency distribution.
    • Under burst load, database writes queue behind the response without
      creating backpressure on the ASGI event loop.
    • A database write failure does not degrade the prediction response — the
      client receives a valid prediction regardless of persistence outcome.
      Persistence errors are logged server-side for async alerting.
"""

from __future__ import annotations

import logging
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Sequence

try:
    import joblib
    _JOBLIB_AVAILABLE = True
except ImportError:
    joblib = None  # type: ignore[assignment]
    _JOBLIB_AVAILABLE = False

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import crud
from database import Base, SessionLocal, engine, get_db
from schemas import DashboardStatsResponse, PredictionResponse, SensorPayload
from config import settings


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger: logging.Logger = logging.getLogger("hvac_api")


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# ISO 10816-3 velocity threshold for rotating machinery (mm/s RMS).
# Readings above this classify the machine as operating in the
# "Potentially Damaged" zone — our primary P-F curve trigger.
ISO_10816_VIBRATION_THRESHOLD_MMS: float = 4.5

# Mock risk score bands — widen or narrow these to tune alert sensitivity
# until the real model is wired in.
ANOMALOUS_RISK_SCORE_MIN: float = 0.75
ANOMALOUS_RISK_SCORE_MAX: float = 0.99
NOMINAL_RISK_SCORE_MIN: float = 0.01
NOMINAL_RISK_SCORE_MAX: float = 0.15


# ══════════════════════════════════════════════════════════════════════════════
#  LIFESPAN (startup / shutdown hooks)
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown lifecycle events.

    Startup
    ───────
    1. Record boot time on app.state for the /health uptime calculation.
    2. Materialise all SQLAlchemy ORM models as physical database tables via
       `Base.metadata.create_all(bind=engine)`. This is idempotent — it issues
       CREATE TABLE IF NOT EXISTS statements, so existing tables and their data
       are never dropped or truncated on restart. On first boot against a fresh
       SQLite file, this creates the `sensor_logs` table automatically without
       requiring a migration tool.
    3. Log mock-mode warning until model.pkl is available.

    Shutdown
    ────────
    Release any held resources. The SQLAlchemy connection pool is disposed
    automatically when the engine goes out of scope; explicit disposal here
    is a safety net for long-running process managers that reuse the engine
    across multiple lifespan cycles.

    Using the modern `lifespan` context manager pattern instead of the
    deprecated `@app.on_event("startup")` decorator per FastAPI ≥ 0.93
    best practices.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    app.state.start_time = datetime.now(timezone.utc)
    logger.info("🚀  HVAC Predictive Maintenance API starting up...")

    # Materialise ORM-declared tables into the SQLite file.
    # Safe to call on every restart — CREATE TABLE IF NOT EXISTS semantics.
    Base.metadata.create_all(bind=engine)
    logger.info("✅  Database tables verified / created via Base.metadata.create_all.")

    # ── Load trained ML model (graceful fallback to mock mode) ────────────────
    # joblib is imported at the top of this module with an ImportError guard.
    # If model.pkl is missing or corrupted the API stays online in mock mode
    # rather than crashing at startup.
    try:
        if not _JOBLIB_AVAILABLE:
            raise ImportError("joblib is not installed")
        model_path = os.path.join(os.path.dirname(__file__), settings.MODEL_PATH.lstrip("./"))
        app.state.model = joblib.load(model_path)
        logger.info("✅  ML model loaded from %s", model_path)
    except FileNotFoundError:
        app.state.model = None
        logger.warning(
            "⚠️  model.pkl not found at '%s' — prediction endpoint is running in "
            "MOCK MODE based on ISO 10816 vibration threshold heuristic.",
            settings.MODEL_PATH,
        )
    except Exception as exc:
        app.state.model = None
        logger.error(
            "❌  Failed to load ML model — falling back to MOCK MODE | error=%s",
            str(exc),
            exc_info=True,
        )

    yield  # Application runs while control is inside this block

    # ── Shutdown ──────────────────────────────────────────────────────────────
    engine.dispose()
    logger.info("🛑  HVAC Predictive Maintenance API shutting down.")


# ══════════════════════════════════════════════════════════════════════════════
#  APPLICATION FACTORY
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="HVAC Predictive Maintenance API",
    description=(
        "## Overview\n"
        "AI-driven anomaly detection for Commercial HVAC Chillers based on "
        "the **P-F (Potential-to-Failure) curve**, where vibration RMS is the "
        "primary leading indicator of impending mechanical failure.\n\n"
        "## Current Mode\n"
        "> ⚠️ **Mock Mode Active.** The Random Forest model is not yet trained. "
        "Predictions are generated using an ISO 10816 vibration threshold "
        "heuristic (`vibration_rms > 4.5 mm/s`) to unblock frontend development.\n\n"
        "## Endpoints\n"
        "- **`POST /api/v1/predict`** — Submit a real-time sensor reading and "
        "receive a failure risk score, anomaly flag, and actionable maintenance alert.\n"
        "- **`GET /api/v1/history`** — Retrieve the 100 most recent sensor "
        "readings and their associated ML prediction results.\n"
        "- **`GET /api/v1/health`** — Liveness and readiness probe.\n\n"
        "## Sensor Schema\n"
        "All 10 sensor parameters are validated against physical bounds wide "
        "enough to admit P-F curve degradation states. See `SensorPayload` for "
        "individual field constraints."
    ),
    version="0.1.0",
    contact={
        "name": "HVAC Platform — Hackathon Team",
        "email": "team@hvac-predictive.com",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ══════════════════════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════════════

# CORSMiddleware must be registered before routes so that preflight OPTIONS
# requests are resolved at the middleware layer. If registered after, FastAPI
# routes them to a 405 Method Not Allowed handler first.
#
# allow_credentials=False is intentional: the CORS spec prohibits pairing
# allow_credentials=True with allow_origins=["*"]. Browsers will block it.
# Tighten allow_origins to specific domains in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,        # ← Tighten to specific origins in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — MOCK PREDICTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _build_feature_vector(payload: SensorPayload) -> list[list[float]]:
    """
    Transform a validated SensorPayload into a 2D feature array suitable
    for scikit-learn's predict / predict_proba interface.

    Column order MUST match the order used during training in
    ml_pipeline/train_model.py:
        suction_temp, discharge_temp, suction_press, discharge_press,
        vibration_rms, power_draw, oil_pressure, runtime_hours, ambient_temp

    Parameters
    ----------
    payload : SensorPayload
        Validated incoming sensor reading.

    Returns
    -------
    list[list[float]]
        A 1×9 nested list representing a single sample feature vector.
    """
    return [[
        payload.suction_temp,
        payload.discharge_temp,
        payload.suction_press,
        payload.discharge_press,
        payload.vibration_rms,
        payload.power_draw,
        payload.oil_pressure,
        float(payload.runtime_hours),
        payload.ambient_temp,
    ]]


def _predict(payload: SensorPayload) -> PredictionResponse:
    """
    Generate a failure risk prediction using the trained Random Forest model.

    When `app.state.model` is loaded (model.pkl exists), this function builds
    a feature vector from the sensor payload and calls `predict_proba()` to
    obtain a calibrated probability of imminent failure. When the model is not
    available (mock mode), it falls back to the ISO 10816 vibration threshold
    heuristic to keep the API functional for frontend development.

    Parameters
    ----------
    payload : SensorPayload
        Validated incoming sensor reading.

    Returns
    -------
    PredictionResponse
        Fully validated prediction response with risk score, anomaly flag,
        and actionable alert text.
    """
    vibration: float = payload.vibration_rms
    temp: float = payload.discharge_temp
    power: float = payload.power_draw
    model = app.state.model

    if model is not None:
        # ── REAL ML INFERENCE ─────────────────────────────────────────────────
        feature_vector = _build_feature_vector(payload)
        risk_score: float = float(model.predict_proba(feature_vector)[0][1])
        is_anomalous: bool = risk_score >= 0.70

        logger.info(
            "ML inference complete | risk_score=%.6f | is_anomalous=%s",
            risk_score, is_anomalous,
        )

        if is_anomalous:
            # Dynamic root cause analysis based on telemetry
            issues = []
            actions = []
            if vibration > 4.5:
                issues.append(f"Vibration at {vibration:.1f} mm/s")
                actions.append("bearing inspection")
            if temp > 150.0:
                issues.append(f"Temp at {temp:.0f}°F")
                actions.append("coolant check")
            if power > 350.0:
                issues.append(f"Power at {power:.0f} kW")
                actions.append("motor winding diagnostic")
            
            if not issues:
                issues.append("Complex multi-parameter degradation")
                actions.append("comprehensive system diagnostic")

            issue_str = " | ".join(issues)
            action_str = " & ".join(actions)
            urgency = "CRITICAL RISK" if risk_score >= 0.90 else "HIGH RISK"
            window = "24 hours" if risk_score >= 0.90 else "72 hours"

            actionable_alert: str = (
                f"⚠️ {urgency} ({risk_score:.0%}): {issue_str}. "
                f"Immediate {action_str} recommended. "
                f"Schedule maintenance within {window}."
            )
        else:
            actionable_alert = (
                f"✅ NOMINAL ({risk_score:.0%}): ML model assessed failure "
                f"probability at {risk_score:.4f}. All parameters within "
                "normal range. No action required."
            )
    else:
        # ── FALLBACK: ISO 10816 MOCK MODE ─────────────────────────────────────
        logger.warning("Model not loaded — using mock heuristic for prediction.")

        if vibration > ISO_10816_VIBRATION_THRESHOLD_MMS:
            risk_score = random.uniform(
                ANOMALOUS_RISK_SCORE_MIN,
                ANOMALOUS_RISK_SCORE_MAX,
            )
            is_anomalous = True
            urgency = "CRITICAL RISK" if risk_score >= 0.90 else "HIGH RISK"
            actionable_alert = (
                f"⚠️ {urgency} ({risk_score:.0%}): Vibration RMS of {vibration:.2f} mm/s "
                f"exceeds threshold. Immediate bearing inspection recommended. "
                "Schedule maintenance within 72 hours."
            )
        else:
            risk_score = random.uniform(
                NOMINAL_RISK_SCORE_MIN,
                NOMINAL_RISK_SCORE_MAX,
            )
            is_anomalous = False
            actionable_alert = (
                f"✅ NOMINAL ({risk_score:.0%}): Vibration RMS of {vibration:.2f} mm/s "
                f"is within the ISO 10816 healthy range "
                f"(< {ISO_10816_VIBRATION_THRESHOLD_MMS} mm/s). "
                "No maintenance action required. Continue scheduled monitoring."
            )

    return PredictionResponse(
        timestamp=payload.timestamp,
        failure_risk_score=risk_score,
        is_anomalous=is_anomalous,
        actionable_alert=actionable_alert,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/",
    summary="Root — API Liveness",
    tags=["System"],
    response_description="Static liveness confirmation payload.",
)
async def root() -> dict[str, str]:
    """
    Lightweight root liveness probe.

    Returns a static JSON payload confirming the API is reachable.
    Suitable for load-balancer health checks and uptime monitors that
    do not require the richer metadata provided by /api/v1/health.
    """
    return {
        "status":  "ok",
        "service": "HVAC Predictive Maintenance API",
        "version": "0.1.0",
        "docs":    "/docs",
    }


@app.get(
    "/api/v1/health",
    status_code=status.HTTP_200_OK,
    summary="Readiness & Liveness Probe",
    tags=["System"],
    response_description=(
        "Server status, engine metadata, ISO 8601 timestamp, uptime in seconds, "
        "and ML model load state."
    ),
    responses={
        200: {"description": "Server is online and ready to accept requests."},
    },
)
async def health_check(request: Request) -> dict[str, Any]:
    """
    Readiness and liveness probe for load balancers, orchestrators, and the
    frontend latency monitor.

    All work is O(1): two `datetime.now()` calls and a subtraction. Safe to
    hammer at any polling frequency without measurable performance impact.

    ### Response Fields
    - **status** — Always `"online"` when this endpoint is reachable.
    - **engine** — Framework identifier for infrastructure routing rules.
    - **version** — API semver; mirrors the value declared in the app factory.
    - **timestamp** — Current server UTC time in ISO 8601 format. Clients can
      diff this against their local clock to estimate one-way network latency.
    - **uptime_seconds** — Fractional seconds since the lifespan startup hook
      ran. Resets on every uvicorn hot-reload.
    - **ml_model_loaded** — Reflects whether `app.state.model` has been
      populated by the lifespan startup block. Currently `False` (mock mode).
    """
    now: datetime = datetime.now(timezone.utc)
    uptime: float = (now - request.app.state.start_time).total_seconds()

    return {
        "status":          "online",
        "engine":          "FastAPI",
        "version":         "0.1.0",
        "timestamp":       now.isoformat(),
        "uptime_seconds":  round(uptime, 3),
        "ml_model_loaded": getattr(request.app.state, "model", None) is not None,
    }


@app.post(
    "/api/v1/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict Failure Risk from Sensor Payload",
    tags=["Prediction"],
    response_description=(
        "Failure risk score (0–1), anomaly flag, and actionable maintenance alert."
    ),
    responses={
        200: {"description": "Prediction successfully generated."},
        422: {
            "description": (
                "Validation Error — one or more sensor fields failed physical "
                "bounds checks or cross-field constraints (e.g., suction pressure "
                "exceeds discharge pressure). No prediction is generated."
            )
        },
        500: {
            "description": (
                "Internal Server Error — unexpected failure in the prediction "
                "engine. The raw error is logged server-side but not returned "
                "to the client."
            )
        },
    },
)
async def predict_failure_risk(
    payload: SensorPayload,
    background_tasks: BackgroundTasks,
) -> PredictionResponse:
    """
    Accept a real-time HVAC chiller sensor reading, generate a failure risk
    prediction, and asynchronously persist the combined reading + prediction
    to the database without blocking the HTTP response.

    ### Async Write Architecture
    ML inference is synchronous and CPU-bound; database I/O is asynchronous
    and unpredictably slow under SQLite WAL checkpoint pressure. To prevent
    SQLite I/O jitter from inflating P99 prediction latency, the database
    write is dispatched via `background_tasks.add_task()`. The client receives
    the `PredictionResponse` immediately after inference completes; the
    `crud.create_sensor_log()` call executes after the response has been sent.

    This means a database write failure does not degrade the prediction
    response delivered to the SCADA client — persistence errors are logged
    server-side without impacting the real-time safety alert pipeline.

    ### Current Behaviour (Mock Mode)
    Applies an **ISO 10816 vibration threshold heuristic**:
    - `vibration_rms > 4.5 mm/s` → High risk score (0.75–0.99), anomaly flagged.
    - `vibration_rms ≤ 4.5 mm/s` → Low risk score (0.01–0.15), nominal.

    ### Future Behaviour (Model Mode)
    Replace mock logic in `_mock_predict()` with:
        `model.predict_proba(feature_vector)[0][1]`
    once the Scikit-Learn Random Forest artifact is available.

    ### Validation
    Pydantic validates the request body automatically before this function
    runs. A `422 Unprocessable Entity` is returned by FastAPI if any field
    fails — no manual validation code is needed here.
    """
    try:
        logger.info(
            "Prediction request received | timestamp=%s | vibration_rms=%.4f mm/s",
            payload.timestamp.isoformat(),
            payload.vibration_rms,
        )

        response: PredictionResponse = _predict(payload)

        logger.info(
            "Prediction response generated | is_anomalous=%s | risk_score=%.6f",
            response.is_anomalous,
            response.failure_risk_score,
        )

        # ── Async persistence — fire-and-forget after response is sent ────────
        # IMPORTANT: We do NOT pass the request-scoped `db` session here.
        # FastAPI tears down Depends() sessions after the response is sent,
        # which races with background task execution and causes DetachedInstanceError.
        # Instead, the background task opens its own independent session.
        prediction_dict: dict[str, Any] = {
            "failure_risk_score": response.failure_risk_score,
            "is_anomalous":       response.is_anomalous,
            "actionable_alert":   response.actionable_alert,
        }

        def _persist_in_background(telemetry: dict, prediction: dict) -> None:
            """Open a dedicated session scoped to this background write only."""
            bg_db = SessionLocal()
            try:
                crud.create_sensor_log(bg_db, telemetry, prediction)
            finally:
                bg_db.close()

        background_tasks.add_task(
            _persist_in_background,
            payload.model_dump(),
            prediction_dict,
        )

        return response

    except HTTPException:
        # Re-raise any HTTPException raised intentionally (e.g., from helpers).
        # Must be re-raised before the generic except block catches it.
        raise

    except Exception as exc:
        # Catch all unexpected server-side errors. Log the full traceback
        # internally but return only a generic 500 to the client — never
        # leak raw stack traces or internal state to the wire.
        logger.exception(
            "Unhandled exception in predict_failure_risk | error=%s", str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An unexpected error occurred while processing the prediction. "
                "The error has been logged. Please retry or contact support."
            ),
        ) from exc

@app.get(
    "/api/v1/history",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Paginated Sensor and Prediction History",
    tags=["History"],
    response_description=(
        "Paginated list of sensor telemetry readings and their associated ML "
        "prediction results, ordered newest first."
    ),
    responses={
        200: {"description": "History page retrieved successfully."},
        422: {
            "description": (
                "Validation Error — `skip` is negative or `limit` exceeds "
                "the maximum permitted value of 1000."
            )
        },
        500: {
            "description": (
                "Internal Server Error — unexpected failure reading from the "
                "database. The raw error is logged server-side."
            )
        },
    },
)
async def get_prediction_history(
    db: Session = Depends(get_db),
    skip: int = Query(
        default=0,
        ge=0,
        description=(
            "Number of rows to skip from the top of the newest-first ordered "
            "result set. Use in combination with `limit` to implement "
            "offset-based pagination. Must be non-negative."
        ),
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description=(
            "Maximum number of rows to return after the offset is applied. "
            "Defaults to 100. Capped at 1000 to prevent full-table scans "
            "from degrading server performance under concurrent load."
        ),
    ),
) -> list[dict[str, Any]]:
    """
    Retrieve a paginated window of sensor telemetry readings and their
    associated ML prediction results from the persistence layer.

    ### Pagination
    Use `skip` and `limit` as query parameters to navigate the history:
    - `GET /api/v1/history` → latest 100 rows (dashboard default)
    - `GET /api/v1/history?skip=100&limit=100` → rows 101–200
    - `GET /api/v1/history?skip=0&limit=25` → latest 25 rows only

    Results are always ordered by `timestamp` descending (newest first),
    so page 1 (`skip=0`) always contains the most recent readings regardless
    of the `limit` value chosen.

    ### Guardrails
    Both `skip` and `limit` are validated by FastAPI's `Query` dependency
    before the route handler executes. Requests with `skip < 0` or
    `limit > 1000` are rejected with a `422 Unprocessable Entity` before
    any database I/O is attempted — protecting the connection pool from
    abusive or accidental full-table scan requests.

    ### Persistence Lag
    Because predictions are written via `BackgroundTasks`, there is a small
    window (typically < 100ms) between a prediction response being delivered
    and its corresponding row appearing in the history. This is acceptable
    for a dashboard polling every few seconds; synchronous writes would be
    required for a strictly consistent audit log.
    """
    try:
        logs: Sequence = crud.get_recent_logs(db, skip=skip, limit=limit)
        return [log.to_dict() for log in logs]

    except Exception as exc:
        logger.exception(
            "Unhandled exception in get_prediction_history | error=%s", str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An unexpected error occurred while retrieving prediction history. "
                "The error has been logged. Please retry or contact support."
            ),
        ) from exc


@app.get(
    "/api/v1/stats",
    response_model=DashboardStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard KPI Aggregate Statistics",
    tags=["Stats"],
    response_description=(
        "Aggregate KPI snapshot: total readings, anomaly count, anomaly rate, "
        "peak risk score, average risk score, and latest reading timestamp."
    ),
    responses={
        200: {"description": "Aggregate stats computed successfully."},
        500: {
            "description": (
                "Internal Server Error — database aggregate query failed. "
                "The error is logged server-side."
            )
        },
    },
)
async def get_stats(
    db: Session = Depends(get_db),
) -> DashboardStatsResponse:
    """
    Return a single-query KPI snapshot from the `sensor_logs` table.

    All five aggregate values (COUNT, SUM, MAX x2, AVG) are computed in
    one database round-trip by `crud.get_dashboard_stats()`. Results are
    validated and precision-normalised by the `DashboardStatsResponse`
    Pydantic schema before being returned to the client.

    ### Metrics
    - **total_readings** — Total rows in sensor_logs.
    - **total_anomalies** — Rows where is_anomalous=True.
    - **anomaly_rate_percentage** — (anomalies / readings) × 100, rounded to 2 d.p.
    - **max_risk_score** — Session peak failure risk (0–1), rounded to 6 d.p.
    - **avg_risk_score** — Baseline average risk for model drift monitoring.
    - **latest_reading_timestamp** — ISO 8601 string of the most recent row.

    Returns sentinel zeros and `"N/A"` timestamp when the database is empty.
    """
    from sqlalchemy.exc import SQLAlchemyError

    try:
        stats: dict = crud.get_dashboard_stats(db)
        return DashboardStatsResponse(**stats)
    except SQLAlchemyError as exc:
        logger.error(
            "Database error in get_stats | error=%s", str(exc), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to compute dashboard statistics. "
                "The database query encountered an error. "
                "Please retry or contact support."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in get_stats | error=%s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving statistics.",
        ) from exc


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Alternative to `uvicorn main:app --reload`.
    # Useful for IDE debugging (set breakpoints, step through routes).
    # For production, always prefer the uvicorn CLI with process management
    # (e.g., gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app).
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )