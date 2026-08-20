# backend/tests/test_physics_engine.py

"""
test_physics_engine.py
─────────────────────────────────────────────────────────────────────────────
Pure function unit tests for the HVAC Digital Twin physics engine.

All tests call physics engine functions directly with scalar inputs.
No HTTP transport, no database, no mocking. Pure math verification.

Coverage: 29 tests across 10 categories.
"""

from __future__ import annotations

import math
import pytest

from physics_engine import (
    # Functions
    compute_ambient_condenser_penalty,
    compute_compression_ratio,
    compute_volumetric_efficiency,
    compute_degradation_factor,
    compute_isentropic_efficiency,
    compute_discharge_temp_physics,
    compute_mass_flow_rate,
    compute_power_draw_physics,
    compute_vibration_rms_physics,
    compute_oil_pressure_physics,
    compute_risk_from_payload,
    _deterministic_flutter,
    _apply_flutter,
    _normalised_deviation,
    _normalised_deviation_inverse,
    _build_dynamic_alert,
    # Constants
    T_AMB_DESIGN,
    K_AMB_CONDENSER_PRESSURE,
    K_AMB_SUCTION_PRESSURE,
    T_AMB_HEALTHY_MAX,
    T_AMB_CRITICAL,
    W_VIBRATION,
    W_TEMPERATURE,
    W_POWER,
    W_OIL,
    W_AMBIENT,
    DEGRADATION_ONSET_HOURS,
    DEGRADATION_MAX_HOURS,
    K_SPECIFIC_HEAT_RATIO,
    ETA_ISENTROPIC_BASELINE,
    ISO_10816_THRESHOLD,
    BASELINE_VIBRATION_RMS,
    BASELINE_POWER_DRAW,
    BASELINE_OIL_PRESSURE,
)


# ══════════════════════════════════════════════════════════════════════════════
#  AMB: Ambient Condenser Penalty Tests (8 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestAmbientCondenserPenalty:
    """Tests for compute_ambient_condenser_penalty()."""

    def test_amb_01_zero_penalty_below_design(self):
        """AMB-01: 40°F ambient → zero penalty."""
        dp_d, dp_s = compute_ambient_condenser_penalty(40.0)
        assert dp_d == 0.0
        assert dp_s == 0.0

    def test_amb_02_zero_penalty_at_design(self):
        """AMB-02: 75°F (exact design point) → zero penalty."""
        dp_d, dp_s = compute_ambient_condenser_penalty(75.0)
        assert dp_d == 0.0
        assert dp_s == 0.0

    def test_amb_03_zero_penalty_extreme_cold(self):
        """AMB-03: -60°F (schema min) → zero penalty."""
        dp_d, dp_s = compute_ambient_condenser_penalty(-60.0)
        assert dp_d == 0.0
        assert dp_s == 0.0

    def test_amb_04_first_micro_penalty(self):
        """AMB-04: 75.1°F → tiny non-zero penalty."""
        dp_d, dp_s = compute_ambient_condenser_penalty(75.1)
        assert dp_d > 0.0
        assert dp_s > 0.0
        assert dp_d == pytest.approx(0.1 * K_AMB_CONDENSER_PRESSURE, abs=0.01)

    def test_amb_05_linear_scaling_100f(self):
        """AMB-05: 100°F → ΔP = K × 25."""
        dp_d, dp_s = compute_ambient_condenser_penalty(100.0)
        assert dp_d == pytest.approx(25.0 * K_AMB_CONDENSER_PRESSURE, abs=0.01)
        assert dp_s == pytest.approx(25.0 * K_AMB_SUCTION_PRESSURE, abs=0.01)

    def test_amb_06_heatwave_120f(self):
        """AMB-06: 120°F → ΔP_d = 1.625 × 45 = 73.125 PSI."""
        dp_d, dp_s = compute_ambient_condenser_penalty(120.0)
        assert dp_d == pytest.approx(73.125, abs=0.001)
        assert dp_s == pytest.approx(6.75, abs=0.001)

    def test_amb_07_extreme_140f(self):
        """AMB-07: 140°F (schema max) → ΔP_d = 1.625 × 65 = 105.625 PSI."""
        dp_d, dp_s = compute_ambient_condenser_penalty(140.0)
        assert dp_d == pytest.approx(105.625, abs=0.001)
        assert dp_s == pytest.approx(9.75, abs=0.001)

    def test_amb_08_returns_tuple_of_floats(self):
        """AMB-08: Return type is a tuple of two floats."""
        result = compute_ambient_condenser_penalty(100.0)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)


# ══════════════════════════════════════════════════════════════════════════════
#  RATIO: Compression Ratio Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestCompressionRatio:
    """Tests for compute_compression_ratio()."""

    def test_ratio_01_normal(self):
        """RATIO-01: Normal operating pressures → ratio ~2.69."""
        ratio = compute_compression_ratio(64.0, 172.0)
        assert ratio == pytest.approx(172.0 / 64.0, abs=0.01)

    def test_ratio_02_zero_suction_floor(self):
        """RATIO-02: Zero suction pressure → floored to 1.0 PSI."""
        ratio = compute_compression_ratio(0.0, 172.0)
        # p_s floored to 1.0, so ratio = 172.0
        assert ratio == pytest.approx(172.0, abs=0.1)

    def test_ratio_03_equal_pressures_clamp(self):
        """RATIO-03: Equal pressures → clamped to ≥1.01."""
        ratio = compute_compression_ratio(100.0, 100.0)
        assert ratio >= 1.01


# ══════════════════════════════════════════════════════════════════════════════
#  ETA: Volumetric Efficiency Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestVolumetricEfficiency:
    """Tests for compute_volumetric_efficiency()."""

    def test_eta_01_normal_ratio(self):
        """ETA-01: Normal ratio ~2.7 → efficiency ~0.90-0.98."""
        eta = compute_volumetric_efficiency(2.7)
        assert 0.85 < eta < 1.0

    def test_eta_02_extreme_ratio_floor(self):
        """ETA-02: Extreme ratio → floored at 0.10."""
        eta = compute_volumetric_efficiency(100.0)
        assert eta == 0.10

    def test_eta_03_ratio_near_unity(self):
        """ETA-03: Ratio near 1.0 → ceiling at 1.0."""
        eta = compute_volumetric_efficiency(1.01)
        assert eta <= 1.0
        assert eta >= 0.99  # Should be very close to 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  DEG: Degradation Factor Tests (4 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestDegradationFactor:
    """Tests for compute_degradation_factor()."""

    def test_deg_01_before_onset(self):
        """DEG-01: runtime < onset → D = 0.0."""
        d = compute_degradation_factor(1000)
        assert d == 0.0

    def test_deg_02_at_onset(self):
        """DEG-02: runtime == onset → D = 0.0."""
        d = compute_degradation_factor(DEGRADATION_ONSET_HOURS)
        assert d == 0.0

    def test_deg_03_mid_range(self):
        """DEG-03: runtime between onset and max → 0 < D < 1."""
        d = compute_degradation_factor(7500)
        assert 0.0 < d < 1.0

    def test_deg_04_at_max(self):
        """DEG-04: runtime == max_hours → D = 1.0."""
        d = compute_degradation_factor(DEGRADATION_MAX_HOURS)
        assert d == pytest.approx(1.0, abs=0.001)


# ══════════════════════════════════════════════════════════════════════════════
#  TEMP: Discharge Temperature Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestDischargeTemp:
    """Tests for compute_discharge_temp_physics()."""

    def test_temp_01_normal(self):
        """TEMP-01: Normal conditions → reasonable discharge temp in [32, 399]."""
        t = compute_discharge_temp_physics(
            41.0, 2.7, K_SPECIFIC_HEAT_RATIO, ETA_ISENTROPIC_BASELINE,
        )
        assert 32.0 <= t <= 399.0

    def test_temp_02_extreme_ratio_clamp_high(self):
        """TEMP-02: Extreme ratio + low efficiency → clamped at 399°F."""
        t = compute_discharge_temp_physics(41.0, 50.0, K_SPECIFIC_HEAT_RATIO, 0.30)
        assert t <= 399.0

    def test_temp_03_low_input_clamp_low(self):
        """TEMP-03: Very low suction temp with minimal ratio → floor at 32°F."""
        t = compute_discharge_temp_physics(-30.0, 1.01, K_SPECIFIC_HEAT_RATIO, 0.85)
        assert t >= 32.0


# ══════════════════════════════════════════════════════════════════════════════
#  PWR: Power Draw Tests (2 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestPowerDraw:
    """Tests for compute_power_draw_physics()."""

    def test_pwr_01_normal(self):
        """PWR-01: Normal conditions → power in [0, 1499] kW."""
        w = compute_power_draw_physics(41.0, 2.7, 0.85, 10.0)
        assert 0.0 <= w <= 1499.0

    def test_pwr_02_extreme_clamp(self):
        """PWR-02: Extreme inputs → clamped at 1499 kW."""
        w = compute_power_draw_physics(150.0, 50.0, 0.30, 50.0)
        assert w <= 1499.0
        assert w >= 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  VIB: Vibration Tests (2 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestVibration:
    """Tests for compute_vibration_rms_physics()."""

    def test_vib_01_normal_no_degradation(self):
        """VIB-01: Normal power, no degradation → low vibration."""
        v = compute_vibration_rms_physics(320.0, 0.0)
        assert 0.1 <= v < ISO_10816_THRESHOLD

    def test_vib_02_extreme_degradation_clamp(self):
        """VIB-02: Full degradation + high power → clamped at 499 mm/s."""
        v = compute_vibration_rms_physics(1499.0, 1.0)
        assert v <= 499.0
        assert v >= 0.1


# ══════════════════════════════════════════════════════════════════════════════
#  FLT: Deterministic Flutter Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestDeterministicFlutter:
    """Tests for _deterministic_flutter()."""

    def test_flt_01_reproducibility(self):
        """FLT-01: Same inputs always produce the same output."""
        f1 = _deterministic_flutter("2024-01-01T00:00:00", 5000, 0)
        f2 = _deterministic_flutter("2024-01-01T00:00:00", 5000, 0)
        assert f1 == f2

    def test_flt_02_different_channels_differ(self):
        """FLT-02: Different channel_id → different flutter value."""
        f0 = _deterministic_flutter("2024-01-01T00:00:00", 5000, 0)
        f1 = _deterministic_flutter("2024-01-01T00:00:00", 5000, 1)
        assert f0 != f1

    def test_flt_03_amplitude_bound(self):
        """FLT-03: Output is within [-amplitude, +amplitude] for many seeds."""
        for ch in range(20):
            f = _deterministic_flutter("2024-06-15T14:00:00", 4320, ch, amplitude=0.01)
            assert -0.01 <= f <= 0.01, (
                f"Flutter for channel {ch} = {f}, outside [-0.01, +0.01]"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  WSUM: Weight Sum Verification (1 test)
# ══════════════════════════════════════════════════════════════════════════════

class TestWeightSum:
    """Tests for weight vector normalisation."""

    def test_wsum_01_weights_sum_to_one(self):
        """WSUM-01: All risk weights must sum to exactly 1.0."""
        total = W_VIBRATION + W_TEMPERATURE + W_POWER + W_OIL + W_AMBIENT
        assert total == pytest.approx(1.0, abs=1e-10)


# ══════════════════════════════════════════════════════════════════════════════
#  ALERT: Direct Alert Generation Tests (5 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertGeneration:
    """Direct unit tests for _build_dynamic_alert() with controlled σ values."""

    def test_alert_nominal(self):
        """ALERT-01: Non-anomalous → NOMINAL alert with ✅."""
        alert = _build_dynamic_alert(
            risk_score=0.15, is_anomalous=False,
            sigma_v=0.0, sigma_t=0.0, sigma_p=0.0, sigma_o=0.0, sigma_amb=0.0,
            vibration_rms=2.5, discharge_temp=100.0,
            power_draw=320.0, oil_pressure=60.0, ambient_temp=75.0,
        )
        assert "NOMINAL" in alert
        assert "✅" in alert
        assert "No action required" in alert

    def test_alert_vibration_dominant(self):
        """ALERT-02: σ_v dominant → 'Bearing Vibration Critical'."""
        alert = _build_dynamic_alert(
            risk_score=0.80, is_anomalous=True,
            sigma_v=1.0, sigma_t=0.1, sigma_p=0.1, sigma_o=0.1, sigma_amb=0.1,
            vibration_rms=20.0, discharge_temp=115.0,
            power_draw=360.0, oil_pressure=50.0, ambient_temp=100.0,
        )
        assert "Bearing Vibration Critical" in alert
        assert "⚠️" in alert

    def test_alert_thermal_dominant(self):
        """ALERT-03: σ_t dominant → 'Thermal Circuit Overload'."""
        alert = _build_dynamic_alert(
            risk_score=0.80, is_anomalous=True,
            sigma_v=0.1, sigma_t=1.0, sigma_p=0.1, sigma_o=0.1, sigma_amb=0.1,
            vibration_rms=5.0, discharge_temp=200.0,
            power_draw=360.0, oil_pressure=50.0, ambient_temp=100.0,
        )
        assert "Thermal Circuit Overload" in alert

    def test_alert_ambient_dominant(self):
        """ALERT-04: σ_amb dominant → 'Environmental Heat Stress'."""
        alert = _build_dynamic_alert(
            risk_score=0.80, is_anomalous=True,
            sigma_v=0.1, sigma_t=0.1, sigma_p=0.1, sigma_o=0.1, sigma_amb=0.9,
            vibration_rms=5.0, discharge_temp=115.0,
            power_draw=360.0, oil_pressure=50.0, ambient_temp=125.0,
        )
        assert "Environmental Heat Stress" in alert
        assert "ambient temperature" in alert

    def test_alert_critical_urgency(self):
        """ALERT-05: risk ≥ 0.90 → 'CRITICAL RISK' and '24 hours'."""
        alert = _build_dynamic_alert(
            risk_score=0.95, is_anomalous=True,
            sigma_v=1.0, sigma_t=1.0, sigma_p=1.0, sigma_o=1.0, sigma_amb=1.0,
            vibration_rms=30.0, discharge_temp=250.0,
            power_draw=600.0, oil_pressure=30.0, ambient_temp=130.0,
        )
        assert "CRITICAL RISK" in alert
        assert "24 hours" in alert


# ══════════════════════════════════════════════════════════════════════════════
#  PAYLOAD: Full compute_risk_from_payload Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeRiskFromPayload:
    """Integration tests for the full compute_risk_from_payload pipeline."""

    @pytest.fixture
    def nominal_payload_dict(self):
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

    def test_payload_nominal_returns_valid_triple(self, nominal_payload_dict):
        """PAYLOAD-01: Nominal payload returns (float, bool, str) triple."""
        risk, is_anom, alert = compute_risk_from_payload(nominal_payload_dict)
        assert isinstance(risk, float)
        assert isinstance(is_anom, bool)
        assert isinstance(alert, str)
        assert 0.0 <= risk <= 1.0
        assert len(alert) >= 1

    def test_payload_ambient_increases_risk(self, nominal_payload_dict):
        """PAYLOAD-02: Higher ambient → higher risk score."""
        nominal_payload_dict["ambient_temp"] = 75.0
        risk_design, _, _ = compute_risk_from_payload(nominal_payload_dict)

        nominal_payload_dict["ambient_temp"] = 120.0
        risk_hot, _, _ = compute_risk_from_payload(nominal_payload_dict)

        assert risk_hot > risk_design

    def test_payload_extreme_inputs_stay_bounded(self, nominal_payload_dict):
        """PAYLOAD-03: Extreme inputs → risk clamped to [0, 1]."""
        nominal_payload_dict["ambient_temp"] = 140.0
        nominal_payload_dict["runtime_hours"] = 1000000
        nominal_payload_dict["vibration_rms"] = 500.0
        nominal_payload_dict["discharge_temp"] = 400.0
        nominal_payload_dict["power_draw"] = 1500.0
        nominal_payload_dict["oil_pressure"] = 0.0

        risk, is_anom, alert = compute_risk_from_payload(nominal_payload_dict)
        assert 0.0 <= risk <= 1.0
        assert isinstance(is_anom, bool)
        assert len(alert) >= 1
