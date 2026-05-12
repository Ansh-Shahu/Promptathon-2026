import React, { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { AuthProvider } from './context/AuthContext'
import LandingPage from './components/LandingPage'
import LoginPage from './components/LoginPage'
import Sidebar, { type NavPage } from './components/Sidebar'
import TopBar from './components/TopBar'
import FleetStats from './components/FleetStats'
import CompressorTable from './components/CompressorTable'
import SensorCards from './components/SensorCards'
import SensorChart from './components/SensorChart'
import SymptomTimeline from './components/SymptomTimeline'
import AlertFeed from './components/AlertFeed'
import AIDiagnostics from './components/AIDiagnostics'
import DigitalTwin from './components/DigitalTwin'
import MaintenanceScheduler from './components/MaintenanceScheduler'
import ReportsPanel from './components/ReportsPanel'
import {
  compressors as staticCompressors,
  generateSymptoms,
  generateAlerts,
  generateTrendData,
  getFleetStats,
  generateTicketHistory,
  generateMaintenanceSchedule,
  generateWeeklyReports,
  type Compressor,
  type DetectedSymptom,
  type AlertEntry,
  type TrendDataPoint,
  type Ticket,
  type MaintenanceEvent,
  type WeeklyReport,
} from './data/mockData'
import {
  fetchHistory,
  fetchStats,
  type PredictionHistoryEntry,
  type DashboardStats,
} from './services/api'

const REFRESH_INTERVAL = 30 // seconds

// ── Helpers: Map backend data to frontend component structures ───────────────

/**
 * Convert backend history entries to the TrendDataPoint format used by SensorChart.
 * Takes the last N entries and maps timestamp + sensor readings.
 */
function historyToTrendData(history: PredictionHistoryEntry[]): TrendDataPoint[] {
  // History arrives newest-first; reverse for chronological chart order
  const chronological = [...history].reverse()
  return chronological.map(entry => {
    const d = new Date(entry.timestamp)
    return {
      time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      vibration: +entry.vibration_rms.toFixed(2),
      pressure: +entry.discharge_press.toFixed(1),
      temperature: +entry.discharge_temp.toFixed(1),
      power: +entry.power_draw.toFixed(1),
    }
  })
}

/**
 * Convert backend history entries to AlertEntry format.
 * Anomalous readings become alerts; nominal readings are skipped.
 */
function historyToAlerts(history: PredictionHistoryEntry[]): AlertEntry[] {
  return history
    .filter(entry => entry.is_anomalous)
    .slice(0, 10) // Show latest 10 anomaly alerts
    .map((entry, idx) => ({
      id: `API-ALT-${entry.id}`,
      compressorId: 'CMP-003', // Associated with the primary monitored unit
      type: 'predictive' as const,
      message: entry.actionable_alert,
      timestamp: entry.timestamp,
      severity: entry.failure_risk_score >= 0.90 ? 'Critical' as const : 'Warning' as const,
      acknowledged: false,
    }))
}

/**
 * Convert backend history entries to DetectedSymptom format.
 * Derives symptoms from sensor readings that exceed known thresholds.
 */
function historyToSymptoms(history: PredictionHistoryEntry[]): DetectedSymptom[] {
  const symptoms: DetectedSymptom[] = []
  const anomalous = history.filter(e => e.is_anomalous).slice(0, 6)

  anomalous.forEach((entry, idx) => {
    if (entry.vibration_rms > 4.5) {
      symptoms.push({
        id: `API-SYM-V-${entry.id}`,
        compressorId: 'CMP-003',
        symptom: `Abnormal vibration detected: ${entry.vibration_rms.toFixed(2)} mm/s RMS`,
        severity: 'Critical',
        detectedAt: entry.timestamp,
        confidence: Math.min(99, Math.round(entry.failure_risk_score * 100)),
        sensor: 'Accelerometer',
      })
    }
    if (entry.discharge_temp > 120) {
      symptoms.push({
        id: `API-SYM-T-${entry.id}`,
        compressorId: 'CMP-003',
        symptom: `Discharge temperature elevated: ${entry.discharge_temp.toFixed(1)}°F`,
        severity: entry.discharge_temp > 150 ? 'Critical' : 'Warning',
        detectedAt: entry.timestamp,
        confidence: Math.min(95, Math.round(entry.failure_risk_score * 100)),
        sensor: 'RTD Sensor',
      })
    }
    if (entry.power_draw > 360) {
      symptoms.push({
        id: `API-SYM-P-${entry.id}`,
        compressorId: 'CMP-003',
        symptom: `Power draw exceeding baseline: ${entry.power_draw.toFixed(1)} kW`,
        severity: 'Warning',
        detectedAt: entry.timestamp,
        confidence: Math.min(90, Math.round(entry.failure_risk_score * 100)),
        sensor: 'Power Meter',
      })
    }
  })

  return symptoms.slice(0, 6) // Cap at 6 symptoms
}

/**
 * Build dynamic compressor data by overlaying the latest backend readings
 * onto the static fleet definitions.
 */
function buildDynamicCompressors(
  history: PredictionHistoryEntry[],
  stats: DashboardStats | null,
): Compressor[] {
  if (history.length === 0) return staticCompressors

  // Get the latest reading for the primary monitored unit
  const latest = history[0] // newest first

  return staticCompressors.map(c => {
    if (c.id === 'CMP-003') {
      // Map the latest ML-scored reading onto the "critical" unit
      const riskScore = latest.failure_risk_score
      let status: Compressor['status'] = 'Normal'
      if (riskScore >= 0.90) status = 'Critical'
      else if (riskScore >= 0.70) status = 'Warning'
      else if (riskScore >= 0.40) status = 'Damaged'

      return {
        ...c,
        temperature: Math.round(latest.discharge_temp),
        vibration: +latest.vibration_rms.toFixed(1),
        pressure: Math.round(latest.discharge_press),
        powerDraw: +latest.power_draw.toFixed(1),
        runtime: latest.runtime_hours,
        efficiency: riskScore < 0.3 ? 96 : riskScore < 0.7 ? 88 : 78,
        status,
      }
    }
    return c
  })
}


function DashboardContent() {
  const [activePage, setActivePage] = useState<NavPage>('dashboard')
  const [selectedUnit, setSelectedUnit] = useState<string>('CMP-003')
  const [searchQuery, setSearchQuery] = useState('')
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  // Backend connectivity state
  const [backendAvailable, setBackendAvailable] = useState(false)
  const [mlModelLoaded, setMlModelLoaded] = useState(false)
  const [apiHistory, setApiHistory] = useState<PredictionHistoryEntry[]>([])
  const [apiStats, setApiStats] = useState<DashboardStats | null>(null)

  // Live data state — initialized with static mock data, overridden by API
  const [symptoms, setSymptoms] = useState<DetectedSymptom[]>(generateSymptoms)
  const [alerts, setAlerts] = useState<AlertEntry[]>(generateAlerts)
  const [trendData, setTrendData] = useState<TrendDataPoint[]>(() => generateTrendData(24))
  const [ticketHistory, setTicketHistory] = useState<Ticket[]>(generateTicketHistory)
  const [maintenanceEvents] = useState<MaintenanceEvent[]>(generateMaintenanceSchedule)
  const [weeklyReports] = useState<WeeklyReport[]>(generateWeeklyReports)

  // Dynamic compressors — updated from backend when available
  const [compressors, setCompressors] = useState<Compressor[]>(staticCompressors)

  const fleetStats = getFleetStats(compressors)
  const selectedCompressor = compressors.find(c => c.id === selectedUnit) || null

  // ── Fetch live data from backend ──────────────────────────────────────────
  const fetchBackendData = useCallback(async () => {
    try {
      // Fetch history and stats in parallel
      const [historyData, statsData] = await Promise.all([
        fetchHistory(0, 200),
        fetchStats(),
      ])

      setBackendAvailable(true)
      setApiHistory(historyData)
      setApiStats(statsData)

      // Override frontend state with backend-sourced data
      if (historyData.length > 0) {
        setTrendData(historyToTrendData(historyData.slice(0, 48))) // last 48 readings for chart
        setAlerts(historyToAlerts(historyData))
        setSymptoms(historyToSymptoms(historyData))
        setCompressors(buildDynamicCompressors(historyData, statsData))
      }

    } catch (err) {
      // Backend not reachable — stay on static mock data silently
      setBackendAvailable(false)
      console.warn('Backend not available, using static data:', err)
    }
  }, [])

  // Auto-refresh every 30 seconds
  const doRefresh = useCallback(() => {
    fetchBackendData()
    setLastRefresh(new Date())
    setCountdown(REFRESH_INTERVAL)
  }, [fetchBackendData])

  // Initial data load
  useEffect(() => {
    fetchBackendData()
  }, [fetchBackendData])

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          doRefresh()
          return REFRESH_INTERVAL
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [doRefresh])

  const handleAcknowledge = (id: string) => {
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a))
  }

  const handleGenerateTicket = (ticket: Ticket) => {
    setTicketHistory(prev => [ticket, ...prev])
  }

  const unacknowledgedCount = alerts.filter(a => !a.acknowledged).length

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'transparent' }}>
      {/* Sidebar */}
      <Sidebar activePage={activePage} onNavigate={setActivePage} alertCount={unacknowledgedCount} />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <TopBar
          lastRefresh={lastRefresh}
          countdown={countdown}
          onManualRefresh={doRefresh}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          alertCount={unacknowledgedCount}
        />

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6" style={{ transformStyle: 'preserve-3d' }}>
          {/* Page title */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                {activePage === 'dashboard' && 'Predictive Maintenance Dashboard'}
                {activePage === 'fleet' && 'Fleet Management'}
                {activePage === 'analytics' && 'Analytics & Insights'}
                {activePage === 'alerts' && 'Alert Management'}
                {activePage === 'maintenance' && 'Maintenance Scheduler'}
                {activePage === 'digital-twin' && 'Digital Twin Simulator'}
                {activePage === 'reports' && 'Management Reports'}
                {activePage === 'settings' && 'Settings'}
              </h2>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                {activePage === 'dashboard' && 'Real-time AI-powered monitoring & anomaly detection'}
                {activePage === 'fleet' && 'Monitor and manage your entire HVAC fleet'}
                {activePage === 'analytics' && 'Deep insights into sensor trends and performance'}
                {activePage === 'alerts' && 'Track and manage system alerts'}
                {activePage === 'maintenance' && 'AI-driven dynamic maintenance scheduling — not fixed, always optimized'}
                {activePage === 'digital-twin' && 'Virtual compressor model — simulate what-if scenarios'}
                {activePage === 'reports' && 'Weekly health trends, cost saved, and failures prevented'}
                {activePage === 'settings' && 'Configure system preferences'}
              </p>
            </div>
            {/* Refresh badge */}
            <div className="hidden lg:flex items-center gap-2 text-[11px] px-3 py-1.5 rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', color: 'var(--text-tertiary)' }}>
              <span className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${backendAvailable ? 'bg-status-ok' : 'bg-status-warn'}`} />
                <span className={`relative inline-flex rounded-full h-2 w-2 ${backendAvailable ? 'bg-status-ok' : 'bg-status-warn'}`} />
              </span>
              {backendAvailable
                ? `ML Model Active · Refreshing in ${countdown}s`
                : `Static Data Mode · Refreshing in ${countdown}s`
              }
            </div>
          </div>

          {/* Backend status banner — shows when connected to live ML */}
          {backendAvailable && apiStats && (
            <div className="flex items-center gap-4 px-4 py-2.5 rounded-xl text-xs font-semibold animate-fade-in"
              style={{ background: 'rgba(45,212,191,0.08)', border: '1px solid rgba(45,212,191,0.2)', color: 'var(--color-primary-400)' }}>
              <i className="fa-solid fa-brain"></i>
              <span>ML Engine Connected</span>
              <span style={{ color: 'var(--text-tertiary)' }}>·</span>
              <span>{apiStats.total_readings} readings analyzed</span>
              <span style={{ color: 'var(--text-tertiary)' }}>·</span>
              <span>{apiStats.total_anomalies} anomalies detected ({apiStats.anomaly_rate_percentage}%)</span>
              <span style={{ color: 'var(--text-tertiary)' }}>·</span>
              <span>Peak risk: {(apiStats.max_risk_score * 100).toFixed(1)}%</span>
            </div>
          )}

          {/* Dashboard page */}
          {activePage === 'dashboard' && (
            <>
              {/* Fleet stats row */}
              <FleetStats {...fleetStats} />

              {/* Main grid: Table + Symptoms | Chart + AI */}
              <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
                {/* Left column — 3/5 */}
                <div className="xl:col-span-3 space-y-6">
                  <CompressorTable
                    compressors={compressors}
                    selectedUnit={selectedUnit}
                    onSelectUnit={setSelectedUnit}
                    searchQuery={searchQuery}
                  />
                  <SensorChart data={trendData} />
                  <AlertFeed alerts={alerts} onAcknowledge={handleAcknowledge} />
                </div>

                {/* Right column — 2/5 */}
                <div className="xl:col-span-2 space-y-6">
                  <SensorCards unit={selectedCompressor} />
                  <SymptomTimeline symptoms={symptoms} />
                  <AIDiagnostics
                    unit={selectedCompressor}
                    onGenerateTicket={handleGenerateTicket}
                    ticketHistory={ticketHistory}
                    compressors={compressors}
                    onSelectUnit={setSelectedUnit}
                  />
                </div>
              </div>
            </>
          )}

          {/* Fleet page */}
          {activePage === 'fleet' && (
            <CompressorTable
              compressors={compressors}
              selectedUnit={selectedUnit}
              onSelectUnit={setSelectedUnit}
              searchQuery={searchQuery}
            />
          )}

          {/* Analytics page */}
          {activePage === 'analytics' && (
            <div className="space-y-6">
              <SensorChart data={trendData} />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold uppercase tracking-wider flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                      <i className="fa-solid fa-gauge text-accent-blue"></i>
                      Sensor Overview — {selectedUnit}
                    </h3>
                    <select 
                      value={selectedUnit}
                      onChange={e => setSelectedUnit(e.target.value)}
                      className="text-xs px-2 py-1.5 rounded-lg outline-none cursor-pointer font-semibold transition-colors"
                      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                    >
                      {compressors.map(c => <option key={c.id} value={c.id}>{c.id} ({c.status})</option>)}
                    </select>
                  </div>
                  <SensorCards unit={selectedCompressor} />
                </div>
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                    <i className="fa-solid fa-chart-pie text-primary-400"></i>
                    Fleet Summary
                  </h3>
                  <FleetStats {...fleetStats} compact={true} />
                </div>
              </div>
            </div>
          )}

          {/* Alerts page */}
          {activePage === 'alerts' && (
            <div className="space-y-6">
              <AlertFeed alerts={alerts} onAcknowledge={handleAcknowledge} />
              <SymptomTimeline symptoms={symptoms} />
            </div>
          )}

          {/* Maintenance page */}
          {activePage === 'maintenance' && (
            <MaintenanceScheduler events={maintenanceEvents} ticketHistory={ticketHistory} />
          )}

          {/* Digital Twin page */}
          {activePage === 'digital-twin' && (
            <DigitalTwin 
              unit={selectedCompressor} 
              allUnits={compressors}
              onSelectUnit={setSelectedUnit}
            />
          )}

          {/* Reports page */}
          {activePage === 'reports' && (
            <ReportsPanel reports={weeklyReports} />
          )}

          {/* Settings page */}
          {activePage === 'settings' && (
            <div className="glass-card-static rich-hover p-8">
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-16 h-16 rounded-2xl bg-accent-blue/10 flex items-center justify-center mb-6">
                  <i className="fa-solid fa-gear text-3xl text-accent-blue"></i>
                </div>
                <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Settings</h3>
                <p className="text-sm max-w-md" style={{ color: 'var(--text-tertiary)' }}>
                  Coming soon — configure alert thresholds, notification preferences, and team access controls.
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<DashboardContent />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
