import React from 'react'
import Card3D from './Card3D'
import { useTheme } from '../context/ThemeContext'

interface StatCardProps {
  iconClass: string
  label: string
  value: string | number
  suffix?: string
  trend?: string
  trendUp?: boolean
  accentColor: string
  accentBg: string
}

function StatCard({ iconClass, label, value, suffix, trend, trendUp, accentColor, accentBg, compact }: StatCardProps & { compact?: boolean }) {
  if (compact) {
    return (
      <Card3D className="p-4 flex items-center gap-4 animate-fade-in" intensity={10}>
        <div className="flex items-center justify-center w-12 h-12 shrink-0 rounded-xl depth-md" style={{ background: accentBg }}>
          <i className={`${iconClass} text-xl`} style={{ color: accentColor }}></i>
        </div>
        <div className="flex-1 min-w-0 depth-lg">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <p className="text-[10px] uppercase tracking-wider font-bold truncate" style={{ color: 'var(--text-secondary)' }}>{label}</p>
            {trend && (
              <span className={`text-[10px] font-bold ${trendUp ? 'text-status-ok' : 'text-status-critical'}`}>
                {trendUp ? '↑' : '↓'} {trend.replace(/[^0-9.%+-]/g, '')}
              </span>
            )}
          </div>
          <p className="text-xl font-black tracking-tight" style={{ color: 'var(--text-primary)' }}>
            {value}
            {suffix && <span className="text-[11px] font-bold ml-1 opacity-60 uppercase">{suffix}</span>}
          </p>
        </div>
      </Card3D>
    )
  }

  return (
    <Card3D className="p-5 flex flex-col gap-3 animate-fade-in" intensity={15}>
      <div className="flex items-center justify-between depth-md">
        <span className="flex items-center justify-center w-10 h-10 rounded-xl" style={{ background: accentBg }}>
          <i className={`${iconClass} text-lg`} style={{ color: accentColor }}></i>
        </span>
        {trend && (
          <span className={`flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${trendUp ? 'text-status-ok bg-status-ok/10' : 'text-status-critical bg-status-critical/10'}`}>
            <i className={`fa-solid fa-arrow-trend-up text-[10px] ${trendUp ? '' : 'rotate-180'}`}></i>
            {trend}
          </span>
        )}
      </div>
      <div className="depth-lg">
        <p className="text-[11px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{label}</p>
        <p className="text-2xl tracking-tight" style={{ color: 'var(--text-primary)', fontWeight: 800 }}>
          {value}
          {suffix && <span className="text-sm font-medium ml-1" style={{ color: 'var(--text-muted)', fontWeight: 500 }}>{suffix}</span>}
        </p>
      </div>
    </Card3D>
  )
}

interface FleetStatsProps {
  total: number; normal: number; warning: number; critical: number; damaged: number; avgEfficiency: number; totalPower: number;
  compact?: boolean;
}

export default function FleetStats({ total, normal, warning, critical, damaged, avgEfficiency, totalPower, compact = false }: FleetStatsProps) {
  const { isDark } = useTheme()
  const damagedColor = isDark ? '#f97316' : '#4b5563' // orange in dark, dark grey in light
  const damagedBg = isDark ? 'rgba(249,115,22,0.15)' : 'rgba(75,85,99,0.15)'
  
  const gridClasses = compact 
    ? "grid grid-cols-1 md:grid-cols-2 gap-4"
    : "grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4"

  return (
    <div className={gridClasses}>
      <StatCard compact={compact} iconClass="fa-solid fa-server" label="Total Units" value={total} suffix="units" trend="+2 this month" trendUp accentColor="var(--color-primary-400)" accentBg="rgba(45,212,191,0.2)" />
      <StatCard compact={compact} iconClass="fa-solid fa-circle-check" label="Normal" value={normal} suffix="units" accentColor="var(--color-status-ok)" accentBg="rgba(34,197,94,0.2)" />
      <StatCard compact={compact} iconClass="fa-solid fa-circle-exclamation animate-blink" label="Critical" value={critical} suffix="units" accentColor="var(--color-status-critical)" accentBg="rgba(239,68,68,0.2)" />
      <StatCard compact={compact} iconClass="fa-solid fa-triangle-exclamation" label="Damaged" value={damaged} suffix="units" accentColor={damagedColor} accentBg={damagedBg} />
      <StatCard compact={compact} iconClass="fa-solid fa-gauge" label="Avg Efficiency" value={avgEfficiency} suffix="%" trend="+1.3%" trendUp accentColor="var(--color-accent-blue)" accentBg="rgba(56,189,248,0.2)" />
      <StatCard compact={compact} iconClass="fa-solid fa-bolt-lightning" label="Total Power" value={totalPower} suffix="kW" trend="-3.2%" trendUp={false} accentColor="var(--color-accent-purple)" accentBg="rgba(167,139,250,0.2)" />
    </div>
  )
}
