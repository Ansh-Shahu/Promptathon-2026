# backend/main.py
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import joblib

from schemas import SensorPayload, PredictionResponse

# Configure robust terminal logging for easy debugging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Global dictionary to hold the loaded ML model safely in memory
ml_resources = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles API startup and shutdown events safely. 
    Loads the model into memory exactly once on startup to ensure lightning-fast API responses.
    """
    model_path = Path(__file__).parent / "rf_chiller_model.pkl"
    try:
        # Attempt to load Kir's exported Scikit-Learn model
        ml_resources["model"] = joblib.load(model_path)
        logging.info("Success: Random Forest model loaded into memory.")
    except Exception as e:
        # Graceful degradation: We catch the error but don't crash the server.
        # This allows the frontend to still connect and show a clean error state.
        logging.error(f"WARNING: ML model not found at {model_path}. Endpoint will return 503. Error: {e}")
        ml_resources["model"] = None
        
    yield # API is actively running and receiving traffic
    
    # Clean up memory on shutdown
    ml_resources.clear()
    logging.info("ML resources safely cleared.")

# Initialize the FastAPI application
app = FastAPI(
    title="Chiller Predictive Maintenance API", 
    description="Prompathon 2026 - Field Service Use Case",
    lifespan=lifespan
)

# Bullet-proof CORS configuration so Ary and Sudhan's Vanilla JS can connect seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows local file execution during the hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/predict", response_model=PredictionResponse)
async def predict_chiller_status(payload: SensorPayload):
    """
    Ingests live sensor data, queries the ML model, and returns a predictive risk score.
    """
    # Fail-safe check: Did the model actually load on startup?
    if ml_resources.get("model") is None:
        raise HTTPException(
            status_code=503, 
            detail="Machine Learning model is currently unavailable. Waiting for Kir to export the .pkl file."
        )
    
    try:
        # Convert the strictly validated Pydantic payload into a Pandas DataFrame
        input_data = pd.DataFrame([payload.model_dump()])
        
        # Execute ML Predictions
        model = ml_resources["model"]
        risk_class = int(model.predict(input_data)[0])
        risk_prob = float(model.predict_proba(input_data)[0][1])
        
        # Generate the actionable alert based on the P-F curve narrative
        if risk_class == 1:
            action = "CRITICAL RISK: High-frequency vibration detected. Initiate early P-F curve inspection to prevent imminent thermal failure."
        else:
            action = "System operating within optimal parameters."
            
        return PredictionResponse(
            failure_risk=risk_class,
            risk_score=risk_prob,
            alert_message=action
        )
        
    except Exception as e:
        logging.error(f"Prediction logic failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error during ML prediction pipeline."
        )