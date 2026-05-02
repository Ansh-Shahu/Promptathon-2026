# backend/schemas.py
from pydantic import BaseModel, Field

class SensorPayload(BaseModel):
    """
    Strict validation for incoming sensor data from the HVAC chillers.
    We use Field constraints to ensure the data falls within realistic physical bounds,
    preventing edge-case crashes during the live demo.
    """
    temperature_f: float = Field(..., description="Chiller temperature in Fahrenheit", ge=-50.0, le=200.0)
    vibration_mms: float = Field(..., description="Vibration in mm/s (Leading indicator)", ge=0.0, le=50.0)
    pressure_psi: float = Field(..., description="Pressure in PSI", ge=0.0, le=500.0)

class PredictionResponse(BaseModel):
    """
    Standardized output payload that the frontend Vanilla JS will consume.
    """
    failure_risk: int = Field(..., description="0 for Normal Operation, 1 for At-Risk")
    risk_score: float = Field(..., description="Probability of failure (0.0 to 1.0)")
    alert_message: str = Field(..., description="Actionable recommendation based on the P-F curve")