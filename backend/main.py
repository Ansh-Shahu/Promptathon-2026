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
"""

from __future__ import annotations

import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from schemas import PredictionResponse, SensorPayload


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

    Startup:  Load ML model artifact from disk (stubbed here — swap the
              comment block for real model loading once model.pkl exists).
    Shutdown: Release any held resources (DB connections, GPU memory, etc.).

    Using the modern `lifespan` pattern instead of the deprecated
    `@app.on_event("startup")` decorator per FastAPI ≥ 0.93 best practices.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    # Record boot time as a timezone-aware UTC datetime so the /health endpoint
    # can compute uptime_seconds with sub-second precision on every request.
    # Stored on app.state to avoid module-level globals and ensure correctness
    # across hot-reloads (each reload re-enters lifespan, resetting the clock).
    app.state.start_time = datetime.now(timezone.utc)
    logger.info("🚀  HVAC Predictive Maintenance API starting up...")
    logger.warning(
        "⚠️  ML model not yet loaded — prediction endpoint is running in "
        "MOCK MODE based on ISO 10816 vibration threshold heuristic."
    )

    # ── FUTURE: Load trained model here ──────────────────────────────────────
    # import joblib
    # app.state.model = joblib.load("model.pkl")
    # logger.info("✅  Random Forest model loaded from model.pkl")

    yield  # Application runs while control is inside this block

    # ── Shutdown ──────────────────────────────────────────────────────────────
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
        "## Prediction Endpoint\n"
        "- **`POST /api/v1/predict`** — Submit a real-time sensor reading and "
        "receive a failure risk score, anomaly flag, and actionable maintenance alert.\n\n"
        "## Sensor Schema\n"
        "All 10 sensor parameters are validated against physical bounds wide "
        "enough to admit P-F curve degradation states. See `SensorPayload` for "
        "individual field constraints."
    ),
    version="0.1.0",
    contact={
        "name": "HVAC Platform — Hackathon Team",
        "email": "team@hvac-predictive.local",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
    # Disable the default /docs redirect from / to keep the root endpoint clean
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
    allow_origins=["*"],        # ← Tighten to specific origins in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — MOCK PREDICTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _mock_predict(payload: SensorPayload) -> PredictionResponse:
    """
    Apply ISO 10816 vibration threshold heuristic to generate a mocked
    prediction response.

    This function isolates all mock logic so it can be replaced in a single
    location when the real model is wired in. The caller (the route handler)
    does not need to change.

    Parameters
    ----------
    payload : SensorPayload
        Validated incoming sensor reading.

    Returns
    -------
    PredictionResponse
        Fully validated prediction response. Pydantic runs all response
        validators (precision normalisation, alert content enforcement)
        during instantiation — any logic bug here surfaces immediately.

    Raises
    ------
    ValueError
        If PredictionResponse instantiation fails its own validators
        (e.g., whitespace-only alert). Propagates to the route handler's
        except block and becomes an HTTP 500.
    """
    vibration: float = payload.vibration_rms

    # ── REPLACE WITH ML INFERENCE ─────────────────────────────────────────────
    # feature_vector = build_feature_vector(payload)   # your preprocessing fn
    # risk_score: float = app.state.model.predict_proba(feature_vector)[0][1]
    # is_anomalous: bool = risk_score >= 0.70
    # ─────────────────────────────────────────────────────────────────────────

    if vibration > ISO_10816_VIBRATION_THRESHOLD_MMS:
        # ── Anomalous branch ──────────────────────────────────────────────────
        risk_score: float = random.uniform(
            ANOMALOUS_RISK_SCORE_MIN,
            ANOMALOUS_RISK_SCORE_MAX,
        )
        is_anomalous: bool = True
        actionable_alert: str = (
            f"⚠️ HIGH RISK ({risk_score:.0%}): Vibration RMS of {vibration:.2f} mm/s "
            f"exceeds the ISO 10816 threshold of "
            f"{ISO_10816_VIBRATION_THRESHOLD_MMS} mm/s. "
            "Immediate bearing inspection recommended. "
            "Schedule maintenance within 72 hours to prevent unplanned downtime."
        )
    else:
        # ── Nominal branch ────────────────────────────────────────────────────
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
        failure_risk_score=risk_score,       # precision-normalised by field_validator
        is_anomalous=is_anomalous,
        actionable_alert=actionable_alert,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/",
    summary="Health Check",
    tags=["System"],
    response_description="API liveness confirmation.",
)
async def root() -> dict[str, str]:
    """
    Lightweight liveness probe.

    Returns a static JSON payload confirming the API is reachable.
    Suitable for load-balancer health checks and uptime monitors.
    """
    return {
        "status": "ok",
        "service": "HVAC Predictive Maintenance API",
        "version": "0.1.0",
        "docs": "/docs",
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
async def health_check(request: Request) -> dict:
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
      ran. Resets on every uvicorn hot-reload, which is intentional — a
      fresh reload is a fresh boot as far as state is concerned.
    - **ml_model_loaded** — Reflects whether `app.state.model` has been
      populated by the lifespan startup block. Currently `False` (mock mode).
    """
    now: datetime = datetime.now(timezone.utc)
    uptime: float = (now - request.app.state.start_time).total_seconds()

    return {
        "status":           "online",
        "engine":           "FastAPI",
        "version":          "0.1.0",
        "timestamp":        now.isoformat(),
        "uptime_seconds":   round(uptime, 3),
        "ml_model_loaded":  False,   # ← Flip to: hasattr(request.app.state, "model")
    }                                #   once model.pkl is loaded in lifespan


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
async def predict_failure_risk(payload: SensorPayload) -> PredictionResponse:
    """
    Accept a real-time HVAC chiller sensor reading and return a failure
    risk prediction.

    ### Current Behaviour (Mock Mode)
    Applies an **ISO 10816 vibration threshold heuristic**:
    - `vibration_rms > 4.5 mm/s` → High risk score (0.75–0.99), anomaly flagged.
    - `vibration_rms ≤ 4.5 mm/s` → Low risk score (0.01–0.15), nominal.

    ### Future Behaviour (Model Mode)
    Replace mock logic with `model.predict_proba(feature_vector)[0][1]`
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

        response: PredictionResponse = _mock_predict(payload)

        logger.info(
            "Prediction response generated | is_anomalous=%s | risk_score=%.6f",
            response.is_anomalous,
            response.failure_risk_score,
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