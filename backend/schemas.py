"""
schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic v2 data contracts for the HVAC Chiller Predictive Maintenance API.

Two models are defined:

  SensorPayload       — Validates and coerces the incoming JSON request body
                        from edge devices / SCADA systems. All physical sensor
                        bounds are intentionally wide to admit P-F curve
                        degradation data for ML evaluation without triggering
                        premature 422 rejections.

  PredictionResponse  — Defines the outgoing prediction envelope returned to
                        the frontend / alerting layer after the Random Forest
                        model scores the payload.

Design Principles
─────────────────
  • Every field carries a `description` that doubles as OpenAPI documentation.
  • Physical bounds use ge/le (not gt/lt) to include the boundary values
    themselves — a vibration reading of exactly 0.0 mm/s is a valid (if
    unusual) reading from a stopped machine.
  • `ConfigDict(json_schema_extra={"example": {...}})` provides a single,
    realistic Swagger example per model so the frontend team can call the API
    without reading the source code.
  • Floating-point precision in `failure_risk_score` is normalised at
    assignment time to avoid cumulative representation errors (e.g.,
    0.700000000000001) polluting client-side threshold comparisons.
  • A cross-field `model_validator` enforces that `actionable_alert` is never
    silently empty when `is_anomalous` is True — a common runtime oversight
    that would silently break the alerting layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Re-usable annotated float types (DRY) ─────────────────────────────────────

# Temperature in °F — used for multiple sensor channels
TempF = Annotated[float, Field(ge=-60.0, le=400.0)]

# Pressure in PSI — used for multiple sensor channels
PressurePSI = Annotated[float, Field(ge=0.0, le=600.0)]


# ══════════════════════════════════════════════════════════════════════════════
#  REQUEST SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class SensorPayload(BaseModel):
    """
    Incoming sensor reading from a Commercial HVAC Chiller edge device.

    Bounds are set wide enough to admit P-F curve degradation states
    (e.g., vibration_rms up to 500 mm/s, discharge_temp up to 400 °F)
    so the ML model — not the schema — decides whether a reading is
    anomalous. Only physically impossible values are rejected.
    """

    model_config = ConfigDict(
        # Reject extra keys sent by misconfigured SCADA clients — prevents
        # silent data loss from typo'd field names being swallowed.
        extra="forbid",
        # Coerce compatible input types (e.g., int → float) rather than
        # raising a type error. Matches real-world SCADA JSON variability.
        coerce_numbers_to_str=False,
        # Populate fields by name AND alias for flexible client integration.
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-30T14:00:00",
                "suction_temp": 41.3,
                "discharge_temp": 101.5,
                "suction_press": 63.8,
                "discharge_press": 173.2,
                "vibration_rms": 2.91,
                "power_draw": 318.5,
                "oil_pressure": 59.7,
                "runtime_hours": 4320,
                "ambient_temp": 78.4,
            }
        },
    )

    # ── Temporal ──────────────────────────────────────────────────────────────

    timestamp: datetime = Field(
        ...,
        description=(
            "UTC timestamp of the sensor reading in ISO 8601 format. "
            "Used to synchronise the prediction response with the source event."
        ),
    )

    # ── Temperature sensors (°F) ──────────────────────────────────────────────

    suction_temp: Annotated[float, Field(ge=-30.0, le=150.0)] = Field(
        ...,
        description=(
            "Refrigerant temperature at the compressor suction port (°F). "
            "Healthy range: 38–44 °F. "
            "Lower bound -30 °F guards against frozen/dead sensor noise. "
            "Upper bound 150 °F is the catastrophic refrigerant circuit limit."
        ),
    )

    discharge_temp: Annotated[float, Field(ge=32.0, le=400.0)] = Field(
        ...,
        description=(
            "Refrigerant temperature at the compressor discharge port (°F). "
            "Healthy range: 95–105 °F. "
            "Intentionally wide upper bound (400 °F) to admit P-F curve "
            "degradation spikes (confirmed fault readings exceed 258 °F) "
            "for ML evaluation without triggering a 422 response."
        ),
    )

    ambient_temp: Annotated[float, Field(ge=-60.0, le=140.0)] = Field(
        ...,
        description=(
            "Outdoor ambient dry-bulb temperature at the chiller installation "
            "site (°F). Bounds span the ASHRAE extreme cold limit (-60 °F) "
            "to Death Valley / rooftop radiant heat maximum (140 °F)."
        ),
    )

    # ── Pressure sensors (PSI) ────────────────────────────────────────────────

    suction_press: Annotated[float, Field(ge=0.0, le=200.0)] = Field(
        ...,
        description=(
            "Refrigerant absolute pressure at the compressor suction port (PSI). "
            "Healthy range: 60–68 PSI. "
            "Lower bound 0 PSI is the physical absolute pressure floor. "
            "Upper bound 200 PSI covers severe refrigerant slugging events."
        ),
    )

    discharge_press: Annotated[float, Field(ge=0.0, le=600.0)] = Field(
        ...,
        description=(
            "Refrigerant absolute pressure at the compressor discharge port (PSI). "
            "Healthy range: 165–180 PSI. "
            "Upper bound 600 PSI includes safety headroom above the typical "
            "relief valve setpoint of 450–500 PSI."
        ),
    )

    oil_pressure: Annotated[float, Field(ge=0.0, le=200.0)] = Field(
        ...,
        description=(
            "Compressor lube oil circuit pressure (PSI). "
            "Healthy range: 55–65 PSI. "
            "Gradual pressure drop is a late-stage P-F bearing wear indicator."
        ),
    )

    # ── Vibration (mm/s RMS) — Primary P-F Leading Indicator ─────────────────

    vibration_rms: Annotated[float, Field(ge=0.0, le=500.0)] = Field(
        ...,
        description=(
            "Compressor bearing vibration, root-mean-square velocity (mm/s). "
            "THIS IS THE PRIMARY P-F CURVE LEADING INDICATOR. "
            "ISO 10816 healthy threshold: < 4.5 mm/s. "
            "Lower bound 0.0 — RMS velocity is mathematically non-negative. "
            "Upper bound 500 mm/s — beyond this, physical disintegration has "
            "already occurred; readings imply sensor malfunction. "
            "Wide bound is intentional: terminal fault readings can exceed "
            "380 mm/s and MUST reach the ML model, not be rejected here."
        ),
    )

    # ── Electrical (kW) ───────────────────────────────────────────────────────

    power_draw: Annotated[float, Field(ge=0.0, le=1500.0)] = Field(
        ...,
        description=(
            "Compressor active power consumption (kW). "
            "Healthy baseline: ~320 kW (200-ton chiller at full load). "
            "Rises during bearing degradation as mechanical drag increases "
            "compressor work. Upper bound 1500 kW provides headroom for "
            "fault-state spikes confirmed up to ~630 kW in simulation."
        ),
    )

    # ── Operational counter ───────────────────────────────────────────────────

    runtime_hours: Annotated[int, Field(ge=0, le=1_000_000)] = Field(
        ...,
        description=(
            "Cumulative compressor operating hours since last major service. "
            "Used as a time-based degradation proxy. "
            "Upper bound 1,000,000 h ≈ 114 years of continuous runtime."
        ),
    )

    # ── Cross-field validator ─────────────────────────────────────────────────

    @model_validator(mode="after")
    def suction_must_be_below_discharge_pressure(self) -> "SensorPayload":
        """
        Physical law: discharge pressure must always exceed suction pressure
        in a vapour-compression refrigeration cycle. If suction ≥ discharge,
        the compressor has stalled or the sensors are swapped/faulty.

        Note: A tolerance of 5 PSI is allowed to account for transient startup
        conditions and sensor sampling jitter.
        """
        tolerance: float = 5.0
        if self.suction_press >= (self.discharge_press + tolerance):
            raise ValueError(
                f"Physical constraint violated: suction_press ({self.suction_press} PSI) "
                f"must be less than discharge_press ({self.discharge_press} PSI). "
                "This indicates a stalled compressor or swapped sensor wiring."
            )
        return self


# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class PredictionResponse(BaseModel):
    """
    ML model prediction envelope returned to the frontend / alerting layer.

    Includes the echoed request timestamp for strict event synchronisation,
    the normalised risk score, a boolean anomaly flag, and a human-readable
    actionable alert string for display in operations dashboards.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-30T14:00:00",
                "failure_risk_score": 0.873,
                "is_anomalous": True,
                "actionable_alert": (
                    "⚠️ HIGH RISK: Vibration anomaly detected. "
                    "Schedule bearing inspection within 72 hours."
                ),
            }
        }
    )

    # ── Echoed temporal anchor ────────────────────────────────────────────────

    timestamp: datetime = Field(
        ...,
        description=(
            "Echoed timestamp from the originating SensorPayload. "
            "Allows clients to correlate predictions with source readings "
            "in time-series stores without a separate request ID."
        ),
    )

    # ── Model output ──────────────────────────────────────────────────────────

    failure_risk_score: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        ...,
        description=(
            "Random Forest predicted probability of imminent failure, "
            "normalised to [0.0, 1.0]. "
            "Precision is rounded to 6 decimal places at assignment time "
            "to eliminate floating-point representation artefacts "
            "(e.g., 0.7000000000000001) from downstream threshold comparisons."
        ),
    )

    is_anomalous: bool = Field(
        ...,
        description=(
            "True if failure_risk_score exceeds the operational decision "
            "threshold (typically 0.70). Set by the prediction service layer, "
            "not derived here, to allow threshold tuning without schema changes."
        ),
    )

    actionable_alert: str = Field(
        ...,
        min_length=1,
        description=(
            "Human-readable maintenance instruction for the operations "
            "dashboard. Must be non-empty. When is_anomalous is True, "
            "this field must contain a specific recommended action "
            "(e.g., 'Schedule bearing inspection within 72 hours.'). "
            "When is_anomalous is False, a confirmation message is required "
            "(e.g., 'All parameters nominal. No action required.')."
        ),
    )

    # ── Field-level validator: precision normalisation ────────────────────────

    @field_validator("failure_risk_score", mode="before")
    @classmethod
    def normalise_risk_score_precision(cls, v: float) -> float:
        """
        Round the raw Random Forest predict_proba() output to 6 decimal places
        before Pydantic's ge/le bounds check runs.

        Rationale: sklearn's predict_proba returns raw IEEE 754 double-precision
        floats. Values near boundaries (e.g., 1.0000000000000002 from floating-
        point accumulation) would fail the le=1.0 constraint without this step.
        Rounding to 6 d.p. is sufficient for any practical risk threshold
        comparison while eliminating representation noise.
        """
        try:
            return round(float(v), 6)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"failure_risk_score must be a numeric type; received {type(v).__name__!r}."
            ) from exc

    # ── Cross-field validator: alert content enforcement ─────────────────────

    @model_validator(mode="after")
    def alert_must_be_actionable_when_anomalous(self) -> "PredictionResponse":
        """
        Enforce that `actionable_alert` is not a generic placeholder when
        `is_anomalous` is True. A blank or whitespace-only alert string would
        silently break the frontend alert banner and on-call notification flow.

        The minimum bar is: the string must not be exclusively whitespace.
        Content quality (e.g., including a time-to-action) is the responsibility
        of the prediction service layer, not the schema.
        """
        if self.is_anomalous and not self.actionable_alert.strip():
            raise ValueError(
                "actionable_alert must contain a non-whitespace maintenance "
                "instruction when is_anomalous is True. "
                "Received an empty or whitespace-only string."
            )
        return self


# ══════════════════════════════════════════════════════════════════════════════
#  QUICK SMOKE-TEST  (python schemas.py)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    # ── Test 1: Valid nominal payload ─────────────────────────────────────────
    nominal = SensorPayload(
        timestamp=datetime(2024, 1, 30, 14, 0, 0),
        suction_temp=41.3,
        discharge_temp=101.5,
        suction_press=63.8,
        discharge_press=173.2,
        vibration_rms=2.91,
        power_draw=318.5,
        oil_pressure=59.7,
        runtime_hours=4320,
        ambient_temp=78.4,
    )
    print("✅  Test 1 — Nominal payload accepted:")
    print(f"    {nominal.model_dump_json(indent=2)}\n")

    # ── Test 2: Valid P-F degradation payload (high vibration / temp) ─────────
    degraded = SensorPayload(
        timestamp=datetime(2024, 2, 11, 15, 0, 0),
        suction_temp=41.5,
        discharge_temp=258.5,   # P-F spike — must NOT be rejected
        suction_press=63.8,
        discharge_press=205.9,
        vibration_rms=388.3,    # Terminal fault — must NOT be rejected
        power_draw=629.96,
        oil_pressure=59.5,
        runtime_hours=1000,
        ambient_temp=85.2,
    )
    print("✅  Test 2 — P-F degradation payload accepted (high vibration/temp):")
    print(f"    vibration_rms={degraded.vibration_rms}, "
          f"discharge_temp={degraded.discharge_temp}\n")

    # ── Test 3: Valid anomalous prediction response ────────────────────────────
    response = PredictionResponse(
        timestamp=degraded.timestamp,
        failure_risk_score=0.8730000000000001,  # raw sklearn float with noise
        is_anomalous=True,
        actionable_alert=(
            "⚠️ HIGH RISK: Vibration anomaly detected. "
            "Schedule bearing inspection within 72 hours."
        ),
    )
    print("✅  Test 3 — Anomalous PredictionResponse accepted:")
    print(f"    risk_score (raw)     : 0.8730000000000001")
    print(f"    risk_score (rounded) : {response.failure_risk_score}")
    print(f"    is_anomalous         : {response.is_anomalous}")
    print(f"    actionable_alert     : {response.actionable_alert}\n")

    # ── Test 4: Nominal prediction response ───────────────────────────────────
    nominal_response = PredictionResponse(
        timestamp=nominal.timestamp,
        failure_risk_score=0.12,
        is_anomalous=False,
        actionable_alert="✅ All parameters nominal. No action required.",
    )
    print("✅  Test 4 — Nominal PredictionResponse accepted:")
    print(f"    risk_score={nominal_response.failure_risk_score}, "
          f"is_anomalous={nominal_response.is_anomalous}\n")

    # ── Test 5: Rejection — physically impossible pressure inversion ──────────
    from pydantic import ValidationError
    try:
        SensorPayload(
            timestamp=datetime(2024, 1, 30, 14, 0, 0),
            suction_temp=41.3,
            discharge_temp=101.5,
            suction_press=180.0,    # HIGHER than discharge — impossible
            discharge_press=170.0,
            vibration_rms=2.91,
            power_draw=318.5,
            oil_pressure=59.7,
            runtime_hours=4320,
            ambient_temp=78.4,
        )
    except ValidationError as e:
        print("✅  Test 5 — Pressure inversion correctly rejected:")
        errors = e.errors()
        print(f"    {errors[0]['msg']}\n")

    # ── Test 6: Rejection — anomalous flag with empty alert ───────────────────
    try:
        PredictionResponse(
            timestamp=datetime(2024, 1, 30, 14, 0, 0),
            failure_risk_score=0.95,
            is_anomalous=True,
            actionable_alert="   ",  # whitespace-only — must be rejected
        )
    except ValidationError as e:
        print("✅  Test 6 — Whitespace-only alert correctly rejected:")
        errors = e.errors()
        print(f"    {errors[0]['msg']}\n")

    # ── Print OpenAPI-ready JSON schemas ──────────────────────────────────────
    print("─" * 60)
    print("📄  SensorPayload JSON Schema (excerpt — first 500 chars):")
    schema_str = json.dumps(SensorPayload.model_json_schema(), indent=2)
    print(schema_str[:500] + "...\n")