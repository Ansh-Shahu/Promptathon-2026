import React, { useState } from 'react'
import type { Compressor, Sector } from '../data/mockData'
import { SECTORS } from '../data/mockData'

interface Props {
  compressors: Compressor[]
  selectedUnit: string | null
  onSelectUnit: (id: string) => void
  searchQuery: string
}

export default function CompressorTable({ compressors, selectedUnit, onSelectUnit, searchQuery }: Props) {
  const [sectorFilter, setSectorFilter] = useState<Sector | 'All'>('All')
  const [statusFilter, setStatusFilter] = useState<string>('All')
  const [showFilters, setShowFilters] = useState(true)

  const filtered = compressors.filter(c => {
    if (sectorFilter !== 'All' && c.sector !== sectorFilter) return false
    if (statusFilter !== 'All' && c.status !== statusFilter) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      return c.id.toLowerCase().includes(q) || c.name.toLowerCase().includes(q) || c.location.toLowerCase().includes(q) || c.sector.toLowerCase().includes(q)
    }
    return true
  })

  const statusIcon = (s: string) => {
    if (s === 'Critical') return <i className="fa-solid fa-circle-exclamation text-[12px] text-status-critical animate-blink"></i>
    if (s === 'Damaged') return <i className="fa-solid fa-triangle-exclamation text-[12px] text-gray-600 dark:text-orange-500 animate-blink"></i>
    if (s === 'Warning') return <i className="fa-solid fa-triangle-exclamation text-[12px] text-status-warn"></i>
    return <i className="fa-solid fa-circle-check text-[12px] text-status-ok"></i>
  }

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      Normal: 'text-status-ok bg-status-ok/10 border-status-ok/20',
      Warning: 'text-status-warn bg-status-warn/10 border-status-warn/20',
      Critical: 'text-status-critical bg-status-critical/10 border-status-critical/20',
      Damaged: 'text-gray-600 bg-gray-600/10 border-gray-600/20 dark:text-orange-500 dark:bg-orange-500/10 dark:border-orange-500/20',
    }
    return map[s] || ''
  }

  return (
    <div className="glass-card-static flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
          Compressor Fleet
        </h3>
        <button onClick={() => setShowFilters(f => !f)} className="flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg cursor-pointer transition-all rich-hover" style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>
          <i className="fa-solid fa-filter text-[11px]"></i>
          Filters
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex flex-wrap items-center gap-3 px-5 py-3 border-b animate-fade-in" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}>
          {/* Sector filter */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Sector:</span>
            <div className="flex gap-1 flex-wrap">
              {['All', ...SECTORS].map(s => (
                <button key={s} onClick={() => setSectorFilter(s as any)}
                  className={`text-[11px] px-2.5 py-1 rounded-lg font-medium cursor-pointer transition-all ${sectorFilter === s ? 'bg-primary-400/15 text-primary-400 border border-primary-400/30' : 'border hover:bg-[var(--bg-card-hover)]'}`}
                  style={sectorFilter !== s ? { color: 'var(--text-tertiary)', borderColor: 'var(--border-subtle)' } : {}}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          {/* Status filter */}
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Status:</span>
            {['All', 'Normal', 'Critical', 'Damaged'].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`text-[11px] px-2.5 py-1 rounded-lg font-medium cursor-pointer transition-all ${statusFilter === s ? 'bg-primary-400/15 text-primary-400 border border-primary-400/30' : 'border hover:bg-[var(--bg-card-hover)]'}`}
                style={statusFilter !== s ? { color: 'var(--text-tertiary)', borderColor: 'var(--border-subtle)' } : {}}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Column header */}
      <div className="grid grid-cols-[0.8fr_1.2fr_0.8fr_0.6fr_0.6fr_0.5fr_40px] gap-2 px-5 py-2.5 text-[10px] font-semibold uppercase tracking-widest border-b"
        style={{ color: 'var(--text-muted)', borderColor: 'var(--border-subtle)' }}>
        <span>Unit ID</span><span>Location</span><span>Sector</span><span>Efficiency</span><span>Power</span><span>Status</span><span></span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto max-h-[320px]">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
            No compressors match the current filters
          </div>
        ) : (
          filtered.map((c, i) => {
            const isActive = selectedUnit === c.id
            const isRisk = c.status === 'Critical'
            const displayEfficiency = c.status === 'Damaged' ? 0 : c.efficiency
            const efficiencyColor = displayEfficiency > 90 ? 'var(--color-status-ok)' : displayEfficiency > 80 ? 'var(--color-status-warn)' : 'var(--color-status-critical)'
            return (
              <button key={c.id} onClick={() => onSelectUnit(c.id)}
                className={`w-full grid grid-cols-[0.8fr_1.2fr_0.8fr_0.6fr_0.6fr_0.5fr_40px] gap-2 items-center px-5 py-3 border-b text-left cursor-pointer transition-all duration-200 ${isActive ? 'bg-primary-400/8 border-l-2 border-l-primary-400' : 'hover:bg-[var(--bg-card-hover)]'} ${isRisk ? 'animate-shimmer' : ''}`}
                style={{ borderBottomColor: 'var(--border-subtle)', animationDelay: `${i * 50}ms` }}
              >
                <span className={`text-sm font-semibold ${isRisk ? 'text-status-critical' : ''}`} style={isRisk ? {} : { color: 'var(--text-primary)' }}>{c.id}</span>
                <span className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  <i className="fa-solid fa-location-dot text-[11px]" style={{ color: 'var(--text-muted)' }}></i>{c.location}
                </span>
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-lg w-fit" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>{c.sector}</span>
                <span className="text-xs font-semibold" style={{ color: efficiencyColor }}>{displayEfficiency}%</span>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{c.powerDraw} kW</span>
                <span className="flex items-center gap-1">
                  {statusIcon(c.status)}
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${statusBadge(c.status)}`}>{c.status}</span>
                </span>
                <i className="fa-solid fa-chevron-right text-[11px]" style={{ color: 'var(--text-muted)' }}></i>
              </button>
            )
          })
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-5 py-2.5 border-t text-[11px]" style={{ borderColor: 'var(--border-default)', color: 'var(--text-muted)' }}>
        <span>Showing {filtered.length} of {compressors.length} compressors</span>
        <span>Filter: {sectorFilter} · {statusFilter}</span>
      </div>
    </div>
  )
}
