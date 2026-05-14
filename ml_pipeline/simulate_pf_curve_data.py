"""
simulate_pf_curve_data.py
─────────────────────────────────────────────────────────────────────────────
Synthetic dataset generator for a Predictive Maintenance platform targeting
Commercial HVAC Chillers.

Statistical Design
──────────────────
Baseline  (rows   1–700): Stationary Gaussian process around realistic
                          chiller operating points. Each signal is modelled
                          as μ + ε, where ε ~ N(0, σ²).

Degradation (rows 701–1000): A normalised degradation index t ∈ [0, 1]
                          drives exponential growth on key indicators,
                          directly simulating the P-F (Potential-to-Failure)
                          curve's "hockey-stick" signature.

  vibration_rms  → baseline + A · (e^(k·t) − 1)          [leading indicator]
  discharge_temp → baseline + B · max(0, e^(k·(t−0.4))−1) [lagging ~row 820]
  power_draw     → baseline + C · max(0, e^(k·(t−0.4))−1) [lagging ~row 820]

failure_imminent flips to 1 at row 851 (two+ indicators have crossed their
degradation thresholds, representing the actionable P-F window).
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# ── Reproducibility ──────────────────────────────────────────────────────────
np.random.seed(42)

# ── Constants ─────────────────────────────────────────────────────────────────
TOTAL_ROWS: int = 1_000
BASELINE_END: int = 700          # Rows 1–700 → normal operation
DEGRADATION_START: int = 701     # Rows 701–1000 → P-F degradation window
FAILURE_LABEL_START: int = 851   # Rows 851–1000 → failure_imminent = 1

START_TIMESTAMP: datetime = datetime(2024, 1, 1, 0, 0, 0)# Updated Output Path Routing

SCRIPT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = SCRIPT_DIR
OUTPUT_FILE: Path = OUTPUT_DIR / "hvac_sensor_data.csv"


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def add_noise(
    signal: float | np.ndarray,
    std: float,
    size: int = 1,
) -> np.ndarray:
    """
    Add zero-mean Gaussian noise to a constant or array signal.

    Parameters
    ----------
    signal : float | np.ndarray
        The clean (noiseless) signal value or array.
    std    : float
        Standard deviation of the Gaussian noise.
    size   : int
        Number of samples to generate (used only when signal is scalar).

    Returns
    -------
    np.ndarray
        Noisy signal of shape (size,) or same shape as `signal`.
    """
    noise: np.ndarray = np.random.normal(loc=0.0, scale=std, size=size)
    return np.asarray(signal) + noise


def exponential_ramp(
    t: np.ndarray,
    amplitude: float,
    growth_rate: float,
    phase_shift: float = 0.0,
) -> np.ndarray:
    """
    Compute a phase-shifted exponential ramp used to model P-F curve growth.

    Formula: amplitude · max(0, e^(growth_rate · (t − phase_shift)) − 1)

    Parameters
    ----------
    t           : np.ndarray
        Normalised time index in [0, 1] across the degradation window.
    amplitude   : float
        Scaling constant (peak contribution at t=1).
    growth_rate : float
        Controls how sharply the curve accelerates (higher → steeper hockey stick).
    phase_shift : float
        Delays onset of growth; signal is zero until t > phase_shift.

    Returns
    -------
    np.ndarray
        Non-negative ramp values of the same shape as t.
    """
    raw: np.ndarray = amplitude * (np.exp(growth_rate * (t - phase_shift)) - 1.0)
    return np.maximum(raw, 0.0)


def build_timestamps(n: int, start: datetime, freq_hours: int = 1) -> pd.DatetimeIndex:
    """
    Generate ISO8601 hourly timestamps starting from `start`.

    Parameters
    ----------
    n           : int
        Total number of timestamps.
    start       : datetime
        Start datetime.
    freq_hours  : int
        Frequency in hours between consecutive readings.

    Returns
    -------
    pd.DatetimeIndex
    """
    return pd.date_range(start=start, periods=n, freq=f"{freq_hours}h")


# ══════════════════════════════════════════════════════════════════════════════
#  BASELINE SIGNAL GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def generate_suction_temp(n: int) -> np.ndarray:
    """Chiller suction temperature — realistic range 38–44 °F."""
    return add_noise(signal=41.0, std=0.8, size=n)


def generate_discharge_temp(n: int) -> np.ndarray:
    """Chiller discharge temperature — realistic range 95–105 °F."""
    return add_noise(signal=100.0, std=1.5, size=n)


def generate_suction_press(n: int) -> np.ndarray:
    """Suction-side refrigerant pressure — realistic range 60–68 PSI."""
    return add_noise(signal=64.0, std=1.2, size=n)


def generate_discharge_press(n: int) -> np.ndarray:
    """Discharge-side refrigerant pressure — realistic range 165–180 PSI."""
    return add_noise(signal=172.0, std=2.0, size=n)


def generate_vibration_rms(n: int) -> np.ndarray:
    """
    Bearing vibration (RMS) — ISO 10816 healthy threshold < 4.5 mm/s.
    Baseline centred at 2.5 mm/s with tight variance.
    """
    return np.clip(add_noise(signal=2.5, std=0.25, size=n), a_min=0.1, a_max=None)


def generate_power_draw(n: int) -> np.ndarray:
    """Compressor power draw — typical 200-ton chiller ~320 kW at full load."""
    return add_noise(signal=320.0, std=5.0, size=n)


def generate_oil_pressure(n: int) -> np.ndarray:
    """Compressor lube oil pressure — healthy range 55–65 PSI."""
    return add_noise(signal=60.0, std=1.0, size=n)


def generate_ambient_temp(n: int) -> np.ndarray:
    """
    Outdoor ambient temperature — simulates a single operational day cycle
    repeated across the dataset to reflect diurnal variation (65–85 °F).
    """
    hours: np.ndarray = np.arange(n) % 24
    diurnal: np.ndarray = 75.0 + 10.0 * np.sin(2.0 * np.pi * (hours - 6) / 24.0)
    return add_noise(signal=diurnal, std=1.5, size=n)


# ══════════════════════════════════════════════════════════════════════════════
#  CORE DATA GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_dataset() -> pd.DataFrame:
    """
    Orchestrate the full 1,000-row synthetic dataset generation.

    Steps
    -----
    1. Generate full-length baseline signals for all parameters.
    2. Build normalised degradation index t over rows 701–1000.
    3. Overwrite degradation-phase values with P-F curve modelled signals.
    4. Assemble into a typed DataFrame and validate schema.

    Returns
    -------
    pd.DataFrame
        Fully typed DataFrame with 1,000 rows and 11 columns.
    """
    n: int = TOTAL_ROWS
    n_deg: int = n - BASELINE_END  # 300 degradation rows

    # ── Step 1: Full-length baselines ─────────────────────────────────────────
    timestamps: pd.DatetimeIndex = build_timestamps(n, START_TIMESTAMP)
    suction_temp: np.ndarray     = generate_suction_temp(n)
    discharge_temp: np.ndarray   = generate_discharge_temp(n)
    suction_press: np.ndarray    = generate_suction_press(n)
    discharge_press: np.ndarray  = generate_discharge_press(n)
    vibration_rms: np.ndarray    = generate_vibration_rms(n)
    power_draw: np.ndarray       = generate_power_draw(n)
    oil_pressure: np.ndarray     = generate_oil_pressure(n)
    runtime_hours: np.ndarray    = np.arange(1, n + 1, dtype=np.int64)
    ambient_temp: np.ndarray     = generate_ambient_temp(n)
    failure_imminent: np.ndarray = np.zeros(n, dtype=np.int8)

    # ── Step 2: Normalised degradation index t ∈ [0, 1] ──────────────────────
    t: np.ndarray = np.linspace(0.0, 1.0, num=n_deg)

    # ── Step 3a: vibration_rms — primary leading indicator ───────────────────
    # Exponential P-F ramp: climbs from ~2.5 mm/s (healthy) to ~18+ mm/s (fault)
    # amplitude=12, growth_rate=3.5 → at t=1: 12·(e^3.5 − 1) ≈ 389 → capped
    # by realistic noise; at t=0.7: ≈12·(e^2.45−1) ≈ 130 → still bounded well
    vib_ramp: np.ndarray = exponential_ramp(t, amplitude=12.0, growth_rate=3.5)
    vibration_rms[BASELINE_END:] = (
        add_noise(signal=2.5 + vib_ramp, std=0.4, size=n_deg)
    )
    vibration_rms = np.clip(vibration_rms, a_min=0.1, a_max=None)

    # ── Step 3b: discharge_temp — lagging thermal indicator (~row 820) ────────
    # Phase-shifted by 0.4 so onset begins at t=0.4 → row ~820.
    # Models heat buildup from bearing friction after vibration onset.
    dtemp_ramp: np.ndarray = exponential_ramp(
        t, amplitude=18.0, growth_rate=3.8, phase_shift=0.4
    )
    discharge_temp[BASELINE_END:] = (
        add_noise(signal=100.0 + dtemp_ramp, std=1.5, size=n_deg)
    )

    # ── Step 3c: power_draw — lagging electrical indicator (~row 820) ─────────
    # Mechanical bearing drag increases compressor work → higher kW draw.
    # Same phase shift as discharge_temp; correlated degradation.
    pwr_ramp: np.ndarray = exponential_ramp(
        t, amplitude=40.0, growth_rate=3.6, phase_shift=0.4
    )
    power_draw[BASELINE_END:] = (
        add_noise(signal=320.0 + pwr_ramp, std=5.0, size=n_deg)
    )

    # ── Step 3d: oil_pressure — mild symptomatic drop near failure ────────────
    # Bearing wear causes micro-leaks; gradual pressure loss from row 901.
    oil_ramp: np.ndarray = exponential_ramp(
        t, amplitude=-8.0, growth_rate=4.0, phase_shift=0.65
    )
    oil_pressure[BASELINE_END:] = (
        add_noise(signal=60.0 + oil_ramp, std=1.0, size=n_deg)
    )
    oil_pressure = np.clip(oil_pressure, a_min=1.0, a_max=None)

    # ── Step 3e: discharge_press — mild sympathetic rise from thermal load ────
    dpress_ramp: np.ndarray = exponential_ramp(
        t, amplitude=10.0, growth_rate=2.8, phase_shift=0.5
    )
    discharge_press[BASELINE_END:] = (
        add_noise(signal=172.0 + dpress_ramp, std=2.0, size=n_deg)
    )

    # ── Step 4: failure_imminent label ────────────────────────────────────────
    failure_imminent[FAILURE_LABEL_START - 1:] = 1  # Rows 851–1000 (0-indexed: 850–999)

    # ── Step 5: Assemble DataFrame with strict types ──────────────────────────
    df: pd.DataFrame = pd.DataFrame({
        "timestamp":       timestamps.strftime("%Y-%m-%dT%H:%M:%S"),
        "suction_temp":    suction_temp.round(2),
        "discharge_temp":  discharge_temp.round(2),
        "suction_press":   suction_press.round(2),
        "discharge_press": discharge_press.round(2),
        "vibration_rms":   vibration_rms.round(4),
        "power_draw":      power_draw.round(2),
        "oil_pressure":    oil_pressure.round(2),
        "runtime_hours":   runtime_hours.astype(np.int64),
        "ambient_temp":    ambient_temp.round(2),
        "failure_imminent": failure_imminent.astype(np.int8),
    })

    return df


def validate_dataset(df: pd.DataFrame) -> None:
    """
    Run lightweight schema and P-F curve integrity checks.
    Raises AssertionError if any check fails.

    Parameters
    ----------
    df : pd.DataFrame
        The generated dataset to validate.
    """
    # Schema checks
    expected_cols: list[str] = [
        "timestamp", "suction_temp", "discharge_temp", "suction_press",
        "discharge_press", "vibration_rms", "power_draw", "oil_pressure",
        "runtime_hours", "ambient_temp", "failure_imminent",
    ]
    assert list(df.columns) == expected_cols, "Column mismatch."
    assert len(df) == TOTAL_ROWS, f"Expected {TOTAL_ROWS} rows, got {len(df)}."
    assert df["failure_imminent"].sum() == (TOTAL_ROWS - FAILURE_LABEL_START + 1), \
        "Incorrect failure_imminent label count."

    # P-F curve checks
    baseline_vib_mean: float  = df.loc[:BASELINE_END - 1, "vibration_rms"].mean()
    degraded_vib_mean: float  = df.loc[BASELINE_END:, "vibration_rms"].mean()
    assert degraded_vib_mean > baseline_vib_mean * 2.0, \
        "P-F curve check failed: degraded vibration should be >2× baseline mean."

    baseline_dtemp_mean: float = df.loc[:BASELINE_END - 1, "discharge_temp"].mean()
    degraded_dtemp_mean: float = df.loc[BASELINE_END:, "discharge_temp"].mean()
    assert degraded_dtemp_mean > baseline_dtemp_mean, \
        "P-F curve check failed: degraded discharge_temp should exceed baseline."

    print("✅  All schema and P-F curve integrity checks passed.")


def print_summary(df: pd.DataFrame) -> None:
    """Print a concise summary report of the generated dataset."""
    print("\n" + "═" * 60)
    print("  HVAC Chiller Synthetic Dataset — Generation Summary")
    print("═" * 60)
    print(f"  Total rows      : {len(df):,}")
    print(f"  Baseline rows   : {BASELINE_END} (rows 1–{BASELINE_END})")
    print(f"  Degradation rows: {TOTAL_ROWS - BASELINE_END} "
          f"(rows {BASELINE_END + 1}–{TOTAL_ROWS})")
    print(f"  Failure label   : rows {FAILURE_LABEL_START}–{TOTAL_ROWS} "
          f"({TOTAL_ROWS - FAILURE_LABEL_START + 1} rows)")
    print(f"  Date range      : {df['timestamp'].iloc[0]}  →  "
          f"{df['timestamp'].iloc[-1]}")
    print("─" * 60)
    print("  Key P-F Indicator Stats (vibration_rms  mm/s):")
    print(f"    Baseline mean  : "
          f"{df.loc[:BASELINE_END - 1, 'vibration_rms'].mean():.4f} mm/s")
    print(f"    Degraded mean  : "
          f"{df.loc[BASELINE_END:, 'vibration_rms'].mean():.4f} mm/s")
    print(f"    Peak value     : {df['vibration_rms'].max():.4f} mm/s")
    print("─" * 60)
    print("  Key Lagging Indicator Stats (discharge_temp  °F):")
    print(f"    Baseline mean  : "
          f"{df.loc[:BASELINE_END - 1, 'discharge_temp'].mean():.2f} °F")
    print(f"    Degraded mean  : "
          f"{df.loc[BASELINE_END:, 'discharge_temp'].mean():.2f} °F")
    print(f"    Peak value     : {df['discharge_temp'].max():.2f} °F")
    print("═" * 60 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Main pipeline: generate → validate → summarise → export."""
    print("🔧  Generating synthetic HVAC chiller P-F curve dataset...")
    df: pd.DataFrame = generate_dataset()
    validate_dataset(df)
    print_summary(df)
    
    # ── Safe I/O Export ───────────────────────────────────────────────────────
    # Ensure the target directory exists before attempting to write
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"💾  Dataset saved → {OUTPUT_FILE}")
    except PermissionError:
        print(f"❌  CRITICAL ERROR: Permission denied.")
        print(f"    Are you currently viewing {OUTPUT_FILE.name} in Excel?")
        print(f"    Please close the file and re-run the script.")
    except Exception as e:
        print(f"❌  CRITICAL ERROR: Unexpected I/O failure: {e}")

if __name__ == "__main__":
    main()