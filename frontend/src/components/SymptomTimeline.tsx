import React from 'react'
import { AlertTriangle, Clock, Cpu, Radio } from 'lucide-react'
import type { DetectedSymptom } from '../data/mockData'
import Card3D from './Card3D'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ${mins % 60}m ago`
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: true,
  })
}

interface Props {
  symptoms: DetectedSymptom[]
}

export default function SymptomTimeline({ symptoms }: Props) {
  const sorted = [...symptoms].sort((a, b) => new Date(b.detectedAt).getTime() - new Date(a.detectedAt).getTime())

  return (
    <Card3D className="flex flex-col overflow-hidden" intensity={10}>
      <div className="flex items-center justify-between px-5 py-4 border-b depth-md" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-2">
          <Radio size={16} className="text-accent-purple" />
          <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
            Detected Symptoms
          </h3>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-purple/10 text-accent-purple font-semibold shadow-sm">
          {symptoms.length} active
        </span>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[320px] divide-y depth-sm" style={{ '--tw-divide-opacity': '1' } as any}>
        {sorted.map((sym, i) => {
          const isCritical = sym.severity === 'Critical'
          return (
            <div key={sym.id}
              className="px-5 py-3.5 flex items-start gap-3 transition-colors hover:bg-[var(--bg-card-hover)] animate-fade-in"
              style={{ animationDelay: `${i * 80}ms`, borderColor: 'var(--border-subtle)' }}
            >
              {/* Timeline dot */}
              <div className="flex flex-col items-center gap-1 pt-0.5">
                <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${isCritical ? 'bg-status-critical animate-blink' : 'bg-status-warn'}`} />
                {i < sorted.length - 1 && <span className="w-px flex-1 min-h-[20px]" style={{ background: 'var(--border-subtle)' }} />}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold" style={{ color: isCritical ? 'var(--color-status-critical)' : 'var(--color-status-warn)' }}>
                    {sym.compressorId}
                  </span>
                  <span className={`text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded-full border ${isCritical ? 'text-status-critical bg-status-critical/10 border-status-critical/20' : 'text-status-warn bg-status-warn/10 border-status-warn/20'}`}>
                    {sym.severity}
                  </span>
                </div>
                <p className="text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>
                  {sym.symptom}
                </p>
                <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  <span className="flex items-center gap-1">
                    <Clock size={10} />
                    {formatTimestamp(sym.detectedAt)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Cpu size={10} />
                    {sym.sensor}
                  </span>
                  <span className="ml-auto font-semibold text-primary-400">
                    {sym.confidence}% confidence
                  </span>
                </div>
              </div>

              <span className="text-[10px] font-medium whitespace-nowrap pt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                {timeAgo(sym.detectedAt)}
              </span>
            </div>
          )
        })}
      </div>
    </Card3D>
  )
}
