import React, { useMemo } from 'react'
import type { Compressor } from '../data/mockData'
import { AreaChart, Area, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import Card3D from './Card3D'
import { useTheme } from '../context/ThemeContext'

interface Props {
  unit: Compressor | null
}

const generateSparkline = (baseValue: number, volatility: number, trend: 'up' | 'down' | 'flat') => {
  return Array.from({ length: 20 }).map((_, i) => {
    let trendFactor = 0;
    if (trend === 'up') trendFactor = i * (volatility / 5);
    if (trend === 'down') trendFactor = -i * (volatility / 5);
    return {
      val: Math.max(0, baseValue + (Math.sin(i) * volatility) + (Math.random() * volatility * 0.5) + trendFactor)
    }
  })
}

export default function SensorCards({ unit }: Props) {
  const { isDark } = useTheme()
  if (!unit) return null

  // If unit is damaged, apply special color scheme
  const damagedColor = isDark ? '#f97316' : '#4b5563' // orange in dark, dark gray in light

  // Generate stable mock trend data for charts based on current unit values
  const vibData = useMemo(() => generateSparkline(unit.vibration, 0.5, unit.vibration > 3.0 ? 'up' : 'flat'), [unit.id, unit.vibration])
  const tempData = useMemo(() => generateSparkline(unit.temperature, 2, unit.temperature > 75 ? 'up' : 'flat'), [unit.id, unit.temperature])
  const powerData = useMemo(() => generateSparkline(unit.powerDraw, 5, 'flat'), [unit.id, unit.powerDraw])

  const cards = [
    {
      type: 'area',
      data: vibData,
      label: 'Vibration RMS', value: unit.vibration, unit: 'mm/s',
      subLabel: 'Average RMS (last 8 hrs)',
      isCritical: unit.vibration > 3.5,
      isWarn: unit.vibration > 2.5 && unit.vibration <= 3.5,
      color: unit.status === 'Damaged' ? damagedColor : (unit.vibration > 3.5 ? '#ef4444' : unit.vibration > 2.5 ? '#eab308' : '#8b5cf6'),
      badge: unit.status === 'Damaged' ? 'Damaged' : (unit.vibration > 3.5 ? 'Critical' : unit.vibration > 2.5 ? 'Warning' : 'Normal'),
      badgeColor: unit.status === 'Damaged' ? 'text-gray-600 border border-gray-600 dark:text-orange-500 dark:border-orange-500 bg-transparent' : (unit.vibration > 3.5 ? 'text-red-600 border border-red-600 dark:text-red-400 dark:border-red-400 bg-transparent' : unit.vibration > 2.5 ? 'text-yellow-600 border border-yellow-600 dark:text-yellow-400 dark:border-yellow-400 bg-transparent' : 'text-emerald-600 border border-emerald-600 dark:text-emerald-400 dark:border-emerald-400 bg-transparent'),
    },
    {
      type: 'area',
      data: tempData,
      label: 'Temperature', value: unit.temperature, unit: '°F',
      subLabel: 'Average Temp. (last 8 hrs)',
      isCritical: unit.temperature > 80,
      isWarn: unit.temperature > 75 && unit.temperature <= 80,
      color: unit.status === 'Damaged' ? damagedColor : (unit.temperature > 80 ? '#ef4444' : unit.temperature > 75 ? '#eab308' : '#ec4899'),
      badge: unit.status === 'Damaged' ? 'Damaged' : (unit.temperature > 80 ? 'Critical' : unit.temperature > 75 ? 'Warning' : 'Normal'),
      badgeColor: unit.status === 'Damaged' ? 'text-gray-600 border border-gray-600 dark:text-orange-500 dark:border-orange-500 bg-transparent' : (unit.temperature > 80 ? 'text-red-600 border border-red-600 dark:text-red-400 dark:border-red-400 bg-transparent' : unit.temperature > 75 ? 'text-yellow-600 border border-yellow-600 dark:text-yellow-400 dark:border-yellow-400 bg-transparent' : 'text-emerald-600 border border-emerald-600 dark:text-emerald-400 dark:border-emerald-400 bg-transparent'),
    },
    {
      type: 'gauge',
      label: 'Pressure', value: unit.pressure, unit: 'PSI',
      subLabel: 'Average Pressure (last 8 hrs)',
      isCritical: unit.pressure < 115,
      isWarn: unit.pressure >= 115 && unit.pressure < 120,
      color: unit.status === 'Damaged' ? damagedColor : (unit.pressure < 115 ? '#ef4444' : unit.pressure < 120 ? '#eab308' : '#10b981'),
      badge: unit.status === 'Damaged' ? 'Damaged' : (unit.pressure < 115 ? 'Low' : unit.pressure < 120 ? 'Warning' : 'Within Range'),
      badgeColor: unit.status === 'Damaged' ? 'text-gray-600 border border-gray-600 dark:text-orange-500 dark:border-orange-500 bg-transparent' : (unit.pressure < 115 ? 'text-red-600 border border-red-600 dark:text-red-400 dark:border-red-400 bg-transparent' : unit.pressure < 120 ? 'text-yellow-600 border border-yellow-600 dark:text-yellow-400 dark:border-yellow-400 bg-transparent' : 'text-emerald-600 border border-emerald-600 dark:text-emerald-400 dark:border-emerald-400 bg-transparent'),
      gaugeValue: Math.min(100, Math.max(0, ((unit.pressure - 100) / 50) * 100)),
    },
    {
      type: 'arc',
      data: powerData,
      label: 'Power Draw', value: unit.powerDraw, unit: 'kW',
      subLabel: 'Average Load (last 8 hrs)',
      isCritical: unit.efficiency < 85,
      isWarn: unit.efficiency >= 85 && unit.efficiency < 92,
      color: unit.status === 'Damaged' ? damagedColor : (unit.efficiency < 85 ? '#ef4444' : unit.efficiency < 92 ? '#eab308' : '#6366f1'),
      badge: unit.status === 'Damaged' ? 'Damaged' : (unit.efficiency < 85 ? 'High Load' : 'Normal'),
      badgeColor: unit.status === 'Damaged' ? 'text-gray-600 border border-gray-600 dark:text-orange-500 dark:border-orange-500 bg-transparent' : (unit.efficiency < 85 ? 'text-red-600 border border-red-600 dark:text-red-400 dark:border-red-400 bg-transparent' : 'text-emerald-600 border border-emerald-600 dark:text-emerald-400 dark:border-emerald-400 bg-transparent'),
      arcValue: unit.efficiency,
    },
  ]

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between mb-4 px-1">
        <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
          <i className={`fa-solid fa-microchip mr-2 ${unit.status === 'Damaged' ? (isDark ? 'text-orange-500' : 'text-gray-600') : 'text-accent-blue'}`}></i>
          Live Sensors — {unit.id}
        </h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cards.map((c, i) => (
          <Card3D
            key={i}
            className="flex flex-col justify-between p-5"
            intensity={12}
          >
            {/* Header: Title + Badge */}
            <div className="flex items-start justify-between mb-2 depth-md">
              <h4 className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                {c.label}
              </h4>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded shadow-sm ${c.badgeColor}`}>
                {c.badge}
              </span>
            </div>

            {/* Chart Area */}
            <div className="h-24 w-full flex items-center justify-center my-2 relative depth-sm">
              {c.type === 'area' && c.data && (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={c.data} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id={`colorUv-${i}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={c.color} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={c.color} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="val" stroke={c.color} strokeWidth={2} fillOpacity={1} fill={`url(#colorUv-${i})`} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              )}

              {c.type === 'gauge' && (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                    <Pie
                      data={[{ value: c.gaugeValue }, { value: 100 - (c.gaugeValue || 0) }]}
                      cx="50%" cy="100%"
                      startAngle={180} endAngle={0}
                      innerRadius="70%" outerRadius="100%"
                      stroke="none"
                      dataKey="value"
                      isAnimationActive={false}
                    >
                      <Cell fill={c.color} />
                      <Cell fill="var(--border-subtle)" />
                    </Pie>
                    {/* Needle representation - approximate */}
                    <path d="M 50% 100% L 50% 30%" stroke="var(--text-primary)" strokeWidth="3" strokeLinecap="round" transform={`rotate(${((c.gaugeValue || 0) / 100) * 180 - 90} 50 100)`} style={{ transformOrigin: '50% 100%' }} />
                    <circle cx="50%" cy="100%" r="6" fill="var(--text-primary)" />
                  </PieChart>
                </ResponsiveContainer>
              )}

              {c.type === 'arc' && (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                    <Pie
                      data={[{ value: c.arcValue }, { value: 100 - (c.arcValue || 0) }]}
                      cx="50%" cy="100%"
                      startAngle={180} endAngle={0}
                      innerRadius="75%" outerRadius="100%"
                      stroke="none"
                      dataKey="value"
                      isAnimationActive={false}
                    >
                      <Cell fill={c.color} />
                      <Cell fill="var(--border-subtle)" />
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Value & SubLabel */}
            <div className="text-center mt-auto pt-2 depth-lg">
              <div className="text-2xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                {c.value} <span className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>{c.unit}</span>
              </div>
              <div className="text-[10px] mt-1" style={{ color: 'var(--text-secondary)' }}>
                {c.subLabel}
              </div>
            </div>
          </Card3D>
        ))}
      </div>
    </div>
  )
}

