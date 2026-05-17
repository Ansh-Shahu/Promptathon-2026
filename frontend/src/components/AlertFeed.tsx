import React from 'react'
import { Bell, CheckCircle, AlertTriangle, Clock, BrainCircuit, Gauge, Radio } from 'lucide-react'
import type { AlertEntry } from '../data/mockData'
import Card3D from './Card3D'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`
}

const typeIcon: Record<string, React.ReactNode> = {
  predictive: <BrainCircuit size={14} className="text-accent-purple" />,
  threshold: <Gauge size={14} className="text-status-warn" />,
  anomaly: <Radio size={14} className="text-accent-blue" />,
}

const typeLabel: Record<string, string> = {
  predictive: 'AI Predictive',
  threshold: 'Threshold',
  anomaly: 'Anomaly Detection',
}

interface Props {
  alerts: AlertEntry[]
  onAcknowledge: (id: string) => void
}

export default function AlertFeed({ alerts, onAcknowledge }: Props) {
  const sorted = [...alerts].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

  return (
    <Card3D className="flex flex-col overflow-hidden" intensity={8}>
      <div className="flex items-center justify-between px-5 py-4 border-b depth-md" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-2">
          <Bell size={16} className="text-status-critical" />
          <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
            Alert Feed
          </h3>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-status-critical/10 text-status-critical font-semibold">
          {alerts.filter(a => !a.acknowledged).length} unread
        </span>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[280px] depth-sm">
        {sorted.map((a, i) => (
          <div key={a.id}
            className={`px-5 py-3.5 border-b flex items-start gap-3 transition-colors hover:bg-[var(--bg-card-hover)] animate-fade-in ${a.acknowledged ? 'opacity-50' : ''}`}
            style={{ borderColor: 'var(--border-subtle)', animationDelay: `${i * 60}ms` }}
          >
            <span className="mt-0.5 flex-shrink-0">
              {a.severity === 'Critical' ? <AlertTriangle size={16} className="text-status-critical animate-blink" /> : <AlertTriangle size={16} className="text-status-warn" />}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{a.compressorId}</span>
                <span className="flex items-center gap-1 text-[9px] font-semibold px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>
                  {typeIcon[a.type]} {typeLabel[a.type]}
                </span>
              </div>
              <p className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>{a.message}</p>
              <div className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <Clock size={10} />
                <span>{new Date(a.timestamp).toLocaleTimeString()}</span>
                <span>· {timeAgo(a.timestamp)}</span>
              </div>
            </div>
            {!a.acknowledged && (
              <button onClick={() => onAcknowledge(a.id)}
                className="text-[10px] font-semibold px-2 py-1 rounded-lg cursor-pointer transition-all text-primary-400 hover:bg-primary-400/10 border border-primary-400/20 flex-shrink-0"
              >
                Ack
              </button>
            )}
            {a.acknowledged && (
              <CheckCircle size={14} className="text-status-ok flex-shrink-0 mt-1" />
            )}
          </div>
        ))}
      </div>
    </Card3D>
  )
}
