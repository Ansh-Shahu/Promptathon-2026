import React, { useState, useEffect } from 'react'
import type { AIPrediction, Compressor, Ticket } from '../data/mockData'
import { getAIPrediction } from '../data/mockData'
import Card3D from './Card3D'

interface Props {
  unit: Compressor | null
  onGenerateTicket: (ticket: Ticket) => void
  ticketHistory: Ticket[]
  compressors?: Compressor[]
  onSelectUnit?: (id: string) => void
}

export default function AIDiagnostics({ unit, onGenerateTicket, ticketHistory, compressors, onSelectUnit }: Props) {
  const [showHistory, setShowHistory] = useState(false)
  const [prediction, setPrediction] = useState<AIPrediction | null>(() => unit ? getAIPrediction(unit) : null)
  const [loading, setLoading] = useState(false)
  // Post-failure emergency cost: what it costs if the compressor actually breaks down
  const [postDamageCostRange, setPostDamageCostRange] = useState<[number, number] | null>(null)

  useEffect(() => {
    if (!unit) return
    setPrediction(getAIPrediction(unit))
    
    // Calculate emergency cost bounds
    if (unit.status === 'Critical') {
      setPostDamageCostRange([500000, 1500000])
    } else if (unit.status === 'Warning') {
      setPostDamageCostRange([150000, 300000])
    } else {
      setPostDamageCostRange(null)
    }
  }, [unit])

  useEffect(() => {
    if (!unit) return

    const hasExistingTicket = ticketHistory.some(t => t.compressorId === unit.id)
    const currentPrediction = prediction ?? getAIPrediction(unit)

    if (unit.status === 'Damaged' && !hasExistingTicket) {
      const autoTicket: Ticket = {
        id: `MT-${4072 + ticketHistory.length + 1}`,
        compressorId: unit.id,
        title: 'Damaged Compressor — Emergency Repair',
        description: `Damage detected on ${unit.id}. Auto-generated maintenance ticket to prioritize emergency repair.`,
        status: 'open',
        priority: 'critical',
        createdAt: new Date().toISOString(),
        assignee: 'Auto-Assigned',
        costEstimate: (currentPrediction.costEstimateRange[0] + currentPrediction.costEstimateRange[1]) / 2,
      }
      onGenerateTicket(autoTicket)
    }
  }, [unit, ticketHistory, onGenerateTicket, prediction])

  if (!unit) return null
  const effectivePrediction = prediction ?? getAIPrediction(unit)
  const isCritical = unit.status === 'Critical'
  const isWarn = unit.status === 'Warning'

  const handleGenerateTicket = () => {
    const newTicket: Ticket = {
      id: `MT-${4072 + ticketHistory.length}`,
      compressorId: unit.id,
      title: effectivePrediction.failureType,
      description: effectivePrediction.suggestedAction,
      status: 'open',
      priority: isCritical ? 'critical' : 'high',
      createdAt: new Date().toISOString(),
      assignee: 'Auto-Assigned',
      costEstimate: (effectivePrediction.costEstimateRange[0] + effectivePrediction.costEstimateRange[1]) / 2,
    }
    onGenerateTicket(newTicket)
  }

  const unitTickets = [...ticketHistory]
    .filter(t => t.compressorId === unit.id)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  const hasUnitTicket = unitTickets.length > 0

  return (
    <Card3D 
      className="relative animate-pulse-glow" 
      style={{ borderColor: 'rgba(45,212,191,0.2)' }}
      intensity={15}
    >
      {/* Gradient top bar */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-primary-400 via-accent-blue to-accent-purple z-20" />

      <div className="p-6">
        {/* Title */}
        <div className="flex items-center gap-2 mb-5 flex-wrap depth-md">
          <i className="fa-solid fa-wand-magic-sparkles text-primary-400"></i>
          <h3 className="text-base font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            AI Diagnostics
          </h3>
          {compressors && onSelectUnit && (
            <select
              value={unit.id}
              onChange={e => onSelectUnit(e.target.value)}
              className="text-xs px-2 py-1 rounded-lg outline-none cursor-pointer font-semibold transition-colors"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
            >
              {compressors.map(c => <option key={c.id} value={c.id}>{c.id} ({c.status})</option>)}
            </select>
          )}
          {!compressors && (
            <span className="text-base font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>— {unit.id}</span>
          )}
          <span className="ml-auto flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-accent-purple/10 text-accent-purple border border-accent-purple/20 shadow-sm">
            <i className="fa-solid fa-microchip text-[11px]"></i>
            Neural Engine v3.2
          </span>
        </div>

        {/* Detailed Prediction */}
        <div className="rounded-xl p-5 mb-4 depth-sm" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
          <div className="flex items-start gap-3">
            <i className={`fa-solid ${isCritical ? 'fa-circle-exclamation text-status-critical' : isWarn ? 'fa-triangle-exclamation text-status-warn' : 'fa-circle-check text-status-ok'} mt-0.5 text-lg`}></i>
            <div className="flex-1">
              {/* Failure Type & Time */}
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                  {effectivePrediction.failureType}
                </span>
                {effectivePrediction.timeToFailure !== 'N/A' && (
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${isCritical ? 'bg-status-critical/10 text-status-critical border border-status-critical/20' : 'bg-status-warn/10 text-status-warn border border-status-warn/20'}`}>
                    <i className="fa-solid fa-clock mr-1"></i>
                    ETA: {effectivePrediction.timeToFailure}
                  </span>
                )}
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-primary-400/10 text-primary-400 border border-primary-400/20">
                  {effectivePrediction.confidence}% confidence
                </span>
              </div>

              {/* Root Cause */}
              <p className="text-xs leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
                {effectivePrediction.rootCause}
              </p>

              {/* Suggested Action */}
              <div className="rounded-lg p-3 mb-3 depth-md" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', transform: 'translateZ(15px)' }}>
                <p className="text-[10px] uppercase tracking-wider font-semibold mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
                  <i className="fa-solid fa-lightbulb text-primary-400"></i> Suggested Action
                </p>
                <p className="text-xs font-medium leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                  {effectivePrediction.suggestedAction}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Cost & Energy Row */}
        <div className="grid grid-cols-2 gap-3 mb-3 depth-sm">
          {/* Preventive Maintenance Cost */}
          <div className="rounded-xl p-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
            <p className="text-[10px] uppercase tracking-wider mb-1.5 flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
              <i className="fa-solid fa-indian-rupee-sign text-[9px]"></i> Preventive Maint. Cost
            </p>
            <p className="text-base font-bold" style={{ color: effectivePrediction.costEstimateRange[1] > 100000 ? 'var(--color-status-critical)' : effectivePrediction.costEstimateRange[1] > 15000 ? 'var(--color-status-warn)' : 'var(--color-status-ok)' }}>
              ₹{effectivePrediction.costEstimateRange[0].toLocaleString('en-IN')} – ₹{effectivePrediction.costEstimateRange[1].toLocaleString('en-IN')}
            </p>
            <p className="text-[9px] mt-1" style={{ color: 'var(--text-muted)' }}>Act now to prevent failure</p>
          </div>
          {/* Energy Optimization */}
          <div className="rounded-xl p-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
            <p className="text-[10px] uppercase tracking-wider mb-1.5 flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
              <i className="fa-solid fa-leaf text-[9px] text-status-ok"></i> Energy Insight
            </p>
            <p className="text-[11px] leading-relaxed font-medium" style={{ color: 'var(--text-primary)' }}>
              {effectivePrediction.energySavingTip.substring(0, 80)}...
            </p>
          </div>
        </div>

        {/* Post-Failure Emergency Cost — only shown when there is a real risk */}
        {postDamageCostRange && (
          <div className="rounded-xl p-3 mb-4 depth-sm animate-fade-in" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.25)' }}>
            <p className="text-[10px] uppercase tracking-wider mb-2 flex items-center gap-1.5 font-semibold" style={{ color: '#ef4444' }}>
              <i className="fa-solid fa-triangle-exclamation text-[10px]"></i>
              If Left Unattended — Post-Failure Emergency Cost
            </p>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <p className="text-base font-bold" style={{ color: '#dc2626' }}>
                ₹{postDamageCostRange[0].toLocaleString('en-IN')} – ₹{postDamageCostRange[1].toLocaleString('en-IN')}
              </p>
              <span className="text-[9px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.12)', color: '#b91c1c' }}>
                {Math.round(postDamageCostRange[1] / effectivePrediction.costEstimateRange[1])}x more expensive
              </span>
            </div>
            <p className="text-[10px] mt-1.5 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Includes emergency labour, parts replacement, system downtime losses &amp; expedited shipping.
            </p>
          </div>
        )}

        {/* Action */}
        {(isCritical || isWarn || unit.status === 'Damaged') && (
          <div className="depth-lg">
            {hasUnitTicket ? (
              <button disabled className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl bg-status-ok/15 text-status-ok font-semibold text-sm border border-status-ok/30 cursor-default">
                <i className="fa-solid fa-circle-check text-lg"></i>
                Ticket Generated · Technician Dispatched
              </button>
            ) : (
              <button onClick={handleGenerateTicket}
                className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-primary-400 to-accent-blue hover:shadow-[0_0_24px_rgba(45,212,191,0.35)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 cursor-pointer"
                style={{ color: 'var(--text-on-primary)' }}
              >
                <i className="fa-solid fa-paper-plane"></i>
                Generate Ticket & Dispatch Technician
              </button>
            )}
            {loading && (
              <div className="mt-3 px-3 py-2 rounded-lg text-[11px] font-medium" style={{ background: 'rgba(59,130,246,0.08)', color: 'var(--text-primary)' }}>
                Fetching prediction from backend...
              </div>
            )}
          </div>
        )}

        {/* Ticket History Toggle */}
        {unitTickets.length > 0 && (
          <div className="mt-4 depth-sm">
            <button onClick={() => setShowHistory(!showHistory)}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-[11px] font-semibold cursor-pointer transition-all hover:bg-[var(--bg-card-hover)]"
              style={{ color: 'var(--text-tertiary)', border: '1px solid var(--border-subtle)' }}
            >
              <i className={`fa-solid ${showHistory ? 'fa-chevron-up' : 'fa-chevron-down'} text-[9px]`}></i>
              {showHistory ? 'Hide' : 'View'} Ticket History ({unitTickets.length})
            </button>
            {showHistory && (
              <div className="mt-3 space-y-2 animate-fade-in">
                {unitTickets.map(t => (
                  <div key={t.id} className="rounded-lg p-3 flex items-start gap-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                    <i className={`fa-solid fa-ticket mt-0.5 text-xs ${t.status === 'resolved' || t.status === 'closed' ? 'text-status-ok' : t.priority === 'critical' ? 'text-status-critical' : 'text-status-warn'}`}></i>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[11px] font-bold" style={{ color: 'var(--text-primary)' }}>#{t.id}</span>
                        <span className={`text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded-full ${
                          t.status === 'resolved' ? 'bg-status-ok/10 text-status-ok' :
                          t.status === 'in-progress' ? 'bg-accent-blue/10 text-accent-blue' :
                          'bg-status-warn/10 text-status-warn'
                        }`}>{t.status}</span>
                        <span className="text-[9px] text-[var(--text-tertiary)]">{new Date(t.createdAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                      <p className="text-[11px] mb-1" style={{ color: 'var(--text-secondary)' }}>{t.title}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Card3D>
  )
}
