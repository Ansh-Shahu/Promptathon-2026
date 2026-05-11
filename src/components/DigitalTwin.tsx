import React, { useState } from 'react'
import type { Compressor } from '../data/mockData'
import { getAIPrediction } from '../data/mockData'

interface Props {
  unit: Compressor | null
  allUnits: Compressor[]
  onSelectUnit: (id: string) => void
}

export default function DigitalTwin({ unit, allUnits, onSelectUnit }: Props) {
  const [loadMultiplier, setLoadMultiplier] = useState(1.0)
  const [simulating, setSimulating] = useState(false)
  const [simResult, setSimResult] = useState<null | {
    temp: number; vibration: number; pressure: number; efficiency: number; risk: string; recommendation: string
  }>(null)

  if (!unit) {
    return (
      <div className="glass-card-static rich-hover p-8">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent-blue/10 flex items-center justify-center mb-6">
            <i className="fa-solid fa-cube text-3xl text-accent-blue"></i>
          </div>
          <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Digital Twin</h3>
          <p className="text-sm max-w-md" style={{ color: 'var(--text-tertiary)' }}>
            Select a compressor unit to view its digital twin model and run simulations.
          </p>
        </div>
      </div>
    )
  }

  const prediction = getAIPrediction(unit)

  const runSimulation = () => {
    setSimulating(true)
    setTimeout(() => {
      const tempIncrease = (loadMultiplier - 1) * 15
      const vibIncrease = (loadMultiplier - 1) * 2.5
      const pressureDrop = (loadMultiplier - 1) * 12
      const effDrop = (loadMultiplier - 1) * 8

      const simTemp = Math.round(unit.temperature + tempIncrease)
      const simVib = +(unit.vibration + vibIncrease).toFixed(1)
      const simPressure = Math.round(unit.pressure - pressureDrop)
      const simEff = Math.max(60, +(unit.efficiency - effDrop).toFixed(1))

      let risk = 'Low'
      let recommendation = 'System can handle this load. Continue monitoring.'
      if (simTemp > 85 || simVib > 4.0) {
        risk = 'Critical'
        recommendation = `Load increase to ${(loadMultiplier * 100).toFixed(0)}% would cause critical conditions within 24 hours. NOT recommended. Reduce load to below 110%.`
      } else if (simTemp > 78 || simVib > 3.0) {
        risk = 'High'
        recommendation = `Load at ${(loadMultiplier * 100).toFixed(0)}% increases failure risk significantly. Limit to 4-hour bursts with cooldown periods.`
      } else if (simTemp > 74) {
        risk = 'Moderate'
        recommendation = `Load at ${(loadMultiplier * 100).toFixed(0)}% is sustainable short-term. Schedule inspection within 48 hours.`
      }

      setSimResult({ temp: simTemp, vibration: simVib, pressure: simPressure, efficiency: simEff, risk, recommendation })
      setSimulating(false)
    }, 1500)
  }

  const riskColor = (r: string) => {
    if (r === 'Critical') return 'var(--color-status-critical)'
    if (r === 'High') return 'var(--color-status-warn)'
    if (r === 'Moderate') return 'var(--color-accent-amber)'
    return 'var(--color-status-ok)'
  }

  return (
    <div className="space-y-6">
      {/* Twin Model */}
      <div className="glass-card-static overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'var(--border-default)' }}>
          <div className="flex items-center gap-2">
            <i className="fa-solid fa-cube text-accent-blue"></i>
            <h3 className="text-sm font-bold uppercase tracking-wider flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              DIGITAL TWIN —
              <select
                value={unit.id}
                onChange={(e) => onSelectUnit(e.target.value)}
                className="bg-transparent border-none outline-none font-bold uppercase cursor-pointer text-accent-blue hover:opacity-80 transition-opacity"
              >
                {allUnits.map(u => (
                  <option key={u.id} value={u.id} className="bg-[var(--bg-card)] text-[var(--text-primary)]">
                    {u.id} - {u.name}
                  </option>
                ))}
              </select>
            </h3>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-blue/10 text-accent-blue font-semibold border border-accent-blue/20">
            <i className="fa-solid fa-signal mr-1"></i>Live Sync
          </span>
        </div>

        <div className="p-5">
          {/* Virtual Model Visualization */}
          <div className="relative rounded-xl p-6 mb-5 overflow-hidden" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
            <div className="absolute inset-0 opacity-5">
              <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(45,212,191,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(45,212,191,0.3) 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
            </div>
            <div className="relative grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: 'Temperature', value: unit.temperature, unit: '°F', icon: 'fa-temperature-half', color: unit.temperature > 80 ? '#ef4444' : '#2dd4bf', optimal: `${prediction.optimalRange.tempMin}-${prediction.optimalRange.tempMax}°F` },
                { label: 'Vibration', value: unit.vibration, unit: 'mm/s', icon: 'fa-wave-square', color: unit.vibration > 3.5 ? '#ef4444' : '#22c55e', optimal: '0.5-2.5 mm/s' },
                { label: 'Pressure', value: unit.pressure, unit: 'PSI', icon: 'fa-gauge-high', color: unit.pressure < 115 ? '#ef4444' : '#38bdf8', optimal: `${prediction.optimalRange.pressureMin}-${prediction.optimalRange.pressureMax} PSI` },
                { label: 'Efficiency', value: unit.efficiency, unit: '%', icon: 'fa-bolt', color: unit.efficiency > 90 ? '#22c55e' : '#facc15', optimal: '90-100%' },
              ].map(s => (
                <div key={s.label} className="text-center">
                  <i className={`fa-solid ${s.icon} text-2xl mb-2`} style={{ color: s.color }}></i>
                  <p className="text-2xl font-extrabold" style={{ color: s.color }}>{s.value}<span className="text-xs font-normal ml-1" style={{ color: 'var(--text-muted)' }}>{s.unit}</span></p>
                  <p className="text-[10px] font-medium" style={{ color: 'var(--text-tertiary)' }}>{s.label}</p>
                  <p className="text-[9px] mt-1" style={{ color: 'var(--text-muted)' }}>Optimal: {s.optimal}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Simulation Controls */}
          <div className="rounded-xl p-5" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
            <h4 className="text-xs font-bold uppercase tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <i className="fa-solid fa-flask text-accent-purple"></i>
              What-If Simulation
            </h4>
            <div className="flex items-center gap-4 mb-4">
              <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Load Adjustment:</label>
              <input type="range" min="0.8" max="1.5" step="0.05" value={loadMultiplier}
                onChange={e => { setLoadMultiplier(parseFloat(e.target.value)); setSimResult(null) }}
                className="flex-1 accent-primary-400"
              />
              <span className="text-sm font-bold min-w-[50px] text-right" style={{ color: loadMultiplier > 1.2 ? 'var(--color-status-critical)' : 'var(--color-primary-400)' }}>
                {(loadMultiplier * 100).toFixed(0)}%
              </span>
            </div>
            <button onClick={runSimulation} disabled={simulating}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-accent-purple to-accent-blue hover:shadow-[0_0_24px_rgba(167,139,250,0.35)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 cursor-pointer disabled:opacity-50"
              style={{ color: '#fff' }}
            >
              {simulating ? (
                <><i className="fa-solid fa-spinner fa-spin"></i> Running Simulation...</>
              ) : (
                <><i className="fa-solid fa-play"></i> Simulate Load at {(loadMultiplier * 100).toFixed(0)}%</>
              )}
            </button>

            {/* Results */}
            {simResult && (
              <div className="mt-4 rounded-xl p-4 animate-fade-in" style={{ background: 'var(--bg-card)', border: `1px solid ${riskColor(simResult.risk)}30` }}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: riskColor(simResult.risk) }}>
                    <i className="fa-solid fa-triangle-exclamation mr-1"></i>
                    Risk Level: {simResult.risk}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-3 mb-3">
                  {[
                    { label: 'Temp', value: `${simResult.temp}°F`, delta: simResult.temp - unit.temperature },
                    { label: 'Vibration', value: `${simResult.vibration}mm/s`, delta: +(simResult.vibration - unit.vibration).toFixed(1) },
                    { label: 'Pressure', value: `${simResult.pressure}PSI`, delta: simResult.pressure - unit.pressure },
                    { label: 'Efficiency', value: `${simResult.efficiency}%`, delta: +(simResult.efficiency - unit.efficiency).toFixed(1) },
                  ].map(m => (
                    <div key={m.label} className="text-center">
                      <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{m.value}</p>
                      <p className="text-[10px]" style={{ color: m.delta > 0 ? 'var(--color-status-critical)' : 'var(--color-status-ok)' }}>
                        {m.delta > 0 ? '+' : ''}{m.delta}
                      </p>
                      <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>{m.label}</p>
                    </div>
                  ))}
                </div>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  <i className="fa-solid fa-robot text-primary-400 mr-1"></i>
                  {simResult.recommendation}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
