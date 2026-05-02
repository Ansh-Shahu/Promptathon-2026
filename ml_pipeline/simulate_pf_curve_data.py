"""
simulate_pf_curve_data.py
Generates synthetic commercial HVAC chiller data.
Models the P-F (Potential-to-Failure) curve where vibration acts as a 
leading indicator weeks before actual temperature/pressure failure thresholds.
"""

import pandas as pd
import numpy as np
import logging
import sys
from pathlib import Path

# ==========================================
# 1. ROBUST LOGGING CONFIGURATION
# ==========================================
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ==========================================
# 2. CORE DATA GENERATION FUNCTION
# ==========================================
def generate_chiller_sensor_data(num_samples: int = 1000) -> pd.DataFrame:
    """
    Generates synthetic chiller sensor data simulating a P-F curve.
    Includes built-in validation to guarantee data integrity before returning.
    """
    if not isinstance(num_samples, int) or num_samples <= 0:
        raise ValueError("num_samples must be a positive integer.")

    try:
        np.random.seed(42)
        
        num_normal = int(num_samples * 0.8)
        num_risk = num_samples - num_normal
        
        # --- NORMAL DATA (Class 0: Healthy Chiller) ---
        normal_data = {
            'temperature_f': np.random.normal(loc=45.0, scale=1.5, size=num_normal),
            'vibration_mms': np.random.normal(loc=0.5, scale=0.1, size=num_normal),
            'pressure_psi': np.random.normal(loc=70.0, scale=2.0, size=num_normal),
            'failure_risk': np.zeros(num_normal, dtype=int)
        }
        
        # --- AT-RISK DATA (Class 1: Early P-F Curve Phase) ---
        risk_data = {
            'temperature_f': np.random.normal(loc=48.0, scale=3.0, size=num_risk),
            'vibration_mms': np.random.normal(loc=3.5, scale=0.8, size=num_risk),
            'pressure_psi': np.random.normal(loc=75.0, scale=5.0, size=num_risk),
            'failure_risk': np.ones(num_risk, dtype=int)
        }
        
        df_normal = pd.DataFrame(normal_data)
        df_risk = pd.DataFrame(risk_data)
        
        df_final = pd.concat([df_normal, df_risk], ignore_index=True)
        df_final = df_final.sample(frac=1).reset_index(drop=True)
        
        df_final['temperature_f'] = df_final['temperature_f'].round(2)
        df_final['vibration_mms'] = df_final['vibration_mms'].round(3)
        df_final['pressure_psi'] = df_final['pressure_psi'].round(1)
        
        # --- DATA INTEGRITY VALIDATION ---
        # Fail loud and early if the data shape is wrong or contains nulls
        if df_final.isnull().values.any():
            raise ValueError("Generated dataset contains NaN values.")
        if len(df_final) != num_samples:
            raise ValueError(f"Expected {num_samples} rows, but generated {len(df_final)}.")
            
        logging.info(f"Successfully generated and validated {len(df_final)} rows of synthetic chiller data.")
        return df_final

    except Exception as e:
        logging.error(f"Failed during data generation matrix operations: {e}")
        raise

# ==========================================
# 3. FAIL-SAFE EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
    
    # 1. Generate the data
    try:
        chiller_df = generate_chiller_sensor_data(1000)
    except ValueError as ve:
        logging.critical(f"Data Validation Error: {ve}")
        sys.exit(1) # Exit with error code
    except Exception as e:
        logging.critical(f"Unexpected error during generation: {e}")
        sys.exit(1)
    
    # 2. Resilient Pathing and Directory Management
    current_script_dir = Path(__file__).parent.resolve()
    output_filepath = current_script_dir / "chiller_training_data.csv"
    
    # Force create the directory if a teammate accidentally deleted it
    try:
        current_script_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logging.critical(f"Permission denied: Cannot create directory at {current_script_dir}")
        sys.exit(1)
    
    # 3. Safe File Writing
    try:
        chiller_df.to_csv(output_filepath, index=False)
        logging.info(f"Data saved to strictly routed path: {output_filepath}")
        
        print("\n--- Sample Data Overview (First 5 Rows) ---")
        print(chiller_df.head())
        sys.exit(0) # Successful execution
        
    except PermissionError:
        # Most common error: Someone has the CSV open in Excel while the script is running
        logging.critical(f"Permission denied: Close '{output_filepath.name}' if it is open in another program.")
        sys.exit(1)
    except OSError as e:
        logging.critical(f"OS level error occurred while writing to {output_filepath}: {e}")
        sys.exit(1)