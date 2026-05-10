# backend/crud.py

"""
crud.py
─────────────────────────────────────────────────────────────────────────────
Data Access Object (DAO) layer for the HVAC Chiller Predictive Maintenance
persistence layer.

Single Responsibility Principle
────────────────────────────────
This module owns exactly one concern: translating between Python objects and
the database. It knows nothing about HTTP, Pydantic schemas, or ML inference.
The router layer knows nothing about SQL or session management. The boundary
between them is the function signatures in this file — dicts and ORM instances
in, ORM instances and lists out.

This separation produces three concrete engineering benefits:

  1. TESTABILITY: CRUD functions can be unit-tested by injecting a test
     database session without spinning up an HTTP server. The router tests can
     mock these functions entirely without touching a database.

  2. REUSABILITY: A background worker, a CLI management command, or a
     WebSocket handler can call these functions directly without duplicating
     SQL logic or coupling to FastAPI's dependency injection system.

  3. TRANSACTION ISOLATION: All session lifecycle decisions (when to commit,
     when to rollback, when to refresh) are made here, in one place, rather
     than scattered across route handlers where they are easy to forget.

SQLAlchemy 2.0 Query Style
───────────────────────────
All queries use the modern `select()` construct introduced in SQLAlchemy 2.0
rather than the legacy `db.query(Model)` style. The 2.0 style is:
  • Type-checker aware — mypy and pyright can infer result types.
  • Composable — `select()` statements can be built incrementally and passed
    between functions without executing.
  • Future-proof — `db.query()` is scheduled for removal in SQLAlchemy 3.0.
"""

import logging
from typing import Sequence

logger = logging.getLogger("hvac_api")

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import SensorTelemetryLog


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def create_sensor_log(
    db: Session,
    telemetry_data: dict,
    ml_outputs: dict,
) -> SensorTelemetryLog:
    """
    Persist a combined sensor telemetry reading and ML inference result as a
    single atomic row in the `sensor_logs` table.

    This function is the sole write entry point for the prediction pipeline.
    It receives data from two separate upstream sources — the validated
    SensorPayload dict from the Pydantic schema layer and the PredictionResponse
    dict from the ML inference layer — and merges them into a single ORM
    instance before committing. This merge is intentional: the two dicts
    arriving separately enforces the separation of concerns in the calling
    route handler (inference runs independently of persistence), while their
    combination here reflects the denormalised table design decision documented
    in models.py.

    Transaction Mechanics — add → commit → refresh
    ────────────────────────────────────────────────
    The three-step write sequence is a SQLAlchemy session lifecycle pattern
    that must not be abbreviated:

      db.add(log)
        Registers the new ORM instance with the session's identity map and
        marks it as "pending" (INSERT pending). No SQL is emitted yet.
        The session now tracks this object for the duration of the transaction.

      db.commit()
        Flushes all pending changes (emits the INSERT statement), commits the
        transaction to the database, and expires all attributes on all tracked
        instances. After commit, `log.id` exists in the database but the
        Python object's in-memory attribute cache has been invalidated —
        accessing `log.id` at this point would trigger a lazy SELECT to
        reload the row.

      db.refresh(log)
        Emits an explicit SELECT for the committed row, repopulating all
        attributes on the `log` instance from the database. This is what
        retrieves the auto-generated `id` value assigned by SQLite's
        autoincrement mechanism. Without this step, returning `log` from
        the function would cause a DetachedInstanceError the moment the
        caller accesses `log.id` after the session has been closed by the
        `get_db()` finally block.

    Why not use `db.flush()` instead of `db.commit()`?
    ────────────────────────────────────────────────────
    `flush()` emits the INSERT and populates `log.id` (making refresh()
    unnecessary), but leaves the transaction open. If the route handler
    raises an exception after the flush, the INSERT is rolled back — correct
    behaviour. However, the prediction API is a write-once endpoint: there
    is no subsequent operation in the same request that could roll back a
    valid telemetry write. Using `commit()` here makes the persistence
    contract explicit: a successful return from this function means the row
    is durably committed. The caller does not need to call `db.commit()`
    again.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session provided by the `get_db()` FastAPI
        dependency. The session's lifecycle (open/close) is managed by the
        dependency — this function must not close it.
    telemetry_data : dict
        Sensor reading fields from the validated SensorPayload, typically
        produced by calling `payload.model_dump()` in the route handler.
        Expected keys: timestamp, suction_temp, discharge_temp, suction_press,
        discharge_press, vibration_rms, power_draw, oil_pressure,
        runtime_hours, ambient_temp.
    ml_outputs : dict
        ML inference result fields from the PredictionResponse, typically
        produced by calling `response.model_dump()` in the route handler.
        Expected keys: failure_risk_score, is_anomalous, actionable_alert.
        The `timestamp` key in ml_outputs (echoed from the payload) is
        intentionally overwritten by telemetry_data's timestamp during the
        merge — both are identical, but telemetry_data is the authoritative
        source.

    Returns
    -------
    SensorTelemetryLog
        The persisted ORM instance with all columns populated, including the
        database-assigned `id`. Safe to access after the session closes
        because `db.refresh()` has eagerly loaded all attributes into the
        instance's in-memory state before the session lifecycle ends.
    """
    combined_data: dict = {**telemetry_data, **ml_outputs}
    log: SensorTelemetryLog = SensorTelemetryLog(**combined_data)

    try:
        db.add(log)
        db.commit()
        db.refresh(log)
    except Exception as exc:
        db.rollback()
        logger.error(
            "Database write failed in create_sensor_log — row discarded | error=%s",
            str(exc),
            exc_info=True,
        )
        raise

    return log


# ══════════════════════════════════════════════════════════════════════════════
#  READ OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_recent_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[SensorTelemetryLog]:
    """
    Retrieve a paginated window of sensor telemetry and prediction log entries,
    ordered from newest to oldest.

    This function backs both the dashboard's live feed endpoint and any
    paginated history view. The `skip` / `limit` pair maps directly to SQL
    OFFSET / LIMIT, enabling the caller to request any contiguous window of
    rows without loading the full table into application memory.

    Pagination Mechanics
    ────────────────────
    The query emitted is equivalent to:

        SELECT * FROM sensor_logs
        ORDER BY timestamp DESC
        LIMIT :limit OFFSET :skip;

    `skip=0, limit=100`  → rows 1–100   (dashboard default: latest 100)
    `skip=100, limit=100` → rows 101–200 (page 2 of a 100-row page size)
    `skip=900, limit=100` → rows 901–1000

    The ORDER BY timestamp DESC is applied before OFFSET and LIMIT, so
    page 1 always contains the newest rows regardless of `skip` value —
    consistent with a "latest first" dashboard display contract.

    SQLAlchemy 2.0 Query Construction
    ───────────────────────────────────
    `.offset()` and `.limit()` are composed onto the base `select()` statement
    before execution. SQLAlchemy emits them as bound parameters rather than
    interpolated integers, preventing SQL injection even if `skip` and `limit`
    originate from untrusted client query parameters.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session provided by the `get_db()` FastAPI
        dependency. Read-only within this function — no commit is performed.
    skip : int, optional
        Number of rows to skip from the top of the ordered result set.
        Defaults to 0 (start from the most recent row). Must be non-negative;
        callers should validate this at the router layer using
        `Query(ge=0)` to prevent negative offsets from producing undefined
        SQLite behaviour.
    limit : int, optional
        Maximum number of rows to return after the offset is applied.
        Defaults to 100. Callers should enforce an upper bound (e.g.,
        `Query(ge=1, le=1000)`) at the router layer to prevent accidental
        full-table scans on large datasets.

    Returns
    -------
    Sequence[SensorTelemetryLog]
        An ordered sequence of ORM instances for the requested page, newest
        first. Returns an empty list if `skip` exceeds the total row count.
        All instance attributes are fully populated and safe to access after
        the database session closes.
    """
    statement = (
        select(SensorTelemetryLog)
        .order_by(SensorTelemetryLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


# ══════════════════════════════════════════════════════════════════════════════
#  AGGREGATE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats(db: Session) -> dict:
    """
    Return a single-query aggregate snapshot of the sensor_logs table,
    designed to populate the KPI strip on the HVAC dashboard.

    Query Strategy — One Round-Trip
    ────────────────────────────────
    All aggregate values are computed in a single SELECT using SQLAlchemy's
    func layer, which emits the equivalent of:

        SELECT
            COUNT(*)                                          AS total_readings,
            SUM(IIF(is_anomalous, 1, 0))                     AS total_anomalies,
            MAX(failure_risk_score)                           AS max_risk_score,
            MAX(timestamp)                                    AS latest_reading_timestamp,
            AVG(failure_risk_score)                           AS avg_risk_score
        FROM sensor_logs;

    A single query prevents TOCTOU inconsistencies that would arise from
    separate COUNT / MAX queries executing at different moments against a
    live, write-active table.

    Proactive Addition — avg_risk_score
    ─────────────────────────────────────
    A session-wide average risk score is included alongside the session max.
    While max_risk_score surfaces the worst single event, avg_risk_score
    reveals *baseline drift* — a slowly rising average on an otherwise
    healthy fleet is the primary early signal of model staleness, long before
    any individual reading crosses an alert threshold. This metric costs zero
    extra DB round-trips and is far more actionable for ML ops than the max.

    Empty-DB Guard
    ──────────────
    SQLAlchemy returns None for MAX/AVG on an empty table (SQL NULL semantics).
    When total_readings == 0, safe sentinel values are returned so neither the
    Pydantic schema layer nor the frontend ever receives None for a numeric field.

    Parameters
    ----------
    db : Session
        Read-only SQLAlchemy session. No writes are performed.

    Returns
    -------
    dict
        Keys matching DashboardStatsResponse field names, plus avg_risk_score.
        All numeric values are Python native types (int / float), never None.

    Raises
    ------
    sqlalchemy.exc.SQLAlchemyError
        Propagated to the route handler on DB failure — the caller is
        responsible for catching this and returning HTTP 500.
    """
    try:
        # ── Single aggregate query ────────────────────────────────────────────
        result = db.execute(
            select(
                func.count().label("total_readings"),
                # IIF() is SQLite-native and maps to CASE WHEN in SQLAlchemy,
                # keeping this portable without FILTER (unsupported in SQLite < 3.30).
                func.sum(
                    func.iif(SensorTelemetryLog.is_anomalous, 1, 0)
                ).label("total_anomalies"),
                func.max(SensorTelemetryLog.failure_risk_score).label("max_risk_score"),
                func.max(SensorTelemetryLog.timestamp).label("latest_reading_timestamp"),
                func.avg(SensorTelemetryLog.failure_risk_score).label("avg_risk_score"),
            )
        ).one()
    except Exception as exc:
        logger.error(
            "Aggregate query failed in get_dashboard_stats | error=%s",
            str(exc),
            exc_info=True,
        )
        raise

    total_readings: int = result.total_readings or 0
    total_anomalies: int = result.total_anomalies or 0

    # ── Empty-DB guard ────────────────────────────────────────────────────────
    if total_readings == 0:
        return {
            "total_readings":           0,
            "total_anomalies":          0,
            "anomaly_rate_percentage":  0.0,
            "max_risk_score":           0.0,
            "avg_risk_score":           0.0,
            "latest_reading_timestamp": "N/A",
        }

    # ── Derived metric: anomaly rate ──────────────────────────────────────────
    # Computed in Python (not SQL) to keep the query portable and to let the
    # Pydantic DashboardStatsResponse validator normalise precision to 2 d.p.
    anomaly_rate: float = (total_anomalies / total_readings) * 100.0

    return {
        "total_readings":           total_readings,
        "total_anomalies":          total_anomalies,
        "anomaly_rate_percentage":  anomaly_rate,
        "max_risk_score":           result.max_risk_score or 0.0,
        "avg_risk_score":           result.avg_risk_score or 0.0,
        "latest_reading_timestamp": result.latest_reading_timestamp or "N/A",
    }