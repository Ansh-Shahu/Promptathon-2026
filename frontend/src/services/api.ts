// ──────────────────────────────────────────────────────────
//  API Service Layer — connects frontend to FastAPI backend
// ──────────────────────────────────────────────────────────

const API_BASE_URL = 'http://localhost:8000'

// ── Types matching backend response schemas ──────────────

export interface HealthResponse {
  status: string
  engine: string
  version: string
  timestamp: string
  uptime_seconds: number
  ml_model_loaded: boolean
}

export interface PredictionHistoryEntry {
  id: number
  timestamp: string
  vibration_rms: number
  suction_temp: number
  discharge_temp: number
  suction_press: number
  discharge_press: number
  power_draw: number
  oil_pressure: number
  ambient_temp: number
  runtime_hours: number
  failure_risk_score: number
  is_anomalous: boolean
  actionable_alert: string
}

export interface DashboardStats {
  total_readings: number
  total_anomalies: number
  anomaly_rate_percentage: number
  max_risk_score: number
  avg_risk_score: number
  latest_reading_timestamp: string
}

export interface PredictionRequest {
  timestamp: string
  suction_temp: number
  discharge_temp: number
  suction_press: number
  discharge_press: number
  vibration_rms: number
  power_draw: number
  oil_pressure: number
  runtime_hours: number
  ambient_temp: number
}

export interface PredictionResponse {
  timestamp: string
  failure_risk_score: number
  is_anomalous: boolean
  actionable_alert: string
}

// ── API Client Functions ─────────────────────────────────

/**
 * Check API server health and model load status.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}

/**
 * Fetch paginated prediction history from the backend.
 * Results are ordered newest-first.
 */
export async function fetchHistory(
  skip = 0,
  limit = 100,
): Promise<PredictionHistoryEntry[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/history?skip=${skip}&limit=${limit}`,
  )
  if (!res.ok) throw new Error(`History fetch failed: ${res.status}`)
  return res.json()
}

/**
 * Fetch aggregate dashboard KPI statistics.
 */
export async function fetchStats(): Promise<DashboardStats> {
  const res = await fetch(`${API_BASE_URL}/api/v1/stats`)
  if (!res.ok) throw new Error(`Stats fetch failed: ${res.status}`)
  return res.json()
}

/**
 * Submit a sensor payload to the prediction endpoint.
 * Used by the Digital Twin simulator.
 */
export async function submitPrediction(
  payload: PredictionRequest,
): Promise<PredictionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`Prediction failed: ${res.status} — ${detail}`)
  }
  return res.json()
}
