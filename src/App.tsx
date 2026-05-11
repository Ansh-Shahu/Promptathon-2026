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
  compressors,
  generateSymptoms,
  generateAlerts,
  generateTrendData,
  getFleetStats,
  generateTicketHistory,
  generateMaintenanceSchedule,
  generateWeeklyReports,
  type DetectedSymptom,
  type AlertEntry,
  type TrendDataPoint,
  type Ticket,
  type MaintenanceEvent,
  type WeeklyReport,
} from './data/mockData'

const REFRESH_INTERVAL = 30 // seconds

function DashboardContent() {
  const [activePage, setActivePage] = useState<NavPage>('dashboard')
  const [selectedUnit, setSelectedUnit] = useState<string>('CMP-003')
  const [searchQuery, setSearchQuery] = useState('')
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  // Live data state
  const [symptoms, setSymptoms] = useState<DetectedSymptom[]>(generateSymptoms)
  const [alerts, setAlerts] = useState<AlertEntry[]>(generateAlerts)
  const [trendData, setTrendData] = useState<TrendDataPoint[]>(() => generateTrendData(24))
  const [ticketHistory, setTicketHistory] = useState<Ticket[]>(generateTicketHistory)
  const [maintenanceEvents] = useState<MaintenanceEvent[]>(generateMaintenanceSchedule)
  const [weeklyReports] = useState<WeeklyReport[]>(generateWeeklyReports)

  const fleetStats = getFleetStats(compressors)
  const selectedCompressor = compressors.find(c => c.id === selectedUnit) || null

  // Auto-refresh every 30 seconds
  const doRefresh = useCallback(() => {
    setSymptoms(generateSymptoms())
    setAlerts(prev => prev.map(a => ({ ...a })))
    setTrendData(generateTrendData(24))
    setLastRefresh(new Date())
    setCountdown(REFRESH_INTERVAL)
  }, [])

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
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-app)' }}>
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
                <span className="absolute inline-flex h-full w-full rounded-full bg-status-ok opacity-75 animate-ping" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-status-ok" />
              </span>
              Detection System Active · Refreshing in {countdown}s
            </div>
          </div>

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
