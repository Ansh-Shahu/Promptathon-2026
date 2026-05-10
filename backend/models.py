# backend/models.py

"""
models.py
─────────────────────────────────────────────────────────────────────────────
SQLAlchemy 2.0 ORM model definitions for the HVAC Chiller Predictive
Maintenance persistence layer.

Design Philosophy — Co-located Telemetry and Inference Storage
───────────────────────────────────────────────────────────────
Each row in `sensor_logs` captures a complete, atomic event: the raw sensor
reading as it arrived from the SCADA edge device AND the ML model's inference
result for that exact reading. Storing both in the same row is a deliberate
architectural choice with three consequences:

  1. AUDIT TRAIL: Every prediction is permanently traceable to the exact
     sensor state that produced it. When a maintenance engineer reviews a
     historical alert, they can see precisely which vibration reading (and
     all co-occurring sensor values) triggered the model's decision — without
     needing to JOIN across tables or reconstruct state from an event log.

  2. MODEL RETRAINING: The co-located schema makes it trivial to export a
     labelled training dataset. A simple SELECT * FROM sensor_logs WHERE
     is_anomalous = 1 produces a correctly labelled positive-class dataset
     for the next Random Forest training cycle, with no feature engineering
     required at export time.

  3. DRIFT DETECTION: Time-series queries over `failure_risk_score` against
     the raw sensor values allow the ML operations team to detect model drift
     — cases where sensor readings have drifted into new operating regimes
     that the current model has never seen, without the risk score reflecting
     the true degradation state.
"""

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# ══════════════════════════════════════════════════════════════════════════════
#  ORM MODEL
# ══════════════════════════════════════════════════════════════════════════════

class SensorTelemetryLog(Base):
    """
    ORM mapping for the `sensor_logs` database table.

    Each row represents one complete telemetry event: a single sensor reading
    cycle received from a Commercial HVAC Chiller edge device, paired with the
    ML inference result produced by the Random Forest prediction endpoint at
    the moment that reading was processed.

    Table Design Rationale
    ──────────────────────
    The table is intentionally denormalised (flat) rather than split into a
    `readings` table and a `predictions` table. For a time-series workload
    dominated by sequential INSERTs and time-range SELECTs, a flat schema
    outperforms a normalised schema because:

      • No JOIN overhead on the dominant read pattern (retrieve reading + its
        prediction in a single row scan).
      • SQLite's B-tree index on `timestamp` supports efficient range queries
        (e.g., "all anomalous readings in the last 24 hours") without a
        covering index that spans multiple tables.
      • The write path is a single INSERT per prediction request rather than
        a multi-statement transaction across two tables, reducing lock
        contention under concurrent SCADA ingestion.

    Indexing Strategy
    ─────────────────
    `id`        — Primary key index: required for O(1) single-row retrieval
                  by the admin dashboard's "view reading by ID" endpoint.
    `timestamp` — Secondary index: the dominant filter predicate in all
                  time-series queries. Without this index, a "last 1000
                  readings" query performs a full table scan that degrades
                  linearly as the table grows toward millions of rows.

    SQLAlchemy 2.0 Typed Mapping
    ─────────────────────────────
    All columns use the `Mapped[T] = mapped_column(...)` syntax introduced in
    SQLAlchemy 2.0. This provides:
      • Full static type checker (mypy / pyright) awareness of column types.
      • Elimination of the legacy `Column(Type, ...)` pattern which carried
        no Python-level type information and required separate type stubs.
      • Runtime validation that ORM-constructed instances carry the correct
        Python types before any SQL is emitted.
    """

    __tablename__: str = "sensor_logs"

    # ── Primary Key ───────────────────────────────────────────────────────────

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        doc=(
            "Auto-incrementing surrogate primary key. "
            "Used by the dashboard API for stable single-row retrieval "
            "(GET /api/v1/readings/{id}) and as a pagination cursor in "
            "keyset-paginated list endpoints. "
            "SQLite assigns these sequentially and without gaps under normal "
            "operation; gaps may appear if INSERTs are rolled back."
        ),
    )

    # ── Temporal Anchor ───────────────────────────────────────────────────────

    timestamp: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
        doc=(
            "ISO 8601 timestamp of the sensor reading as received from the "
            "SCADA edge device, stored as a string to preserve the exact "
            "format transmitted by the client (e.g., '2024-06-15T14:00:00'). "
            "Stored as String rather than SQLAlchemy's DateTime type to avoid "
            "timezone-aware vs. naive datetime coercion issues across different "
            "SQLite driver versions. "
            "Indexed to support efficient time-range queries: the dominant "
            "access pattern for the dashboard's historical trend charts."
        ),
    )

    # ── Physical Sensor Readings ───────────────────────────────────────────────
    #
    #  All sensor fields are non-nullable. A row must represent a complete,
    #  validated sensor reading — partial rows with NULL sensor values would
    #  corrupt the ML feature vector on any retraining SELECT and are rejected
    #  at the Pydantic schema layer before reaching the persistence layer.

    vibration_rms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Compressor bearing vibration, root-mean-square velocity (mm/s). "
            "PRIMARY P-F CURVE LEADING INDICATOR. "
            "ISO 10816-3 healthy threshold: < 4.5 mm/s. "
            "Values above this threshold are the earliest detectable signal "
            "of impending bearing failure — preceding thermal and electrical "
            "degradation by hours to days depending on failure mode. "
            "This column is the most important feature in the Random Forest "
            "model and should be the first column inspected when reviewing "
            "historical anomaly events."
        ),
    )

    suction_temp: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Refrigerant temperature at the compressor suction port (°F). "
            "Healthy range: 38–44 °F. "
            "Reflects the degree of superheat in the refrigerant leaving the "
            "evaporator. A sustained drop below 35 °F indicates refrigerant "
            "floodback (liquid refrigerant entering the compressor), which "
            "causes immediate mechanical damage. A rise above 50 °F indicates "
            "loss of refrigerant charge or evaporator fouling."
        ),
    )

    discharge_temp: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Refrigerant temperature at the compressor discharge port (°F). "
            "Healthy range: 95–105 °F. "
            "LAGGING P-F INDICATOR — rises approximately 120 rows after "
            "vibration_rms begins its exponential climb, as bearing friction "
            "heat conducts into the refrigerant circuit. "
            "Values above 150 °F indicate high-side heat rejection failure "
            "or compressor valve inefficiency. Values above 200 °F are "
            "pre-failure territory requiring immediate shutdown."
        ),
    )

    suction_press: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Refrigerant absolute pressure at the compressor suction port (PSI). "
            "Healthy range: 60–68 PSI for R-134a at standard evaporator conditions. "
            "A sustained drop toward 18–25 PSI indicates low refrigerant charge "
            "(leak condition). Must always be meaningfully lower than "
            "discharge_press — suction_press ≥ discharge_press is a physical "
            "impossibility indicating compressor seizure, valve failure, or "
            "swapped sensor wiring (enforced by schema-level validation)."
        ),
    )

    discharge_press: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Refrigerant absolute pressure at the compressor discharge port (PSI). "
            "Healthy range: 165–180 PSI for R-134a condensing at ~100 °F. "
            "Rises with ambient temperature and condenser fouling. "
            "Pressure ratio (discharge_press / suction_press) is a key "
            "compressor efficiency indicator: healthy ratio is 2.0–3.5. "
            "A ratio above 4.0 indicates severe condenser degradation. "
            "A ratio below 1.5 (or inverted) indicates compressor failure."
        ),
    )

    power_draw: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Compressor active power consumption (kW). "
            "Healthy baseline: ~320 kW for a 200-ton chiller at full load. "
            "LAGGING P-F INDICATOR — rises in tandem with discharge_temp as "
            "bearing mechanical drag increases the work the compressor must "
            "perform to maintain refrigerant flow against system pressure. "
            "A sudden spike without a corresponding rise in vibration_rms "
            "may indicate compressor valve wear (reduced volumetric efficiency "
            "causing the motor to work harder for the same refrigerant flow)."
        ),
    )

    oil_pressure: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Compressor lube oil circuit pressure (PSI). "
            "Healthy range: 55–65 PSI. "
            "LATE-STAGE P-F INDICATOR — gradual pressure drop (toward 40 PSI) "
            "in the final phase of bearing degradation as micro-fractures in "
            "the bearing surface allow oil to bypass the bearing clearances, "
            "reducing circuit pressure. "
            "Most chillers have a low-oil-pressure safety cutout at ~35 PSI — "
            "a drop to this level would trigger an automatic shutdown before "
            "catastrophic failure if the vibration alert is not acted upon."
        ),
    )

    ambient_temp: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Outdoor ambient dry-bulb temperature at the chiller installation "
            "site (°F). "
            "Included as a contextual feature for the ML model because ambient "
            "temperature is a primary driver of chiller load and condenser "
            "heat rejection capacity. A high failure_risk_score on a 118 °F "
            "day may indicate heat rejection capacity limitation rather than "
            "mechanical bearing failure — the model uses ambient_temp to "
            "distinguish between these two failure modes."
        ),
    )

    runtime_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc=(
            "Cumulative compressor operating hours since last major service. "
            "Stored as Integer to match the SensorPayload schema type exactly. "
            "SCADA systems reporting in fractional hour increments (e.g., 0.1 h) "
            "should round to the nearest integer before submitting to this API. "
            "Used by the ML model as a time-based degradation proxy: bearing "
            "wear rate is non-linear with runtime, accelerating significantly "
            "after ~8,000 hours (approximately 1 year of continuous operation). "
            "This feature allows the model to weight the same vibration_rms "
            "reading differently depending on the machine's service age."
        ),
    )

    # ── ML Inference Results ──────────────────────────────────────────────────
    #
    #  These columns store the Random Forest model's output at the moment the
    #  sensor reading was processed. Storing inference results alongside raw
    #  readings enables historical alert review, model performance auditing,
    #  and retraining dataset export without requiring the ML model to be
    #  re-run against historical data.

    failure_risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "Random Forest predicted probability of imminent failure, "
            "normalised to [0.0, 1.0]. "
            "Stored at 6 decimal place precision as emitted by the "
            "`normalise_risk_score_precision` field validator in schemas.py. "
            "Time-series analysis of this column (rolling mean, standard "
            "deviation of score changes) is the primary signal for detecting "
            "model drift — a gradual upward creep in the baseline score "
            "distribution without a corresponding increase in confirmed faults "
            "indicates the model is becoming over-sensitive and requires "
            "retraining."
        ),
    )

    is_anomalous: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc=(
            "True if failure_risk_score exceeded the operational decision "
            "threshold (typically 0.70) at the time of inference. "
            "Stored as a materialised boolean rather than derived at query time "
            "to avoid threshold recalculation inconsistencies if the threshold "
            "is adjusted after data is written: historical rows preserve the "
            "alert state as it was seen by the operator at the time, which is "
            "the legally and operationally correct record for maintenance audits."
        ),
    )

    actionable_alert: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc=(
            "Human-readable maintenance instruction generated by the prediction "
            "endpoint at inference time. "
            "Stored verbatim to provide a complete, self-contained audit record: "
            "the historical log shows exactly what instruction the system issued "
            "to the operator, enabling post-incident review of whether the alert "
            "was specific enough to drive the correct maintenance action. "
            "Also used as the source string for the dashboard's alert history "
            "panel, eliminating the need to regenerate alert text from stored "
            "scores during read queries."
        ),
    )

    def __repr__(self) -> str:
        """
        Unambiguous developer representation for logging and debugging.

        Includes the four fields most useful for quick triage in log output:
        the row ID (for database lookup), the timestamp (for temporal context),
        the primary P-F indicator (vibration_rms), and the model's verdict
        (is_anomalous). Full sensor values are accessible via the ORM instance
        attributes when deeper inspection is needed.
        """
        return (
            f"<SensorTelemetryLog("
            f"id={self.id}, "
            f"timestamp={self.timestamp!r}, "
            f"vibration_rms={self.vibration_rms:.4f} mm/s, "
            f"is_anomalous={self.is_anomalous}"
            f")>"
        )

    def to_dict(self) -> dict:
        """
        Serialise the ORM instance to a plain Python dictionary.

        Used by API response serialisation paths that need a dict
        representation without triggering an additional Pydantic model
        instantiation cycle. Also used in the test suite for direct
        assertion against expected field values without relying on
        SQLAlchemy's ORM attribute access patterns.

        Returns
        -------
        dict
            All column values keyed by their column names, in schema
            declaration order. Numeric values are returned as native
            Python float/int — not numpy scalars — ensuring safe
            downstream JSON serialisation without a custom encoder.
        """
        return {
            "id":                 self.id,
            "timestamp":          self.timestamp,
            "vibration_rms":      self.vibration_rms,
            "suction_temp":       self.suction_temp,
            "discharge_temp":     self.discharge_temp,
            "suction_press":      self.suction_press,
            "discharge_press":    self.discharge_press,
            "power_draw":         self.power_draw,
            "oil_pressure":       self.oil_pressure,
            "ambient_temp":       self.ambient_temp,
            "runtime_hours":      self.runtime_hours,
            "failure_risk_score": self.failure_risk_score,
            "is_anomalous":       self.is_anomalous,
            "actionable_alert":   self.actionable_alert,
        }