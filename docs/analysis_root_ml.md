# HVAC Predictive Maintenance — Deep File & Folder Analysis: Root & ML Pipeline

> **Generated:** 2026-05-26
> **Scope:** Root Directory & `ml_pipeline/`

---

## 1. Root Directory (`/`)

### `requirements.txt` (root)
- **Purpose:** Meta-file that acts as a router for dependency installation.
- **Why it exists:** In a monorepo containing a Python backend, Python ML pipeline, and Node frontend, a single `requirements.txt` at the root is ambiguous. This file directs developers to the specific folders (`backend/` and `ml_pipeline/`).
- **Dependencies Used:** None. Purely instructional comments.
- **Error Resilience:** Prevents silent failures or cross-contamination of environments by explicitly detailing the `cd` commands.
- **Future Scope / Improvements:** Replace with a `Makefile` or task runner (like `Taskfile` or `Justfile`) at the root level to automate setup across all three domains with a single command (e.g., `make install-all`).

---

## 2. Machine Learning Pipeline (`ml_pipeline/`)

This directory isolates the data generation, training, and testing of the Random Forest model from the production API serving it.

### `ml_pipeline/simulate_pf_curve_data.py`
- **Purpose:** Generates a synthetic 1,000-row HVAC sensor dataset modelling the P-F (Potential-to-Failure) degradation curve.
- **Why it exists:** Real-world SCADA telemetry featuring actual machine failure is highly proprietary and rare. To build a predictive model, realistic synthetic data must be generated representing both healthy states and end-of-life degradation.
- **What and why it uses:** Uses `numpy` for Gaussian noise and exponential math, `pandas` for DataFrame construction.
- **Statistical Design:**
  - **Rows 1–700:** Stationary Gaussian baseline around realistic chiller operating points.
  - **Rows 701–1000:** Exponential ramp on key indicators (vibration → leading, discharge temp/power → lagging).
- **Error Resilience:** Hardcoded random seeds (`np.random.seed(42)`) ensure deterministic output, preventing model drift caused simply by regenerating the dataset.
- **Anomaly:** The `OUTPUT_DIR` is hardcoded to an absolute Windows path: `E:\Promptathon-2026\ml_pipeline`. This will fail immediately on macOS/Linux or another developer's Windows machine.
- **Future Scope / Improvements:** 
  - Change output routing to use `Path(__file__).resolve().parent`.
  - Parameterise the degradation slopes so multiple failure modes (e.g., slow bearing wear vs. rapid refrigerant leak) can be generated.

### `ml_pipeline/hvac_sensor_data.csv`
- **Purpose:** The persisted output of the simulation script; acts as the training dataset.
- **Why it exists:** Caching the data allows the training script to run iteratively without regenerating data, ensuring training stability.
- **Structure:** 1,000 rows × 11 columns (9 features + timestamp + `failure_imminent` target).
- **Future Scope / Improvements:** Exclude from version control via `.gitignore` if the dataset grows larger than 10MB. Migrate to Parquet format for faster I/O and strict schema enforcement.

### `ml_pipeline/train_model.py`
- **Purpose:** End-to-end training pipeline: load CSV → split → train → evaluate → export.
- **Why it exists:** The core algorithm generation script. Separating this from the backend ensures the backend remains lightweight and doesn't require heavy training overhead at startup.
- **What and why it uses:** `scikit-learn` for the `RandomForestClassifier` and metrics. Random Forests are chosen because they handle non-linear relationships well and provide feature importance out-of-the-box, which is crucial for predictive maintenance explainability.
- **Error Resilience:** 
  - Validates that all expected feature columns exist in the loaded dataset before proceeding, failing fast with a clear `sys.exit(1)` if mismatched.
  - Uses `class_weight="balanced"` to prevent the model from blindly predicting the majority class (nominal).
- **Future Scope / Improvements:**
  - Add k-fold cross-validation to prove the model's generalisability.
  - Implement Hyperparameter tuning (e.g., Optuna or GridSearchCV) rather than hardcoded constants.
  - Export a metadata JSON alongside `model.pkl` detailing the training accuracy, date, and feature order for the backend to verify before loading.

### `ml_pipeline/inject_fault.py`
- **Purpose:** A demonstration utility that blasts a single, critically out-of-bounds sensor reading to the backend API via HTTP POST.
- **Why it exists:** Waiting for a gradual degradation curve during a hackathon demo is impractical. This forces an immediate anomaly flag on the dashboard.
- **What and why it uses:** `requests` to perform the HTTP POST.
- **Future Scope / Improvements:** Expand into a full `load_test.py` that can stream data at varying rates to test the backend's async write capabilities and the frontend's chart rendering performance under stress.

### `ml_pipeline/requirements.txt`
- **Purpose:** Defines the Python packages needed for data science operations.
- **Why it exists:** Keeps heavy ML training libraries separated from the production backend dependencies (which may not need pandas, for instance).
- **Anomaly:** Specifies `scikit-learn==1.6.1`. However, the `backend/requirements.txt` specifies `scikit-learn==1.8.0`. Serialising a model in one version and deserialising it in another via `joblib` is highly prone to subtle breakage or outright crashes.
- **Future Scope / Improvements:** Create a `shared-requirements.txt` or use a modern package manager like `Poetry` or `uv` with workspace support to ensure the inference and training environments use identical library versions.
