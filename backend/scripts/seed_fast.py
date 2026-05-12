"""
seed_fast.py
─────────────────────────────────────────────────────────────────────────────
Seeds the HVAC telemetry database FAST by running ML inference locally
and bulk-inserting directly into SQLite — bypasses the HTTP overhead.

Usage
─────
  cd backend && py -3 scripts/seed_fast.py
"""

import os
import sys
from pathlib import Path

# Add backend to path so we can import its modules
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import joblib
import numpy as np
import pandas as pd
from database import Base, SessionLocal, engine
from models import SensorTelemetryLog

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = BACKEND_DIR.parent
DATASET_PATH = PROJECT_ROOT / "ml_pipeline" / "hvac_sensor_data.csv"
MODEL_PATH = BACKEND_DIR / "model.pkl"

FEATURE_COLUMNS = [
    "suction_temp", "discharge_temp", "suction_press", "discharge_press",
    "vibration_rms", "power_draw", "oil_pressure", "runtime_hours", "ambient_temp",
]


def main():
    print("=== HVAC Fast Database Seeder ===")

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Load model
    if not MODEL_PATH.exists():
        print(f"[ERROR] model.pkl not found at {MODEL_PATH}")
        sys.exit(1)
    model = joblib.load(MODEL_PATH)
    print(f"Model loaded: {MODEL_PATH}")

    # Load dataset
    if not DATASET_PATH.exists():
        print(f"[ERROR] Dataset not found at {DATASET_PATH}")
        sys.exit(1)
    df = pd.read_csv(DATASET_PATH)
    print(f"Dataset loaded: {len(df)} rows")

    # Run batch ML inference
    X = df[FEATURE_COLUMNS].values
    probas = model.predict_proba(X)[:, 1]
    print(f"ML inference complete for {len(probas)} samples")
    print(f"  Risk score range: {probas.min():.6f} - {probas.max():.6f}")
    print(f"  Anomalies (>= 0.70): {(probas >= 0.70).sum()}")

    # Clear existing data
    db = SessionLocal()
    try:
        deleted = db.query(SensorTelemetryLog).delete()
        db.commit()
        print(f"Cleared {deleted} existing rows")
    except Exception as e:
        db.rollback()
        print(f"Warning: Could not clear existing data: {e}")

    # Bulk insert
    rows = []
    for idx, row in df.iterrows():
        risk_score = float(probas[idx])
        is_anomalous = risk_score >= 0.70
        vibration = float(row["vibration_rms"])

        if is_anomalous:
            alert = (
                f"HIGH RISK ({risk_score:.0%}): ML model detected failure "
                f"probability of {risk_score:.4f}. Vibration RMS at "
                f"{vibration:.2f} mm/s. "
                "Immediate bearing inspection recommended. "
                "Schedule maintenance within 72 hours to prevent unplanned downtime."
            )
        else:
            alert = (
                f"NOMINAL ({risk_score:.0%}): ML model assessed failure "
                f"probability at {risk_score:.4f}. All sensor parameters within "
                "acceptable operating range. "
                "No maintenance action required. Continue scheduled monitoring."
            )

        log = SensorTelemetryLog(
            timestamp=str(row["timestamp"]),
            suction_temp=float(row["suction_temp"]),
            discharge_temp=float(row["discharge_temp"]),
            suction_press=float(row["suction_press"]),
            discharge_press=float(row["discharge_press"]),
            vibration_rms=vibration,
            power_draw=float(row["power_draw"]),
            oil_pressure=float(row["oil_pressure"]),
            runtime_hours=int(row["runtime_hours"]),
            ambient_temp=float(row["ambient_temp"]),
            failure_risk_score=round(risk_score, 6),
            is_anomalous=is_anomalous,
            actionable_alert=alert,
        )
        rows.append(log)

    try:
        db.add_all(rows)
        db.commit()
        print(f"Inserted {len(rows)} rows successfully!")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Bulk insert failed: {e}")
        sys.exit(1)
    finally:
        db.close()

    # Verify
    db2 = SessionLocal()
    count = db2.query(SensorTelemetryLog).count()
    anomaly_count = db2.query(SensorTelemetryLog).filter(
        SensorTelemetryLog.is_anomalous == True
    ).count()
    db2.close()

    print(f"\nDatabase stats:")
    print(f"  Total readings : {count}")
    print(f"  Anomalies      : {anomaly_count}")
    print(f"  Anomaly rate   : {(anomaly_count/count*100):.1f}%")
    print("\nDone! Restart or refresh the dashboard to see live data.")


if __name__ == "__main__":
    main()
