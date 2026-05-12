// ──────────────────────────────────────────────────────────
//  Centralized mock data — swap this layer for real API later
// ──────────────────────────────────────────────────────────

export type Status = 'Normal' | 'Warning' | 'Critical' | 'Damaged'
export type Sector = 'Commercial' | 'Industrial' | 'Residential' | 'Data Center' | 'Healthcare'

export interface Compressor {
  id: string
  name: string
  location: string
  sector: Sector
  status: Status
  temperature: number
  vibration: number
  pressure: number
  powerDraw: number
  runtime: number
  efficiency: number
  lastMaintenance: string
  nextMaintenance: string
  model: string
}

export interface DetectedSymptom {
  id: string
  compressorId: string
  symptom: string
  severity: Status
  detectedAt: string
  confidence: number
  sensor: string
}

export interface AlertEntry {
  id: string
  compressorId: string
  type: 'anomaly' | 'threshold' | 'predictive'
  message: string
  timestamp: string
  severity: Status
  acknowledged: boolean
}

export interface TrendDataPoint {
  time: string
  vibration: number
  pressure: number
  temperature: number
  power: number
}

export interface Ticket {
  id: string
  compressorId: string
  title: string
  description: string
  status: 'open' | 'in-progress' | 'resolved' | 'closed'
  priority: 'low' | 'medium' | 'high' | 'critical'
  createdAt: string
  resolvedAt?: string
  assignee: string
  costEstimate: number
}

export interface MaintenanceEvent {
  id: string
  compressorId: string
  type: 'predictive' | 'preventive' | 'corrective'
  title: string
  scheduledDate: string
  status: 'scheduled' | 'in-progress' | 'completed' | 'overdue'
  assignee: string
  estimatedCost: number
  notes: string
}

export interface WeeklyReport {
  weekLabel: string
  healthScore: number
  failuresPrevented: number
  costSaved: number
  energySaved: number
  ticketsResolved: number
  avgEfficiency: number
}

// ── AI Prediction Output ─────────────────────────────────
export interface AIPrediction {
  compressorId: string
  failureType: string
  timeToFailure: string
  confidence: number
  rootCause: string
  suggestedAction: string
  costEstimateRange: [number, number]
  energySavingTip: string
  optimalRange: { tempMin: number; tempMax: number; pressureMin: number; pressureMax: number }
}

export function getAIPrediction(unit: Compressor): AIPrediction {
  if (unit.status === 'Critical') {
    return {
      compressorId: unit.id,
      failureType: 'Compressor Bearing Seizure',
      timeToFailure: '36–48 hours',
      confidence: 92,
      rootCause: `Overheating (${unit.temperature}°F) combined with vibration anomaly (${unit.vibration} mm/s) indicates bearing degradation. Runtime of ${unit.runtime}h exceeds recommended service interval.`,
      suggestedAction: 'Reduce load by 20% immediately. Schedule emergency bearing replacement within 24 hours. Flush lubrication system.',
      costEstimateRange: [4500, 8200],
      energySavingTip: `Operating at ${unit.efficiency}% efficiency wastes ~${((100 - unit.efficiency) * unit.powerDraw / 100).toFixed(1)} kW. Restoring to 95%+ saves ₹${((100 - unit.efficiency) * unit.powerDraw * 8 * 30 / 100).toFixed(0)}/month.`,
      optimalRange: { tempMin: 65, tempMax: 75, pressureMin: 125, pressureMax: 140 },
    }
  }
  if (unit.status === 'Warning') {
    return {
      compressorId: unit.id,
      failureType: 'Bearing Wear / Refrigerant Leak',
      timeToFailure: '7–14 days',
      confidence: 78,
      rootCause: `Elevated suction temperature (${unit.temperature}°F) and vibration signature (${unit.vibration} mm/s) suggest early-stage bearing wear. Oil pressure fluctuation detected.`,
      suggestedAction: 'Schedule preventive maintenance within 5 days. Inspect bearing assembly and check refrigerant levels. Consider operating in energy-efficient mode (reduce load 10%).',
      costEstimateRange: [1200, 3500],
      energySavingTip: `Switch to energy-efficient mode to save ~${(unit.powerDraw * 0.12).toFixed(1)} kW. Estimated monthly saving: ₹${(unit.powerDraw * 0.12 * 8 * 30).toFixed(0)}.`,
      optimalRange: { tempMin: 65, tempMax: 75, pressureMin: 125, pressureMax: 140 },
    }
  }
  return {
    compressorId: unit.id,
    failureType: 'None Detected',
    timeToFailure: 'N/A',
    confidence: 97,
    rootCause: 'All sensor parameters within normal operating range. No anomalies detected.',
    suggestedAction: 'Continue normal operation. Next scheduled maintenance is sufficient.',
    costEstimateRange: [0, 500],
    energySavingTip: `System running optimally at ${unit.efficiency}% efficiency. Current power draw of ${unit.powerDraw} kW is within expected range.`,
    optimalRange: { tempMin: 65, tempMax: 75, pressureMin: 125, pressureMax: 140 },
  }
}

// ── Sectors ─────────────────────────────────────────────
export const SECTORS: Sector[] = ['Commercial', 'Industrial', 'Residential', 'Data Center', 'Healthcare']

// ── Compressor Fleet ────────────────────────────────────
export const compressors: Compressor[] = [
  {
    id: 'CMP-001', name: 'Carrier 30XA-252',
    location: 'Building A — Rooftop', sector: 'Commercial',
    status: 'Normal', temperature: 72, vibration: 1.8, pressure: 132,
    powerDraw: 45.2, runtime: 8420, efficiency: 94.2,
    lastMaintenance: '2026-03-15', nextMaintenance: '2026-06-15',
    model: 'Carrier 30XA',
  },
  {
    id: 'CMP-002', name: 'Carrier 30HXC-375',
    location: 'Building B — Basement', sector: 'Commercial',
    status: 'Normal', temperature: 68, vibration: 1.5, pressure: 128,
    powerDraw: 52.8, runtime: 6240, efficiency: 96.1,
    lastMaintenance: '2026-02-20', nextMaintenance: '2026-05-20',
    model: 'Carrier 30HXC',
  },
  {
    id: 'CMP-003', name: 'Carrier 06T-Screw',
    location: 'Sector 4 Server Room', sector: 'Data Center',
    status: 'Critical', temperature: 88, vibration: 4.2, pressure: 110,
    powerDraw: 68.5, runtime: 12800, efficiency: 78.3,
    lastMaintenance: '2025-11-10', nextMaintenance: '2026-02-10',
    model: 'Carrier 06T',
  },
  {
    id: 'CMP-004', name: 'Carrier 30RB-262',
    location: 'Building C — Floor 3', sector: 'Healthcare',
    status: 'Normal', temperature: 70, vibration: 1.2, pressure: 135,
    powerDraw: 38.1, runtime: 4560, efficiency: 97.5,
    lastMaintenance: '2026-04-01', nextMaintenance: '2026-07-01',
    model: 'Carrier 30RB',
  },
  {
    id: 'CMP-005', name: 'Carrier 30XW-552',
    location: 'Warehouse — East Wing', sector: 'Industrial',
    status: 'Damaged', temperature: 81, vibration: 3.1, pressure: 118,
    powerDraw: 72.3, runtime: 9800, efficiency: 85.7,
    lastMaintenance: '2026-01-05', nextMaintenance: '2026-04-05',
    model: 'Carrier 30XW',
  },
  {
    id: 'CMP-006', name: 'Carrier 30MPA-640',
    location: 'Tower D — Penthouse', sector: 'Residential',
    status: 'Normal', temperature: 69, vibration: 1.0, pressure: 130,
    powerDraw: 41.6, runtime: 3200, efficiency: 98.2,
    lastMaintenance: '2026-03-28', nextMaintenance: '2026-06-28',
    model: 'Carrier 30MPA',
  },
  {
    id: 'CMP-007', name: 'Carrier 30HXC-190',
    location: 'Data Hall Alpha', sector: 'Data Center',
    status: 'Normal', temperature: 71, vibration: 1.6, pressure: 129,
    powerDraw: 55.0, runtime: 7600, efficiency: 93.8,
    lastMaintenance: '2026-02-14', nextMaintenance: '2026-05-14',
    model: 'Carrier 30HXC',
  },
  {
    id: 'CMP-008', name: 'Carrier 06N-Recip',
    location: 'Plant Floor B2', sector: 'Industrial',
    status: 'Normal', temperature: 79, vibration: 2.9, pressure: 120,
    powerDraw: 63.4, runtime: 11200, efficiency: 87.1,
    lastMaintenance: '2025-12-20', nextMaintenance: '2026-03-20',
    model: 'Carrier 06N',
  },
  {
    id: 'CMP-009', name: 'Carrier 19DV-Centrifugal',
    location: 'Hospital Main Wing', sector: 'Healthcare',
    status: 'Normal', temperature: 71, vibration: 1.1, pressure: 131,
    powerDraw: 85.2, runtime: 2100, efficiency: 95.4,
    lastMaintenance: '2026-04-10', nextMaintenance: '2026-07-10',
    model: 'Carrier 19DV',
  },
  {
    id: 'CMP-010', name: 'Carrier 30XV-AirCooled',
    location: 'Mall Complex Roof', sector: 'Commercial',
    status: 'Normal', temperature: 74, vibration: 1.9, pressure: 127,
    powerDraw: 48.9, runtime: 5400, efficiency: 92.1,
    lastMaintenance: '2026-01-15', nextMaintenance: '2026-04-15',
    model: 'Carrier 30XV',
  },
  {
    id: 'CMP-011', name: 'Carrier 23RV-Screw',
    location: 'Manufacturing Plant', sector: 'Industrial',
    status: 'Normal', temperature: 75, vibration: 2.0, pressure: 125,
    powerDraw: 95.0, runtime: 15400, efficiency: 89.5,
    lastMaintenance: '2026-02-05', nextMaintenance: '2026-05-05',
    model: 'Carrier 23RV',
  },
  {
    id: 'CMP-012', name: 'Carrier AquaForce',
    location: 'Hotel Basement', sector: 'Residential',
    status: 'Normal', temperature: 80, vibration: 2.8, pressure: 122,
    powerDraw: 58.7, runtime: 8900, efficiency: 86.4,
    lastMaintenance: '2025-12-10', nextMaintenance: '2026-03-10',
    model: 'Carrier AquaForce',
  },
  {
    id: 'CMP-013', name: 'Carrier 30KAV',
    location: 'Data Center Omega', sector: 'Data Center',
    status: 'Normal', temperature: 68, vibration: 1.3, pressure: 130,
    powerDraw: 70.1, runtime: 4300, efficiency: 96.8,
    lastMaintenance: '2026-03-01', nextMaintenance: '2026-06-01',
    model: 'Carrier 30KAV',
  },
  {
    id: 'CMP-014', name: 'Carrier 30CX',
    location: 'Clinic Annex', sector: 'Healthcare',
    status: 'Normal', temperature: 70, vibration: 1.4, pressure: 128,
    powerDraw: 32.5, runtime: 3100, efficiency: 97.2,
    lastMaintenance: '2026-04-05', nextMaintenance: '2026-07-05',
    model: 'Carrier 30CX',
  },
  {
    id: 'CMP-015', name: 'Carrier 30XW',
    location: 'Logistics Hub', sector: 'Commercial',
    status: 'Critical', temperature: 85, vibration: 3.9, pressure: 112,
    powerDraw: 66.8, runtime: 14200, efficiency: 80.1,
    lastMaintenance: '2025-10-20', nextMaintenance: '2026-01-20',
    model: 'Carrier 30XW',
  }
]

// ── Detected Symptoms ───────────────────────────────────
export function generateSymptoms(): DetectedSymptom[] {
  const now = new Date()
  return [
    {
      id: 'SYM-001', compressorId: 'CMP-003',
      symptom: 'Abnormal vibration pattern detected',
      severity: 'Critical', detectedAt: new Date(now.getTime() - 120000).toISOString(),
      confidence: 94, sensor: 'Accelerometer',
    },
    {
      id: 'SYM-002', compressorId: 'CMP-003',
      symptom: 'Discharge pressure below threshold',
      severity: 'Critical', detectedAt: new Date(now.getTime() - 300000).toISOString(),
      confidence: 89, sensor: 'Pressure Transducer',
    },
    {
      id: 'SYM-003', compressorId: 'CMP-005',
      symptom: 'Elevated suction temperature',
      severity: 'Warning', detectedAt: new Date(now.getTime() - 600000).toISOString(),
      confidence: 76, sensor: 'RTD Sensor',
    },
    {
      id: 'SYM-004', compressorId: 'CMP-005',
      symptom: 'Bearing wear signature in vibration FFT',
      severity: 'Warning', detectedAt: new Date(now.getTime() - 900000).toISOString(),
      confidence: 72, sensor: 'Vibration Analyzer',
    },
    {
      id: 'SYM-005', compressorId: 'CMP-008',
      symptom: 'Oil pressure fluctuation detected',
      severity: 'Warning', detectedAt: new Date(now.getTime() - 1500000).toISOString(),
      confidence: 68, sensor: 'Oil Pressure Sensor',
    },
    {
      id: 'SYM-006', compressorId: 'CMP-003',
      symptom: 'Power draw exceeding rated capacity',
      severity: 'Critical', detectedAt: new Date(now.getTime() - 180000).toISOString(),
      confidence: 91, sensor: 'Power Meter',
    },
  ]
}

// ── Alert History ───────────────────────────────────────
export function generateAlerts(): AlertEntry[] {
  const now = new Date()
  return [
    {
      id: 'ALT-001', compressorId: 'CMP-003', type: 'predictive',
      message: '85% probability of compressor failure within 12 hours',
      timestamp: new Date(now.getTime() - 60000).toISOString(),
      severity: 'Critical', acknowledged: false,
    },
    {
      id: 'ALT-002', compressorId: 'CMP-005', type: 'threshold',
      message: 'Temperature exceeded warning threshold (80°F)',
      timestamp: new Date(now.getTime() - 420000).toISOString(),
      severity: 'Warning', acknowledged: false,
    },
    {
      id: 'ALT-003', compressorId: 'CMP-008', type: 'anomaly',
      message: 'Unusual oil pressure pattern detected by AI',
      timestamp: new Date(now.getTime() - 1200000).toISOString(),
      severity: 'Warning', acknowledged: true,
    },
    {
      id: 'ALT-004', compressorId: 'CMP-003', type: 'threshold',
      message: 'Vibration level exceeded critical threshold (4.0 mm/s)',
      timestamp: new Date(now.getTime() - 90000).toISOString(),
      severity: 'Critical', acknowledged: false,
    },
  ]
}

// ── Trend Data Generator ────────────────────────────────
export function generateTrendData(hours: number = 24): TrendDataPoint[] {
  const data: TrendDataPoint[] = []
  const now = new Date()
  for (let i = hours; i >= 0; i--) {
    const t = new Date(now.getTime() - i * 3600000)
    const progress = (hours - i) / hours
    data.push({
      time: t.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      vibration: +(1.8 + progress * 2.4 + Math.random() * 0.3).toFixed(2),
      pressure: +(132 - progress * 22 + Math.random() * 3).toFixed(1),
      temperature: +(68 + progress * 20 + Math.random() * 2).toFixed(1),
      power: +(42 + progress * 26 + Math.random() * 4).toFixed(1),
    })
  }
  return data
}

// ── Fleet Summary Stats ─────────────────────────────────
export function getFleetStats(units: Compressor[]) {
  const total = units.length
  const normal = units.filter(u => u.status === 'Normal').length
  const warning = units.filter(u => u.status === 'Warning').length
  const critical = units.filter(u => u.status === 'Critical').length
  const damaged = units.filter(u => u.status === 'Damaged').length
  const avgEfficiency = +(units.reduce((s, u) => s + u.efficiency, 0) / total).toFixed(1)
  const totalPower = +(units.reduce((s, u) => s + u.powerDraw, 0)).toFixed(1)
  return { total, normal, warning, critical, damaged, avgEfficiency, totalPower }
}

// ── Ticket History ──────────────────────────────────────
export function generateTicketHistory(): Ticket[] {
  return [
    {
      id: 'MT-4068', compressorId: 'CMP-008', title: 'Oil Pressure Anomaly Fix',
      description: 'Replaced oil pressure relief valve and cleaned oil filter assembly.',
      status: 'resolved', priority: 'medium', createdAt: '2026-04-20T09:30:00Z',
      resolvedAt: '2026-04-22T14:00:00Z', assignee: 'Mike Rivera', costEstimate: 2100,
    },
    {
      id: 'MT-4069', compressorId: 'CMP-012', title: 'Bearing Inspection & Lubrication',
      description: 'Preventive bearing inspection. Minor wear detected — lubricated and monitored.',
      status: 'resolved', priority: 'low', createdAt: '2026-04-22T11:00:00Z',
      resolvedAt: '2026-04-23T10:00:00Z', assignee: 'Sarah Chen', costEstimate: 850,
    },
    {
      id: 'MT-4070', compressorId: 'CMP-015', title: 'Emergency Compressor Shutdown',
      description: 'Critical vibration levels triggered auto-shutdown. Bearing replacement required.',
      status: 'in-progress', priority: 'critical', createdAt: '2026-04-28T16:00:00Z',
      assignee: 'James Park', costEstimate: 6500,
    },
    {
      id: 'MT-4071', compressorId: 'CMP-005', title: 'Temperature Sensor Calibration',
      description: 'RTD sensor reading elevated. Recalibrated and validated against reference.',
      status: 'open', priority: 'high', createdAt: '2026-04-30T08:15:00Z',
      assignee: 'Lisa Wong', costEstimate: 450,
    },
  ]
}

// ── Maintenance Schedule ────────────────────────────────
export function generateMaintenanceSchedule(): MaintenanceEvent[] {
  return [
    {
      id: 'SCH-001', compressorId: 'CMP-003', type: 'predictive',
      title: 'Emergency Bearing Replacement',
      scheduledDate: '2026-05-03', status: 'scheduled',
      assignee: 'James Park', estimatedCost: 7500,
      notes: 'AI predicted bearing failure in 36-48h. Parts pre-ordered.',
    },
    {
      id: 'SCH-002', compressorId: 'CMP-005', type: 'preventive',
      title: 'Vibration Analysis & Bearing Service',
      scheduledDate: '2026-05-06', status: 'scheduled',
      assignee: 'Mike Rivera', estimatedCost: 2200,
      notes: 'Early bearing wear detected. Preventive service to avoid escalation.',
    },
    {
      id: 'SCH-003', compressorId: 'CMP-008', type: 'preventive',
      title: 'Oil System Inspection',
      scheduledDate: '2026-05-08', status: 'scheduled',
      assignee: 'Sarah Chen', estimatedCost: 1100,
      notes: 'Follow-up on oil pressure fluctuation. Full oil system flush.',
    },
    {
      id: 'SCH-004', compressorId: 'CMP-015', type: 'corrective',
      title: 'Full Compressor Overhaul',
      scheduledDate: '2026-05-04', status: 'in-progress',
      assignee: 'James Park', estimatedCost: 12000,
      notes: 'Critical unit. Complete disassembly, bearing + seal replacement.',
    },
    {
      id: 'SCH-005', compressorId: 'CMP-012', type: 'preventive',
      title: 'Refrigerant Level Check',
      scheduledDate: '2026-05-10', status: 'scheduled',
      assignee: 'Lisa Wong', estimatedCost: 600,
      notes: 'Routine refrigerant check. Top-up if below optimal level.',
    },
    {
      id: 'SCH-006', compressorId: 'CMP-001', type: 'preventive',
      title: 'Quarterly Filter Replacement',
      scheduledDate: '2026-04-28', status: 'completed',
      assignee: 'Mike Rivera', estimatedCost: 350,
      notes: 'Standard quarterly maintenance. All filters replaced.',
    },
  ]
}

// ── Weekly Reports ──────────────────────────────────────
export function generateWeeklyReports(): WeeklyReport[] {
  return [
    { weekLabel: 'Apr 7–13', healthScore: 94, failuresPrevented: 1, costSaved: 8500, energySaved: 320, ticketsResolved: 3, avgEfficiency: 93.2 },
    { weekLabel: 'Apr 14–20', healthScore: 91, failuresPrevented: 2, costSaved: 14200, energySaved: 480, ticketsResolved: 5, avgEfficiency: 91.8 },
    { weekLabel: 'Apr 21–27', healthScore: 88, failuresPrevented: 1, costSaved: 6800, energySaved: 290, ticketsResolved: 4, avgEfficiency: 90.5 },
    { weekLabel: 'Apr 28–May 4', healthScore: 85, failuresPrevented: 3, costSaved: 21500, energySaved: 560, ticketsResolved: 6, avgEfficiency: 89.1 },
  ]
}
