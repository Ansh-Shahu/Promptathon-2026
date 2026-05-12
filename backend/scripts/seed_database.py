"""
seed_database.py
─────────────────────────────────────────────────────────────────────────────
Seeds the HVAC telemetry database by sending every row of the synthetic CSV
dataset through the /api/v1/predict endpoint.

This creates a realistic historical dataset in the database that the frontend
can fetch from /api/v1/history and /api/v1/stats.

Usage
─────
  1. Start the FastAPI server:  cd backend && py -3 -m uvicorn main:app --reload
  2. Run this script:           py -3 backend/scripts/seed_database.py
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE_URL = "http://localhost:8000"
PREDICT_URL = f"{API_BASE_URL}/api/v1/predict"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATASET_PATH = PROJECT_ROOT / "ml_pipeline" / "hvac_sensor_data.csv"

BATCH_SIZE = 50  # Print progress every N rows


def main():
    print("=== HVAC Database Seeder ===")
    print(f"Dataset : {DATASET_PATH}")
    print(f"API URL : {PREDICT_URL}")

    # Check server health
    try:
        health = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=5)
        health_data = health.json()
        print(f"Server  : {health_data.get('status', 'unknown')}")
        print(f"ML Model: {'Loaded' if health_data.get('ml_model_loaded') else 'Mock Mode'}")
    except requests.ConnectionError:
        print("[ERROR] Cannot connect to the API server. Is it running on port 8000?")
        sys.exit(1)

    # Load dataset
    if not DATASET_PATH.exists():
        print(f"[ERROR] Dataset not found at {DATASET_PATH}")
        sys.exit(1)

    df = pd.read_csv(DATASET_PATH)
    total_rows = len(df)
    print(f"Rows    : {total_rows}")
    print("-" * 40)

    success_count = 0
    error_count = 0
    start_time = time.time()

    for idx, row in df.iterrows():
        payload = {
            "timestamp": row["timestamp"],
            "suction_temp": float(row["suction_temp"]),
            "discharge_temp": float(row["discharge_temp"]),
            "suction_press": float(row["suction_press"]),
            "discharge_press": float(row["discharge_press"]),
            "vibration_rms": float(row["vibration_rms"]),
            "power_draw": float(row["power_draw"]),
            "oil_pressure": float(row["oil_pressure"]),
            "runtime_hours": int(row["runtime_hours"]),
            "ambient_temp": float(row["ambient_temp"]),
        }

        try:
            resp = requests.post(PREDICT_URL, json=payload, timeout=10)
            if resp.status_code == 200:
                success_count += 1
            else:
                error_count += 1
                if error_count <= 3:
                    print(f"  [WARN] Row {idx}: HTTP {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            error_count += 1
            if error_count <= 3:
                print(f"  [ERROR] Row {idx}: {e}")

        if (idx + 1) % BATCH_SIZE == 0:
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed
            print(f"  Progress: {idx + 1}/{total_rows} ({rate:.0f} rows/sec)")

    elapsed = time.time() - start_time
    print("-" * 40)
    print(f"Complete: {success_count} succeeded, {error_count} failed in {elapsed:.1f}s")

    # Verify stats
    try:
        stats = requests.get(f"{API_BASE_URL}/api/v1/stats", timeout=5).json()
        print(f"\nDatabase Stats:")
        print(f"  Total readings : {stats.get('total_readings', 'N/A')}")
        print(f"  Anomalies      : {stats.get('total_anomalies', 'N/A')}")
        print(f"  Anomaly rate   : {stats.get('anomaly_rate_percentage', 'N/A')}%")
        print(f"  Peak risk      : {stats.get('max_risk_score', 'N/A')}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
