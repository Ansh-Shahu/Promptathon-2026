from typing import List

from fastapi import FastAPI
from pydantic import BaseModel, conlist

app = FastAPI(
    title="HVAC Failure Prediction API",
    description="Simple FastAPI backend for compressor prediction input/output validation.",
    version="0.1.0",
)


class PredictRequest(BaseModel):
    input: conlist(float, min_items=3, max_items=3)


class PredictResponse(BaseModel):
    prediction: str
    received: List[float]


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    """Predict maintenance status from a 3-value sensor input."""
    temperature, pressure, vibration = payload.input

    # Temporary business logic until ML is integrated.
    if vibration > 0.7 or temperature > 35:
        prediction_result = "Maintenance Required"
    else:
        prediction_result = "Normal"

    return PredictResponse(prediction=prediction_result, received=payload.input)
