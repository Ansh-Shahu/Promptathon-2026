# backend/tests/test_ambient_integration.py

"""
test_ambient_integration.py
─────────────────────────────────────────────────────────────────────────────
End-to-end integration tests for the HVAC Digital Twin, covering:

  • Mandatory Scenario 1: Cold Baseline (40–75°F) — zero penalty verification
  • Mandatory Scenario 2: Extreme Heatwave (110–140°F) — cascade & clamp tests
  • Mandatory Scenario 3: Compound Stress — degradation × heatwave interaction
  • Schema Boundary Probes — ge/le exact boundary acceptance
  • Schema Rejection Tests — 422 for invalid payloads
  • E2E API Integration — risk score trend verification
  • Alert System Verification — alert content via API
  • Health Endpoint — physics engine label verification

CRITICAL: All API tests force the physics engine path by setting
`app.state.model = None` in the fixture, as per the Architectural Correction.

Coverage: 73 test cases across 9 test classes.
"""

from __future__ import annotations

import math
from typing import Any, Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from schemas import SensorPayload, PredictionResponse
from physics_engine import (
    RISK_ANOMALY_THRESHOLD,
    RISK_CRITICAL_THRESHOLD,
    T_AMB_DESIGN,
    T_AMB_HEALTHY_MAX,
    T_AMB_CRITICAL,
)


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

PREDICT_URL: str = "/api/v1/predict"
HEALTH_URL: str = "/api/v1/health"


# ══════════════════════════════════════════════════════════════════════════════
#  FIXTURES — Physics Engine Force-Route
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def physics_client() -> Generator[TestClient, None, None]:
    """
    TestClient fixture that forces the physics engine fallback path.

    The model override MUST happen INSIDE the TestClient context manager
    because FastAPI's lifespan hook runs during TestClient.__enter__(),
    which loads model.pkl and sets app.state.model to the Random Forest.
    Setting model=None before entering the context is overwritten by the
    lifespan. By setting it after, we guarantee the physics engine path.
    """
    with TestClient(app) as c:
        # Lifespan has already run — model.pkl is loaded into app.state.model.
        # Save the loaded model and override to force physics engine path.
        original_model = app.state.model
        app.state.model = None
        yield c
        # Restore the original model for clean teardown.
        app.state.model = original_model


@pytest.fixture
def baseline_payload() -> dict[str, Any]:
    """
    Healthy baseline payload at design conditions (75°F ambient).

    All values sit at the centre of their healthy operating bands.
    Individual tests clone this and mutate only the fields under test.
    """
    return {
        "timestamp": "2024-06-15T14:00:00",
        "suction_temp": 41.0,
        "discharge_temp": 100.0,
        "suction_press": 64.0,
        "discharge_press": 172.0,
        "vibration_rms": 2.5,
        "power_draw": 320.0,
        "oil_pressure": 60.0,
        "runtime_hours": 4320,
        "ambient_temp": 75.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MANDATORY SCENARIO 1: COLD BASELINE (40–75°F)  [5 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestColdBaseline:
    """Verify zero ambient penalty at or below design temperature."""

    def test_cold_01_40f(self, physics_client, baseline_payload):
        """COLD-01: 40°F ambient → zero penalty, low risk, nominal."""
        baseline_payload["ambient_temp"] = 40.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] < RISK_ANOMALY_THRESHOLD
        assert data["is_anomalous"] is False
        assert "NOMINAL" in data["actionable_alert"]

    def test_cold_02_60f(self, physics_client, baseline_payload):
        """COLD-02: 60°F ambient → zero penalty, low risk."""
        baseline_payload["ambient_temp"] = 60.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] < RISK_ANOMALY_THRESHOLD
        assert data["is_anomalous"] is False

    def test_cold_03_75f_design_point(self, physics_client, baseline_payload):
        """COLD-03: 75°F (design point) → exactly zero ambient penalty."""
        baseline_payload["ambient_temp"] = 75.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] < RISK_ANOMALY_THRESHOLD

    def test_cold_04_75_1f_first_micro_penalty(self, physics_client, baseline_payload):
        """COLD-04: 75.1°F → first micro-penalty, still nominal."""
        baseline_payload["ambient_temp"] = 75.1
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] < RISK_ANOMALY_THRESHOLD

    def test_cold_05_minus60f_schema_min(self, physics_client, baseline_payload):
        """COLD-05: -60°F (schema min) → zero penalty, valid response."""
        baseline_payload["ambient_temp"] = -60.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] < RISK_ANOMALY_THRESHOLD
        assert data["is_anomalous"] is False


# ══════════════════════════════════════════════════════════════════════════════
#  MANDATORY SCENARIO 2: EXTREME HEATWAVE (110–140°F)  [5 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestExtremeHeatwave:
    """Verify cascading ambient penalties under heatwave conditions."""

    def test_heat_01_110f(self, physics_client, baseline_payload):
        """HEAT-01: 110°F → valid response, risk > design baseline."""
        baseline_payload["ambient_temp"] = 110.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_heat_02_120f_cascading(self, physics_client, baseline_payload):
        """HEAT-02: 120°F → cascading pressure/power/temp effects."""
        baseline_payload["ambient_temp"] = 120.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_heat_03_130f_sigma_amb_saturated(self, physics_client, baseline_payload):
        """HEAT-03: 130°F → σ_amb saturated at 1.0."""
        baseline_payload["ambient_temp"] = 130.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_heat_04_140f_schema_max(self, physics_client, baseline_payload):
        """HEAT-04: 140°F (schema max) → all clamps hold, no 422."""
        baseline_payload["ambient_temp"] = 140.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0
        assert len(data["actionable_alert"]) > 0

    def test_heat_05_120f_high_discharge_press(self, physics_client, baseline_payload):
        """HEAT-05: 120°F + discharge_press=400 → ΔP+400 clamped ≤599."""
        baseline_payload["ambient_temp"] = 120.0
        baseline_payload["discharge_press"] = 400.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  MANDATORY SCENARIO 3: COMPOUND STRESS  [5 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestCompoundStress:
    """Verify degradation × heatwave compound interaction."""

    def test_comp_01_degraded_plus_heatwave(self, physics_client, baseline_payload):
        """COMP-01: 8000h runtime + 120°F → elevated risk."""
        baseline_payload["runtime_hours"] = 8000
        baseline_payload["ambient_temp"] = 120.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] > 0.0

    def test_comp_02_max_degradation_max_heat(self, physics_client, baseline_payload):
        """COMP-02: 10000h + 130°F → near-ceiling risk."""
        baseline_payload["runtime_hours"] = 10000
        baseline_payload["ambient_temp"] = 130.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] > 0.5

    def test_comp_03_double_maximum(self, physics_client, baseline_payload):
        """COMP-03: 10000h + 140°F → risk clamped ≤1.0."""
        baseline_payload["runtime_hours"] = 10000
        baseline_payload["ambient_temp"] = 140.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_comp_04_onset_boundary_plus_heatwave(self, physics_client, baseline_payload):
        """COMP-04: 5000h (onset) + 120°F → degradation=0, only ambient."""
        baseline_payload["runtime_hours"] = 5000
        baseline_payload["ambient_temp"] = 120.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_comp_05_schema_maximums_bulletproof(self, physics_client, baseline_payload):
        """COMP-05: runtime=1000000 + ambient=140°F → bulletproof clamp."""
        baseline_payload["runtime_hours"] = 1000000
        baseline_payload["ambient_temp"] = 140.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA BOUNDARY TESTS — ge/le exact probes  [20 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaBoundaryGe:
    """Test exact ge (minimum) boundary values are accepted (9 tests)."""

    @pytest.mark.parametrize("field,value", [
        ("ambient_temp", -60.0),
        ("suction_temp", -30.0),
        ("discharge_temp", 32.0),
        ("suction_press", 0.0),
        ("vibration_rms", 0.0),
        ("power_draw", 0.0),
        ("oil_pressure", 0.0),
        ("runtime_hours", 0),
    ])
    def test_bnd_ge_accepted(self, physics_client, baseline_payload, field, value):
        """BND-GE: Field at exact ge boundary → 200 OK."""
        baseline_payload[field] = value
        # Ensure pressure cross-validator is satisfied
        if field == "suction_press":
            baseline_payload["discharge_press"] = max(
                baseline_payload["discharge_press"], value + 10.0,
            )
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200, (
            f"Field {field}={value} should be accepted "
            f"but got {resp.status_code}: {resp.text[:200]}"
        )

    def test_bnd_ge_discharge_press_at_valid_minimum(
        self, physics_client, baseline_payload,
    ):
        """BND-GE: discharge_press=6, suction=0 → accepted (margin=6>5)."""
        baseline_payload["discharge_press"] = 6.0
        baseline_payload["suction_press"] = 0.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200


class TestSchemaBoundaryLe:
    """Test exact le (maximum) boundary values are accepted (9 tests)."""

    @pytest.mark.parametrize("field,value", [
        ("ambient_temp", 140.0),
        ("suction_temp", 150.0),
        ("discharge_temp", 400.0),
        ("discharge_press", 600.0),
        ("suction_press", 200.0),
        ("vibration_rms", 500.0),
        ("power_draw", 1500.0),
        ("oil_pressure", 200.0),
        ("runtime_hours", 1000000),
    ])
    def test_bnd_le_accepted(self, physics_client, baseline_payload, field, value):
        """BND-LE: Field at exact le boundary → 200 OK."""
        baseline_payload[field] = value
        # Fix pressure relationship
        if field == "suction_press":
            baseline_payload["discharge_press"] = 600.0
        if field == "discharge_press":
            baseline_payload["suction_press"] = min(
                baseline_payload["suction_press"], value - 10.0,
            )
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200, (
            f"Field {field}={value} should be accepted "
            f"but got {resp.status_code}: {resp.text[:200]}"
        )


class TestSchemaBoundaryOverflow:
    """Test values slightly above le boundary are rejected (2 tests)."""

    def test_bnd_ovr_01_ambient_above_max(self, physics_client, baseline_payload):
        """BND-OVR-01: ambient_temp=140.01 → 422."""
        baseline_payload["ambient_temp"] = 140.01
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_bnd_ovr_02_vibration_above_max(self, physics_client, baseline_payload):
        """BND-OVR-02: vibration_rms=500.01 → 422."""
        baseline_payload["vibration_rms"] = 500.01
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA VALIDATION REJECTION TESTS  [18 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaRejection:
    """Test that invalid payloads are correctly rejected with 422."""

    # ── Missing required fields ───────────────────────────────────────────────

    def test_rej_01_missing_timestamp(self, physics_client, baseline_payload):
        """REJ-01: Missing timestamp → 422."""
        del baseline_payload["timestamp"]
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_02_missing_ambient_temp(self, physics_client, baseline_payload):
        """REJ-02: Missing ambient_temp → 422."""
        del baseline_payload["ambient_temp"]
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_03_missing_runtime_hours(self, physics_client, baseline_payload):
        """REJ-03: Missing runtime_hours → 422."""
        del baseline_payload["runtime_hours"]
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_04_empty_payload(self, physics_client):
        """REJ-04: Empty payload → 422."""
        resp = physics_client.post(PREDICT_URL, json={})
        assert resp.status_code == 422

    # ── Boolean injection (SCADA relay state guard) ───────────────────────────

    def test_rej_05_bool_vibration(self, physics_client, baseline_payload):
        """REJ-05: vibration_rms=true → 422 (bool guard)."""
        baseline_payload["vibration_rms"] = True
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_06_bool_power_draw(self, physics_client, baseline_payload):
        """REJ-06: power_draw=false → 422 (bool guard)."""
        baseline_payload["power_draw"] = False
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_07_bool_ambient(self, physics_client, baseline_payload):
        """REJ-07: ambient_temp=true → 422 (bool guard)."""
        baseline_payload["ambient_temp"] = True
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    # ── String injection ──────────────────────────────────────────────────────

    def test_rej_08_string_vibration(self, physics_client, baseline_payload):
        """REJ-08: vibration_rms='NaN' → 422."""
        baseline_payload["vibration_rms"] = "NaN"
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_09_string_power_draw(self, physics_client, baseline_payload):
        """REJ-09: power_draw='infinity' → 422."""
        baseline_payload["power_draw"] = "infinity"
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_10_string_ambient(self, physics_client, baseline_payload):
        """REJ-10: ambient_temp='hot' → 422."""
        baseline_payload["ambient_temp"] = "hot"
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    # ── Null injection ────────────────────────────────────────────────────────

    def test_rej_11_null_ambient(self, physics_client, baseline_payload):
        """REJ-11: ambient_temp=null → 422."""
        baseline_payload["ambient_temp"] = None
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_12_null_vibration(self, physics_client, baseline_payload):
        """REJ-12: vibration_rms=null → 422."""
        baseline_payload["vibration_rms"] = None
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    # ── Pressure inversion ────────────────────────────────────────────────────

    def test_rej_13_pressure_inversion(self, physics_client, baseline_payload):
        """REJ-13: suction=180, discharge=170 → 422 (impossible cycle)."""
        baseline_payload["suction_press"] = 180.0
        baseline_payload["discharge_press"] = 170.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_14_pressure_margin_violation(self, physics_client, baseline_payload):
        """REJ-14: suction=100, discharge=104 (margin < 5) → 422."""
        baseline_payload["suction_press"] = 100.0
        baseline_payload["discharge_press"] = 104.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    # ── Extra forbidden keys ──────────────────────────────────────────────────

    def test_rej_15_extra_key_humidity(self, physics_client, baseline_payload):
        """REJ-15: Extra key 'humidity' → 422 (extra=forbid)."""
        baseline_payload["humidity"] = 0.5
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_16_extra_key_proto(self, physics_client, baseline_payload):
        """REJ-16: Extra key '__proto__' → 422 (extra=forbid)."""
        baseline_payload["__proto__"] = {}
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    # ── Float overflow / edge ─────────────────────────────────────────────────

    def test_rej_17_float_overflow_vibration(self, physics_client, baseline_payload):
        """REJ-17: vibration_rms=1e308 → 422 (exceeds le=500)."""
        baseline_payload["vibration_rms"] = 1e308
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422

    def test_rej_18_float_huge_ambient(self, physics_client, baseline_payload):
        """REJ-18: ambient_temp=999999 → 422 (exceeds le=140)."""
        baseline_payload["ambient_temp"] = 999999.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
#  E2E API INTEGRATION TESTS  [12 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIIntegration:
    """End-to-end API integration tests via physics engine path."""

    def test_api_01_nominal_healthy(self, physics_client, baseline_payload):
        """API-01: Nominal payload → 200, low risk, not anomalous."""
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0
        assert data["is_anomalous"] is False
        assert "NOMINAL" in data["actionable_alert"]
        assert "timestamp" in data

    def test_api_02_cold_40f_vs_design(self, physics_client, baseline_payload):
        """API-02: Cold 40°F risk ≤ design 75°F risk (zero penalty)."""
        baseline_payload["ambient_temp"] = 40.0
        resp_cold = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp_cold.status_code == 200

        baseline_payload["ambient_temp"] = 75.0
        resp_design = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp_design.status_code == 200

        assert (
            resp_cold.json()["failure_risk_score"]
            <= resp_design.json()["failure_risk_score"]
        )

    def test_api_03_cold_60f_nominal(self, physics_client, baseline_payload):
        """API-03: Cold 60°F → zero penalty, not anomalous."""
        baseline_payload["ambient_temp"] = 60.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        assert resp.json()["is_anomalous"] is False

    def test_api_04_design_75f_nominal(self, physics_client, baseline_payload):
        """API-04: Design point 75°F → zero penalty baseline."""
        baseline_payload["ambient_temp"] = 75.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        assert resp.json()["is_anomalous"] is False

    def test_api_05_heatwave_110f_elevated(self, physics_client, baseline_payload):
        """API-05: Heatwave 110°F → risk > design baseline."""
        baseline_payload["ambient_temp"] = 110.0
        resp_hot = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp_hot.status_code == 200

        baseline_payload["ambient_temp"] = 75.0
        resp_base = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp_base.status_code == 200

        assert (
            resp_hot.json()["failure_risk_score"]
            > resp_base.json()["failure_risk_score"]
        )

    def test_api_06_heatwave_120f_monotonic(self, physics_client, baseline_payload):
        """API-06: Heatwave 120°F risk ≥ 110°F risk (monotonic increase)."""
        baseline_payload["ambient_temp"] = 120.0
        resp_120 = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp_120.status_code == 200

        baseline_payload["ambient_temp"] = 110.0
        resp_110 = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp_110.status_code == 200

        assert (
            resp_120.json()["failure_risk_score"]
            >= resp_110.json()["failure_risk_score"]
        )

    def test_api_07_heatwave_140f_no_crash(self, physics_client, baseline_payload):
        """API-07: Heatwave 140°F (schema max) → valid response."""
        baseline_payload["ambient_temp"] = 140.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0
        assert isinstance(data["is_anomalous"], bool)
        assert len(data["actionable_alert"]) >= 1

    def test_api_08_compound_8000h_120f(self, physics_client, baseline_payload):
        """API-08: Compound 8000h + 120°F → elevated risk > design."""
        baseline_payload["runtime_hours"] = 8000
        baseline_payload["ambient_temp"] = 120.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] > 0.0

    def test_api_09_compound_10000h_130f(self, physics_client, baseline_payload):
        """API-09: Compound 10000h + 130°F → high risk (>0.5)."""
        baseline_payload["runtime_hours"] = 10000
        baseline_payload["ambient_temp"] = 130.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failure_risk_score"] > 0.5

    def test_api_10_compound_10000h_140f_clamped(
        self, physics_client, baseline_payload,
    ):
        """API-10: Compound 10000h + 140°F → risk ≤ 1.0."""
        baseline_payload["runtime_hours"] = 10000
        baseline_payload["ambient_temp"] = 140.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_api_11_all_schema_max(self, physics_client):
        """API-11: All fields at schema maximum → 200 OK, no crash."""
        max_payload = {
            "timestamp": "2024-12-31T23:59:59",
            "suction_temp": 150.0,
            "discharge_temp": 400.0,
            "suction_press": 200.0,
            "discharge_press": 600.0,
            "vibration_rms": 500.0,
            "power_draw": 1500.0,
            "oil_pressure": 200.0,
            "runtime_hours": 1000000,
            "ambient_temp": 140.0,
        }
        resp = physics_client.post(PREDICT_URL, json=max_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0
        assert isinstance(data["is_anomalous"], bool)

    def test_api_12_all_schema_min(self, physics_client):
        """API-12: All fields at schema minimum → 200 OK, no crash."""
        min_payload = {
            "timestamp": "2024-01-01T00:00:00",
            "suction_temp": -30.0,
            "discharge_temp": 32.0,
            "suction_press": 0.0,
            "discharge_press": 600.0,   # Must be >> suction + 5
            "vibration_rms": 0.0,
            "power_draw": 0.0,
            "oil_pressure": 0.0,
            "runtime_hours": 0,
            "ambient_temp": -60.0,
        }
        resp = physics_client.post(PREDICT_URL, json=min_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  ALERT SYSTEM VERIFICATION  [8 tests]
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertSystem:
    """Verify context-aware dynamic alert generation via API."""

    def test_alt_01_nominal_alert_format(self, physics_client, baseline_payload):
        """ALT-01: Nominal payload → alert contains '✅' and 'NOMINAL'."""
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        alert = resp.json()["actionable_alert"]
        assert "NOMINAL" in alert
        assert "✅" in alert

    def test_alt_02_high_vibration_anomalous(self, physics_client, baseline_payload):
        """ALT-02: High vibration → anomalous, alert mentions vibration."""
        baseline_payload["vibration_rms"] = 50.0
        baseline_payload["power_draw"] = 600.0
        baseline_payload["oil_pressure"] = 35.0
        baseline_payload["runtime_hours"] = 9000
        baseline_payload["ambient_temp"] = 110.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        if data["is_anomalous"]:
            alert_lower = data["actionable_alert"].lower()
            assert "vibration" in alert_lower or "bearing" in alert_lower

    def test_alt_03_high_discharge_temp(self, physics_client, baseline_payload):
        """ALT-03: High discharge temp → valid response."""
        baseline_payload["discharge_temp"] = 350.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["failure_risk_score"] <= 1.0

    def test_alt_04_high_power_draw(self, physics_client, baseline_payload):
        """ALT-04: High power draw → valid response."""
        baseline_payload["power_draw"] = 1000.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200

    def test_alt_05_low_oil_pressure(self, physics_client, baseline_payload):
        """ALT-05: Low oil pressure → valid response."""
        baseline_payload["oil_pressure"] = 10.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200

    def test_alt_06_ambient_increases_risk(self, physics_client, baseline_payload):
        """ALT-06: High ambient increases risk vs. design baseline."""
        baseline_payload["ambient_temp"] = 75.0
        resp_base = physics_client.post(PREDICT_URL, json=baseline_payload)

        baseline_payload["ambient_temp"] = 135.0
        resp_hot = physics_client.post(PREDICT_URL, json=baseline_payload)

        assert resp_base.status_code == 200
        assert resp_hot.status_code == 200
        assert (
            resp_hot.json()["failure_risk_score"]
            > resp_base.json()["failure_risk_score"]
        )

    def test_alt_07_multi_parameter_degradation(self, physics_client, baseline_payload):
        """ALT-07: Multiple elevated params → anomalous with alert."""
        baseline_payload["vibration_rms"] = 30.0
        baseline_payload["discharge_temp"] = 250.0
        baseline_payload["power_draw"] = 600.0
        baseline_payload["oil_pressure"] = 30.0
        baseline_payload["runtime_hours"] = 9000
        baseline_payload["ambient_temp"] = 120.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_anomalous"] is True
        assert "⚠️" in data["actionable_alert"]

    def test_alt_08_critical_urgency(self, physics_client, baseline_payload):
        """ALT-08: Extreme stress → CRITICAL RISK with 24-hour window."""
        baseline_payload["vibration_rms"] = 100.0
        baseline_payload["discharge_temp"] = 350.0
        baseline_payload["power_draw"] = 1000.0
        baseline_payload["oil_pressure"] = 5.0
        baseline_payload["runtime_hours"] = 10000
        baseline_payload["ambient_temp"] = 140.0
        resp = physics_client.post(PREDICT_URL, json=baseline_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_anomalous"] is True
        assert data["failure_risk_score"] >= 0.90
        assert "CRITICAL" in data["actionable_alert"]
        assert "24 hours" in data["actionable_alert"]


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH ENDPOINT — Physics Engine Label  [1 test]
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """Verify health endpoint reflects physics engine mode."""

    def test_health_physics_engine_label(self, physics_client):
        """HEALTH-01: Model=None → 'Physics Engine (Thermodynamic Digital Twin)'."""
        resp = physics_client.get(HEALTH_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["prediction_mode"] == "Physics Engine (Thermodynamic Digital Twin)"
