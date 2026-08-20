# backend/physics_engine.py

"""
physics_engine.py
─────────────────────────────────────────────────────────────────────────────
Deterministic thermodynamic physics engine for the HVAC Chiller Predictive
Maintenance API mock mode.

Replaces random.uniform() with first-principles R-134a vapour-compression
cycle calculations, bearing degradation modelling, and a multi-parameter
weighted risk score.

Architecture
────────────
  All functions are STATELESS and PURE — no global variables, no class
  instances, no memory of previous calls. Each function accepts scalar
  float/int inputs and returns scalar outputs. This matches the request-
  scoped HTTP architecture in main.py and is safe under ASGI concurrency.

Refrigerant
───────────
  R-134a (1,1,1,2-Tetrafluoroethane) — the dominant refrigerant in
  commercial water-cooled centrifugal chillers (200-ton class).

  Key thermodynamic properties used:
    k (specific heat ratio, Cp/Cv) = 1.126
    Molecular weight               = 102.03 g/mol
    Specific gas constant R        = 0.08149 kJ/(kg·K)

Deterministic Flutter
─────────────────────
  Real SCADA sensors exhibit micro-electrical noise (ADC quantisation,
  EMI pickup, grounding loops). To simulate this without RNG, a tiny
  deterministic perturbation (±1%) is derived from a hash of the
  payload's timestamp string and runtime_hours integer. The hash is
  stable and reproducible — the same input always produces the same
  flutter, making the output fully deterministic and debuggable.

Usage
─────
  from physics_engine import compute_risk_from_payload

  risk_score, is_anomalous, alert = compute_risk_from_payload(payload_dict)
"""

from __future__ import annotations

import hashlib
import math
from typing import Tuple


# ══════════════════════════════════════════════════════════════════════════════
#  PHYSICAL CONSTANTS — R-134a Vapour-Compression Cycle
# ══════════════════════════════════════════════════════════════════════════════

# Specific heat ratio (Cp/Cv) for R-134a vapour at typical suction conditions.
# Source: NIST Webbook, R-134a at 40°F saturated vapour.
K_SPECIFIC_HEAT_RATIO: float = 1.126

# Clearance volume ratio for a typical centrifugal compressor.
# Range 0.02–0.06; 0.04 is a standard design-point value.
CLEARANCE_RATIO: float = 0.04

# Baseline isentropic efficiency for a new, well-maintained compressor.
# Degrades with bearing wear via the degradation factor.
ETA_ISENTROPIC_BASELINE: float = 0.85

# Compressor displacement parameters (200-ton chiller at 3600 RPM).
COMPRESSOR_RPM: float = 3600.0
# Displacement volume (m³/rev) — sized for ~320 kW at nominal conditions.
DISPLACEMENT_VOLUME: float = 0.012
# R-134a suction gas density at 40°F / 64 PSI (kg/m³).
SUCTION_GAS_DENSITY: float = 16.5


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTHY BASELINES — Reference operating points
# ══════════════════════════════════════════════════════════════════════════════

BASELINE_VIBRATION_RMS: float = 2.5       # mm/s
BASELINE_OIL_PRESSURE: float = 60.0       # PSI
BASELINE_DISCHARGE_TEMP: float = 100.0    # °F
BASELINE_POWER_DRAW: float = 320.0        # kW
BASELINE_SUCTION_TEMP: float = 41.0       # °F
BASELINE_SUCTION_PRESS: float = 64.0      # PSI
BASELINE_DISCHARGE_PRESS: float = 172.0   # PSI

# ISO 10816-3 vibration threshold for rotating machinery (mm/s RMS).
ISO_10816_THRESHOLD: float = 4.5

# Risk score thresholds — consistent with ML model threshold in main.py.
RISK_ANOMALY_THRESHOLD: float = 0.70
RISK_CRITICAL_THRESHOLD: float = 0.90


# ══════════════════════════════════════════════════════════════════════════════
#  AMBIENT THERMAL PENALTY — Condenser heat rejection model
# ══════════════════════════════════════════════════════════════════════════════

# ARI 550/590 standard rating condition for water-cooled chillers.
T_AMB_DESIGN: float = 75.0  # °F — design-point ambient dry-bulb temperature

# R-134a condenser pressure sensitivity to ambient temperature.
# Derived from saturation curve slope (~2.5 PSI/°F at condenser sat temp)
# multiplied by cooling tower + condenser approach transmission gain (~0.65).
# At 120°F ambient (45°F above design): ΔP = 1.625 × 45 = 73.1 PSI.
K_AMB_CONDENSER_PRESSURE: float = 1.625  # PSI per °F above design

# Evaporator-side suction pressure sensitivity (minor — buffered by building
# thermal mass). Represents increased evaporator load from higher cooling demand.
K_AMB_SUCTION_PRESSURE: float = 0.15  # PSI per °F above design

# Ambient temperature thresholds for risk score normalisation.
T_AMB_HEALTHY_MAX: float = 95.0   # °F — upper bound of comfortable operation
T_AMB_CRITICAL: float = 130.0     # °F — extreme heatwave / rooftop radiant heat


# ══════════════════════════════════════════════════════════════════════════════
#  DEGRADATION MODEL PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════

# Runtime hours at which bearing degradation begins its exponential climb.
DEGRADATION_ONSET_HOURS: int = 5000

# Maximum runtime hours used to normalise the degradation index.
DEGRADATION_MAX_HOURS: int = 10000

# Exponential growth rate — controls how sharply degradation accelerates.
DEGRADATION_GROWTH_RATE: float = 3.0

# Scaling coefficients: how degradation factor D maps to each physical effect.
K_VIBRATION: float = 8.0     # D=1.0 → vibration multiplier of 9× baseline
K_EFFICIENCY: float = 0.25   # D=1.0 → η_is drops to 75% of baseline
K_OIL_PRESSURE: float = 0.35 # D=1.0 → oil pressure drops to 65% of baseline


# ══════════════════════════════════════════════════════════════════════════════
#  RISK SCORE WEIGHTS — Multi-parameter weighted fusion
# ══════════════════════════════════════════════════════════════════════════════

# Vibration-dominant per P-F curve doctrine: it is the earliest detectable
# signal, preceding thermal and electrical symptoms by hours to days.
# Weights re-balanced to include environmental stress factor (σ_amb).
W_VIBRATION: float = 0.35
W_TEMPERATURE: float = 0.22
W_POWER: float = 0.18
W_OIL: float = 0.13
W_AMBIENT: float = 0.12


# ══════════════════════════════════════════════════════════════════════════════
#  DETERMINISTIC FLUTTER — Micro-noise from timestamp hash
# ══════════════════════════════════════════════════════════════════════════════

def _deterministic_flutter(
    timestamp_str: str,
    runtime_hours: int,
    channel_id: int,
    amplitude: float = 0.01,
) -> float:
    """
    Generate a tiny deterministic perturbation factor for a given sensor
    channel, seeded by the reading's timestamp and runtime hours.

    The output is a float in [-amplitude, +amplitude] that simulates
    micro-electrical sensor flutter (ADC noise, EMI pickup) without any
    randomness. The same inputs always produce the same output.

    Parameters
    ----------
    timestamp_str : str
        ISO 8601 timestamp string from the payload.
    runtime_hours : int
        Cumulative runtime hours from the payload.
    channel_id : int
        Integer identifier for the sensor channel (0=vibration, 1=temp,
        2=power, 3=oil, etc.) — ensures different channels get different
        flutter values from the same timestamp.
    amplitude : float
        Maximum absolute perturbation as a fraction (0.01 = ±1%).

    Returns
    -------
    float
        Perturbation factor in [-amplitude, +amplitude].
    """
    # Build a unique seed string for this specific reading + channel.
    seed_str: str = f"{timestamp_str}:{runtime_hours}:{channel_id}"
    # SHA-256 produces a uniform distribution of bits.
    digest: bytes = hashlib.sha256(seed_str.encode("utf-8")).digest()
    # Take the first 4 bytes as an unsigned 32-bit integer.
    hash_int: int = int.from_bytes(digest[:4], byteorder="big", signed=False)
    # Normalise to [0, 1], then shift to [-1, +1], then scale by amplitude.
    normalised: float = hash_int / 0xFFFFFFFF  # [0.0, 1.0]
    return amplitude * (2.0 * normalised - 1.0)  # [-amplitude, +amplitude]


def _apply_flutter(value: float, flutter: float) -> float:
    """Apply a multiplicative flutter perturbation to a sensor value."""
    return value * (1.0 + flutter)


# ══════════════════════════════════════════════════════════════════════════════
#  THERMODYNAMIC CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def compute_compression_ratio(p_suction: float, p_discharge: float) -> float:
    """
    Pressure ratio across the compressor.

    Parameters
    ----------
    p_suction   : float  Suction pressure (PSI). Must be > 0.
    p_discharge : float  Discharge pressure (PSI).

    Returns
    -------
    float
        Compression ratio Pd/Ps. Minimum clamped to 1.01 to prevent
        division-by-zero in downstream log/power calculations.
    """
    # Defensive floor: Pydantic cross-validator guarantees Ps < Pd - 5,
    # but we add a safety floor for robustness.
    p_s: float = max(p_suction, 1.0)
    return max(p_discharge / p_s, 1.01)


def compute_volumetric_efficiency(
    ratio: float,
    clearance: float = CLEARANCE_RATIO,
    k: float = K_SPECIFIC_HEAT_RATIO,
) -> float:
    """
    Volumetric efficiency of the compressor.

    η_v = 1 - c · (r_p^(1/k) - 1)

    Returns
    -------
    float
        Volumetric efficiency in (0, 1]. Clamped to [0.10, 1.0].
    """
    eta_v: float = 1.0 - clearance * (math.pow(ratio, 1.0 / k) - 1.0)
    return max(min(eta_v, 1.0), 0.10)


def compute_degradation_factor(
    runtime_hours: int,
    onset: int = DEGRADATION_ONSET_HOURS,
    max_hours: int = DEGRADATION_MAX_HOURS,
    growth_rate: float = DEGRADATION_GROWTH_RATE,
) -> float:
    """
    Monotonic bearing degradation factor D ∈ [0, 1].

    D = 0 for runtime < onset (healthy bearing).
    D climbs exponentially from onset to max_hours.
    D is clamped to 1.0 at the ceiling.

    Parameters
    ----------
    runtime_hours : int
        Cumulative operating hours since last major service.

    Returns
    -------
    float
        Degradation factor in [0.0, 1.0].
    """
    if runtime_hours <= onset:
        return 0.0

    # Normalised progress through the degradation window [0, 1].
    t: float = min((runtime_hours - onset) / max(max_hours - onset, 1), 1.0)

    # Exponential ramp: e^(λ·t) - 1, normalised by e^λ - 1 so D(t=1) = 1.0.
    numerator: float = math.exp(growth_rate * t) - 1.0
    denominator: float = math.exp(growth_rate) - 1.0
    return min(numerator / denominator, 1.0)


def compute_isentropic_efficiency(
    degradation: float,
    eta_base: float = ETA_ISENTROPIC_BASELINE,
    k_eff: float = K_EFFICIENCY,
) -> float:
    """
    Isentropic efficiency degraded by bearing wear.

    η_is = η_base · (1 - D · k_eff)

    Returns
    -------
    float
        Efficiency in [0.30, η_base]. Floor at 0.30 prevents physically
        impossible negative efficiency or division-by-near-zero downstream.
    """
    eta: float = eta_base * (1.0 - degradation * k_eff)
    return max(eta, 0.30)


def compute_discharge_temp_physics(
    t_suction_f: float,
    ratio: float,
    k: float = K_SPECIFIC_HEAT_RATIO,
    eta_is: float = ETA_ISENTROPIC_BASELINE,
) -> float:
    """
    Isentropic discharge temperature with efficiency correction.

    T_d = T_s · r_p^((k-1)/k) / η_is

    Temperatures are converted to Rankine (°F + 459.67) for the
    calculation, then back to °F.

    Returns
    -------
    float
        Discharge temperature in °F. Clamped to [32, 399] to stay
        within Pydantic schema bounds (ge=32, le=400).
    """
    # Convert suction temp from Fahrenheit to Rankine (absolute scale).
    t_s_rankine: float = t_suction_f + 459.67

    # Isentropic compression with efficiency loss.
    exponent: float = (k - 1.0) / k
    t_d_rankine: float = t_s_rankine * math.pow(ratio, exponent) / eta_is

    # Convert back to Fahrenheit.
    t_d_f: float = t_d_rankine - 459.67

    return max(min(t_d_f, 399.0), 32.0)


def compute_mass_flow_rate(
    eta_v: float,
    rho_s: float = SUCTION_GAS_DENSITY,
    v_d: float = DISPLACEMENT_VOLUME,
    rpm: float = COMPRESSOR_RPM,
) -> float:
    """
    Refrigerant mass flow rate through the compressor.

    ṁ = ρ_s · V_d · (N/60) · η_v

    Returns
    -------
    float
        Mass flow rate in kg/s. Minimum clamped to 0.1 kg/s.
    """
    m_dot: float = rho_s * v_d * (rpm / 60.0) * eta_v
    return max(m_dot, 0.1)


def compute_power_draw_physics(
    t_suction_f: float,
    ratio: float,
    eta_is: float,
    m_dot: float,
    k: float = K_SPECIFIC_HEAT_RATIO,
) -> float:
    """
    Isentropic compression power with real-gas efficiency correction.

    W = ṁ · (k/(k-1)) · R_specific · T_s · (r_p^((k-1)/k) - 1) / η_is

    The specific gas constant R for R-134a is 0.08149 kJ/(kg·K).
    T_s is converted to Kelvin for the calculation.

    Returns
    -------
    float
        Power draw in kW. Clamped to [0, 1499] to stay within schema.
    """
    R_SPECIFIC: float = 0.08149  # kJ/(kg·K) for R-134a

    # Convert suction temp to Kelvin: (°F - 32) × 5/9 + 273.15
    t_s_kelvin: float = (t_suction_f - 32.0) * 5.0 / 9.0 + 273.15

    exponent: float = (k - 1.0) / k
    pressure_work: float = math.pow(ratio, exponent) - 1.0

    w_kw: float = m_dot * (k / (k - 1.0)) * R_SPECIFIC * t_s_kelvin * pressure_work / eta_is

    return max(min(w_kw, 1499.0), 0.0)


def compute_vibration_rms_physics(
    power_kw: float,
    degradation: float,
    base_vibration: float = BASELINE_VIBRATION_RMS,
    base_power: float = BASELINE_POWER_DRAW,
    k_vib: float = K_VIBRATION,
) -> float:
    """
    Bearing vibration correlated to compressor load and degradation.

    v_rms = v_base · load_factor · (1 + D · k_vib)

    The load factor scales vibration proportionally to the power draw
    relative to the baseline (a compressor working harder vibrates more
    even with healthy bearings).

    Returns
    -------
    float
        Vibration RMS in mm/s. Clamped to [0.1, 499] for schema safety.
    """
    # Load factor: how hard the compressor is working relative to baseline.
    load_factor: float = max(power_kw / max(base_power, 1.0), 0.5)

    # Degradation amplification: bearing roughness increases vibration.
    degradation_multiplier: float = 1.0 + degradation * k_vib

    v_rms: float = base_vibration * load_factor * degradation_multiplier

    return max(min(v_rms, 499.0), 0.1)


def compute_oil_pressure_physics(
    degradation: float,
    base_oil: float = BASELINE_OIL_PRESSURE,
    k_oil: float = K_OIL_PRESSURE,
) -> float:
    """
    Lube oil pressure degraded by bearing surface micro-fractures.

    P_oil = P_base · (1 - D · k_oil)

    Returns
    -------
    float
        Oil pressure in PSI. Clamped to [1.0, 199] for schema safety.
    """
    p_oil: float = base_oil * (1.0 - degradation * k_oil)
    return max(min(p_oil, 199.0), 1.0)


def compute_ambient_condenser_penalty(
    ambient_temp_f: float,
    t_design: float = T_AMB_DESIGN,
    k_condenser: float = K_AMB_CONDENSER_PRESSURE,
    k_suction: float = K_AMB_SUCTION_PRESSURE,
) -> tuple[float, float]:
    """
    Compute condenser and suction pressure penalties caused by elevated
    ambient temperature.

    In a water-cooled centrifugal chiller, the condenser rejects heat to a
    cooling tower. As ambient dry-bulb temperature rises, the cooling tower
    return water temperature increases, raising condenser saturation pressure.
    The compressor must work against a higher head, increasing the compression
    ratio and cascading into elevated power draw, discharge temperature, and
    vibration.

    The R-134a saturation curve slope at condenser conditions (~105°F sat
    temp) is approximately 2.5 PSI/°F. With a typical cooling tower approach
    of 7°F and condenser approach of 5°F, the effective ambient-to-condenser
    transmission gain is ~0.65, yielding K_amb = 2.5 × 0.65 = 1.625 PSI/°F.

    Cold-side (below design): the penalty is zero. Cold ambient temperatures
    actually improve condenser performance, but we model this conservatively
    as "no benefit" rather than "negative penalty" to avoid artificially
    deflating risk scores during winter operation.

    Parameters
    ----------
    ambient_temp_f : float
        Outdoor ambient dry-bulb temperature in °F.
    t_design : float
        Design-point ambient temperature (default: 75°F per ARI 550/590).
    k_condenser : float
        Condenser pressure sensitivity (PSI/°F above design).
    k_suction : float
        Suction pressure sensitivity (PSI/°F above design).

    Returns
    -------
    tuple[float, float]
        (delta_p_discharge, delta_p_suction) — additive pressure penalties
        in PSI. Both are ≥ 0.0 (cold ambient produces zero penalty).
    """
    delta_t: float = max(ambient_temp_f - t_design, 0.0)

    delta_p_discharge: float = k_condenser * delta_t
    delta_p_suction: float = k_suction * delta_t

    return delta_p_discharge, delta_p_suction


# ══════════════════════════════════════════════════════════════════════════════
#  RISK SCORE — Deterministic multi-parameter weighted fusion
# ══════════════════════════════════════════════════════════════════════════════

def _normalised_deviation(
    value: float,
    healthy_max: float,
    critical_max: float,
) -> float:
    """
    Normalise a sensor reading to [0, 1] based on how far it has deviated
    from the healthy ceiling toward the critical ceiling.

    Returns 0.0 if value ≤ healthy_max (fully healthy).
    Returns 1.0 if value ≥ critical_max (fully critical).
    Linear interpolation between.
    """
    if value <= healthy_max:
        return 0.0
    if value >= critical_max:
        return 1.0
    return (value - healthy_max) / max(critical_max - healthy_max, 0.001)


def _normalised_deviation_inverse(
    value: float,
    healthy_min: float,
    critical_min: float,
) -> float:
    """
    Normalise a sensor reading to [0, 1] for metrics that DECREASE toward
    failure (e.g., oil pressure drops as bearings degrade).

    Returns 0.0 if value ≥ healthy_min.
    Returns 1.0 if value ≤ critical_min.
    """
    if value >= healthy_min:
        return 0.0
    if value <= critical_min:
        return 1.0
    return (healthy_min - value) / max(healthy_min - critical_min, 0.001)


# ══════════════════════════════════════════════════════════════════════════════
#  CONTEXT-AWARE ALERT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _build_dynamic_alert(
    risk_score: float,
    is_anomalous: bool,
    sigma_v: float,
    sigma_t: float,
    sigma_p: float,
    sigma_o: float,
    sigma_amb: float,
    vibration_rms: float,
    discharge_temp: float,
    power_draw: float,
    oil_pressure: float,
    ambient_temp: float,
) -> str:
    """
    Generate a context-aware actionable alert string that dynamically
    identifies the primary driver of the risk score.

    The alert branches based on which normalised deviation factor is
    dominant, providing specific maintenance instructions rather than
    generic warnings.

    Parameters
    ----------
    sigma_v, sigma_t, sigma_p, sigma_o : float
        Normalised deviation factors for vibration, temperature, power,
        and oil pressure respectively. Range [0, 1].

    Returns
    -------
    str
        Non-empty actionable alert string. Guaranteed len ≥ 1.
    """
    if not is_anomalous:
        return (
            f"✅ NOMINAL ({risk_score:.0%}): Physics engine assessed "
            f"composite failure probability at {risk_score:.4f}. "
            f"Vibration {vibration_rms:.2f} mm/s, discharge {discharge_temp:.1f}°F, "
            f"power {power_draw:.1f} kW, oil {oil_pressure:.1f} PSI, "
            f"ambient {ambient_temp:.1f}°F — "
            "all parameters within operational envelope. No action required."
        )

    # Identify the primary and secondary drivers.
    drivers: list[tuple[float, str, str, str]] = [
        (sigma_v, "Bearing Vibration Critical",
         f"vibration at {vibration_rms:.2f} mm/s (threshold: {ISO_10816_THRESHOLD} mm/s)",
         "immediate bearing inspection and vibration spectral analysis"),
        (sigma_t, "Thermal Circuit Overload",
         f"discharge temperature at {discharge_temp:.1f}°F (healthy: ≤105°F)",
         "condenser fouling inspection and refrigerant charge verification"),
        (sigma_p, "Compressor Overload",
         f"power draw at {power_draw:.1f} kW (baseline: {BASELINE_POWER_DRAW} kW)",
         "motor winding diagnostic and compressor valve inspection"),
        (sigma_o, "Lubrication System Degradation",
         f"oil pressure at {oil_pressure:.1f} PSI (healthy: ≥55 PSI)",
         "oil circuit integrity check and bearing clearance measurement"),
        (sigma_amb, "Environmental Heat Stress",
         f"ambient temperature at {ambient_temp:.1f}°F (design: {T_AMB_DESIGN}°F)",
         "activate auxiliary condenser fan staging and verify cooling tower water flow"),
    ]

    # Sort by severity (highest σ first).
    drivers.sort(key=lambda x: x[0], reverse=True)

    primary = drivers[0]
    urgency: str = "CRITICAL RISK" if risk_score >= RISK_CRITICAL_THRESHOLD else "HIGH RISK"
    window: str = "24 hours" if risk_score >= RISK_CRITICAL_THRESHOLD else "72 hours"

    # Build the alert with primary driver identification.
    alert_parts: list[str] = [
        f"⚠️ {urgency} ({risk_score:.0%}): {primary[1]} — {primary[2]}."
    ]

    # Add secondary contributors if they are also elevated.
    secondary_issues: list[str] = []
    for driver in drivers[1:]:
        if driver[0] > 0.15:  # Only mention if meaningfully elevated.
            secondary_issues.append(driver[2])

    if secondary_issues:
        alert_parts.append(
            f" Contributing factors: {'; '.join(secondary_issues)}."
        )

    alert_parts.append(
        f" Recommended action: {primary[3]}."
        f" Schedule maintenance within {window}."
    )

    return "".join(alert_parts)


# ══════════════════════════════════════════════════════════════════════════════
#  OUTPUT VALIDATION — Schema compliance guard
# ══════════════════════════════════════════════════════════════════════════════

def _validate_outputs(
    risk_score: float,
    is_anomalous: bool,
    actionable_alert: str,
) -> None:
    """
    Assert that all physics engine outputs comply with the downstream
    Pydantic PredictionResponse schema constraints.

    Raises AssertionError with a diagnostic message if any constraint
    is violated — this should never happen in production but serves as
    a defence-in-depth tripwire during development.
    """
    assert 0.0 <= risk_score <= 1.0, (
        f"Physics engine produced risk_score={risk_score} outside [0, 1]."
    )
    assert isinstance(is_anomalous, bool), (
        f"is_anomalous must be bool, got {type(is_anomalous).__name__}."
    )
    assert isinstance(actionable_alert, str) and len(actionable_alert) >= 1, (
        "actionable_alert must be a non-empty string."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC INTERFACE — Single entry point for main.py
# ══════════════════════════════════════════════════════════════════════════════

def compute_risk_from_payload(
    payload_dict: dict,
) -> Tuple[float, bool, str]:
    """
    Compute a deterministic failure risk prediction from a validated
    SensorPayload dictionary using first-principles thermodynamic and
    mechanical calculations.

    This function is the SOLE public interface consumed by main.py's
    mock mode branch. It replaces the previous random.uniform() calls
    with physics-grounded calculations.

    Parameters
    ----------
    payload_dict : dict
        A dictionary matching the SensorPayload field names. Must contain
        all 10 sensor fields. Typically produced by `payload.model_dump()`.

    Returns
    -------
    tuple[float, bool, str]
        (risk_score, is_anomalous, actionable_alert)
        - risk_score: float in [0.0, 1.0], rounded to 6 d.p.
        - is_anomalous: bool, True if risk_score ≥ 0.70
        - actionable_alert: non-empty context-aware maintenance instruction
    """
    # ── Extract sensor values from the payload ────────────────────────────────
    suction_temp: float = float(payload_dict["suction_temp"])
    discharge_temp_raw: float = float(payload_dict["discharge_temp"])
    suction_press: float = float(payload_dict["suction_press"])
    discharge_press: float = float(payload_dict["discharge_press"])
    vibration_rms_raw: float = float(payload_dict["vibration_rms"])
    power_draw_raw: float = float(payload_dict["power_draw"])
    oil_pressure_raw: float = float(payload_dict["oil_pressure"])
    runtime_hours: int = int(payload_dict["runtime_hours"])
    ambient_temp: float = float(payload_dict["ambient_temp"])

    # Extract timestamp for deterministic flutter seeding.
    ts_str: str = str(payload_dict.get("timestamp", ""))

    # ── Step 0: Ambient thermal penalty — condenser pressure elevation ────────
    # Elevated ambient temperature raises condenser saturation pressure via
    # the cooling tower heat rejection chain. This MUST be applied before
    # the compression ratio calculation to cascade through all downstream
    # thermodynamic functions (η_v, T_d, W, v_rms).
    delta_p_discharge, delta_p_suction = compute_ambient_condenser_penalty(
        ambient_temp,
    )
    p_discharge_eff: float = min(discharge_press + delta_p_discharge, 599.0)
    p_suction_eff: float = min(suction_press + delta_p_suction, 199.0)

    # Maintain thermodynamic cycle validity: Ps must remain below Pd.
    # The Pydantic cross-validator guarantees the RAW values satisfy this,
    # but the ambient penalty adds to Pd far more than Ps, so the gap
    # actually widens. This guard is pure defence-in-depth.
    if p_suction_eff >= p_discharge_eff - 5.0:
        p_suction_eff = p_discharge_eff - 6.0

    # ── Step 1: Compression ratio (using ambient-adjusted pressures) ──────────
    ratio: float = compute_compression_ratio(p_suction_eff, p_discharge_eff)

    # ── Step 2: Bearing degradation factor ────────────────────────────────────
    degradation: float = compute_degradation_factor(runtime_hours)

    # ── Step 3: Degraded isentropic efficiency ────────────────────────────────
    eta_is: float = compute_isentropic_efficiency(degradation)

    # ── Step 4: Volumetric efficiency ─────────────────────────────────────────
    eta_v: float = compute_volumetric_efficiency(ratio)

    # ── Step 5: Mass flow rate ────────────────────────────────────────────────
    m_dot: float = compute_mass_flow_rate(eta_v)

    # ── Step 6: Physics-calculated discharge temperature ──────────────────────
    discharge_temp_calc: float = compute_discharge_temp_physics(
        suction_temp, ratio, K_SPECIFIC_HEAT_RATIO, eta_is,
    )
    # Blend: use the MAXIMUM of the physics calculation and the raw input.
    # The raw input may contain real degradation data from the CSV simulation.
    # The physics model provides a floor that reflects thermodynamic reality.
    discharge_temp_eff: float = max(discharge_temp_raw, discharge_temp_calc)

    # ── Step 7: Physics-calculated power draw ─────────────────────────────────
    power_draw_calc: float = compute_power_draw_physics(
        suction_temp, ratio, eta_is, m_dot,
    )
    # Blend: use the maximum of physics and raw input.
    power_draw_eff: float = max(power_draw_raw, power_draw_calc)

    # ── Step 8: Vibration from load and degradation ───────────────────────────
    vibration_calc: float = compute_vibration_rms_physics(
        power_draw_eff, degradation,
    )
    # Use the maximum of calculated and raw input.
    vibration_eff: float = max(vibration_rms_raw, vibration_calc)

    # ── Step 9: Oil pressure from degradation ─────────────────────────────────
    oil_calc: float = compute_oil_pressure_physics(degradation)
    # Use the minimum — oil pressure DROPS during degradation.
    oil_eff: float = min(oil_pressure_raw, oil_calc)

    # ── Step 10: Apply deterministic flutter (±1%) ────────────────────────────
    vibration_eff = _apply_flutter(
        vibration_eff,
        _deterministic_flutter(ts_str, runtime_hours, channel_id=0),
    )
    vibration_eff = max(vibration_eff, 0.1)  # Floor after flutter

    discharge_temp_eff = _apply_flutter(
        discharge_temp_eff,
        _deterministic_flutter(ts_str, runtime_hours, channel_id=1, amplitude=0.005),
    )
    discharge_temp_eff = max(discharge_temp_eff, 32.0)

    power_draw_eff = _apply_flutter(
        power_draw_eff,
        _deterministic_flutter(ts_str, runtime_hours, channel_id=2),
    )
    power_draw_eff = max(power_draw_eff, 0.0)

    oil_eff = _apply_flutter(
        oil_eff,
        _deterministic_flutter(ts_str, runtime_hours, channel_id=3, amplitude=0.005),
    )
    oil_eff = max(oil_eff, 1.0)

    # ── Step 11: Normalised deviations ────────────────────────────────────────
    # Each σ represents how far the parameter has deviated from healthy
    # toward critical, normalised to [0, 1].
    sigma_v: float = _normalised_deviation(
        vibration_eff,
        healthy_max=ISO_10816_THRESHOLD,   # 4.5 mm/s
        critical_max=25.0,                 # Terminal bearing failure
    )
    sigma_t: float = _normalised_deviation(
        discharge_temp_eff,
        healthy_max=110.0,                 # °F — upper healthy bound
        critical_max=200.0,                # °F — pre-failure territory
    )
    sigma_p: float = _normalised_deviation(
        power_draw_eff,
        healthy_max=350.0,                 # kW — upper healthy bound
        critical_max=600.0,                # kW — fault-state territory
    )
    sigma_o: float = _normalised_deviation_inverse(
        oil_eff,
        healthy_min=55.0,                  # PSI — lower healthy bound
        critical_min=35.0,                 # PSI — safety cutout level
    )
    sigma_amb: float = _normalised_deviation(
        ambient_temp,
        healthy_max=T_AMB_HEALTHY_MAX,     # 95°F
        critical_max=T_AMB_CRITICAL,       # 130°F
    )

    # ── Step 12: Weighted risk score ──────────────────────────────────────────
    risk_raw: float = (
        W_VIBRATION * sigma_v
        + W_TEMPERATURE * sigma_t
        + W_POWER * sigma_p
        + W_OIL * sigma_o
        + W_AMBIENT * sigma_amb
    )

    # Clamp to [0, 1] and round to 6 d.p. for PredictionResponse precision.
    risk_score: float = round(max(min(risk_raw, 1.0), 0.0), 6)

    # ── Step 13: Anomaly flag ─────────────────────────────────────────────────
    is_anomalous: bool = risk_score >= RISK_ANOMALY_THRESHOLD

    # ── Step 14: Context-aware alert ──────────────────────────────────────────
    actionable_alert: str = _build_dynamic_alert(
        risk_score=risk_score,
        is_anomalous=is_anomalous,
        sigma_v=sigma_v,
        sigma_t=sigma_t,
        sigma_p=sigma_p,
        sigma_o=sigma_o,
        sigma_amb=sigma_amb,
        vibration_rms=vibration_eff,
        discharge_temp=discharge_temp_eff,
        power_draw=power_draw_eff,
        oil_pressure=oil_eff,
        ambient_temp=ambient_temp,
    )

    # ── Step 15: Validate outputs before returning ────────────────────────────
    _validate_outputs(risk_score, is_anomalous, actionable_alert)

    return risk_score, is_anomalous, actionable_alert
