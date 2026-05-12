import React, { useState } from 'react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import type { TrendDataPoint } from '../data/mockData'
import Card3D from './Card3D'

interface Props {
  data: TrendDataPoint[]
}

type ChartMetric = 'vibration' | 'pressure' | 'temperature' | 'power'

const metrics: { key: ChartMetric; label: string; unit: string; color: string }[] = [
  { key: 'vibration', label: 'Vibration', unit: 'mm/s', color: '#ef4444' },
  { key: 'pressure', label: 'Pressure', unit: 'PSI', color: '#38bdf8' },
  { key: 'temperature', label: 'Temperature', unit: '°F', color: '#facc15' },
  { key: 'power', label: 'Power', unit: 'kW', color: '#a78bfa' },
]

export default function SensorChart({ data }: Props) {
  const { isDark } = useTheme()
  const [activeMetrics, setActiveMetrics] = useState<Set<ChartMetric>>(new Set(['vibration', 'pressure']))
  const gridColor = isDark ? '#1e293b' : '#e2e8f0'
  const tickColor = isDark ? '#64748b' : '#94a3b8'
  const tooltipBg = isDark ? '#111827' : '#ffffff'
  const tooltipBorder = isDark ? '#334155' : '#e2e8f0'

  const toggle = (m: ChartMetric) => {
    setActiveMetrics(prev => {
      const next = new Set(prev)
      if (next.has(m)) { if (next.size > 1) next.delete(m) }
      else next.add(m)
      return next
    })
  }

  return (
    <Card3D className="p-5" intensity={5}>
      <div className="flex items-center justify-between mb-4 depth-md">
        <div className="flex items-center gap-2">
          <TrendingUp size={16} className="text-accent-blue" />
          <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
            Live Sensor Trends
          </h3>
        </div>
        <div className="flex gap-1.5">
          {metrics.map(m => (
            <button key={m.key} onClick={() => toggle(m.key)}
              className={`text-[10px] font-semibold px-2.5 py-1 rounded-lg cursor-pointer transition-all border ${activeMetrics.has(m.key) ? 'opacity-100' : 'opacity-40'}`}
              style={{
                color: m.color,
                background: activeMetrics.has(m.key) ? `${m.color}15` : 'transparent',
                borderColor: activeMetrics.has(m.key) ? `${m.color}30` : 'var(--border-subtle)',
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <defs>
            {metrics.filter(m => activeMetrics.has(m.key)).map(m => (
              <linearGradient key={m.key} id={`grad-${m.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={m.color} stopOpacity={0.2} />
                <stop offset="95%" stopColor={m.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey="time" tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} tickLine={false} />
          <Tooltip contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 10, fontSize: 12, color: isDark ? '#e2e8f0' : '#0f172a' }} />
          {metrics.filter(m => activeMetrics.has(m.key)).map(m => (
            <Area key={m.key} type="monotone" dataKey={m.key} name={`${m.label} (${m.unit})`}
              stroke={m.color} strokeWidth={2} fill={`url(#grad-${m.key})`}
              dot={false} activeDot={{ r: 4, strokeWidth: 0 }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </Card3D>
  )
}
