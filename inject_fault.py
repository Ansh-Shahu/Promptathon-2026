"""
inject_fault.py
─────────────────────────────────────────────────────────────────────────────
Injects a critical fault reading into the HVAC API to simulate a sudden
failure for demo purposes.

Usage
─────
  py -3 inject_fault.py
"""

import json
import time
import requests

url = "http://localhost:8000/api/v1/predict"

# CRITICAL FAULT PAYLOAD
# These extreme values will cause the ML model to predict a high failure risk.
fault_payload = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "suction_temp": 41.5,
    "discharge_temp": 195.0,  # Huge spike (Normal ~100)
    "suction_press": 63.8,
    "discharge_press": 220.0, # High pressure
    "vibration_rms": 25.4,    # Extreme vibration (Normal < 4.5)
    "power_draw": 520.0,      # High power (Normal ~320)
    "oil_pressure": 40.0,      # Dropping oil pressure (Normal ~60)
    "runtime_hours": 1000,
    "ambient_temp": 90.0,
}

def main():
    print("=== HVAC Fault Injector ===")
    print(f"Target URL: {url}")
    print("Sending critical fault payload...")
    print("-" * 40)
    
    try:
        response = requests.post(url, json=fault_payload, timeout=5)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        print("-" * 40)
        print("\n✅ Success! Refresh your dashboard to see the spike.")
        print("Look for the sharp vertical climb in the Sensor Chart!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Is the FastAPI server running on http://localhost:8000?")

if __name__ == "__main__":
    main()
