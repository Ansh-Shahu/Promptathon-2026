import React, { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'
import { useTheme } from '../context/ThemeContext'
import type { WeeklyReport } from '../data/mockData'

interface Props {
  reports: WeeklyReport[]
}

export default function ReportsPanel({ reports }: Props) {
  const { isDark } = useTheme()
  const [activeTab, setActiveTab] = useState<'overview' | 'cost' | 'energy'>('overview')

  const totalFailuresPrevented = reports.reduce((s, r) => s + r.failuresPrevented, 0)
  const totalCostSaved = reports.reduce((s, r) => s + r.costSaved, 0)
  const totalEnergySaved = reports.reduce((s, r) => s + r.energySaved, 0)
  const totalTickets = reports.reduce((s, r) => s + r.ticketsResolved, 0)
  const avgHealth = +(reports.reduce((s, r) => s + r.healthScore, 0) / reports.length).toFixed(1)

  const gridColor = isDark ? '#1e293b' : '#e2e8f0'
  const tickColor = isDark ? '#64748b' : '#94a3b8'

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Avg Health Score', value: `${avgHealth}%`, icon: 'fa-heart-pulse', color: 'var(--color-status-ok)', bg: 'rgba(34,197,94,0.12)' },
          { label: 'Failures Prevented', value: totalFailuresPrevented, icon: 'fa-shield-halved', color: 'var(--color-primary-400)', bg: 'rgba(45,212,191,0.12)' },
          { label: 'Cost Saved', value: `₹${(totalCostSaved / 1000).toFixed(1)}k`, icon: 'fa-piggy-bank', color: 'var(--color-accent-purple)', bg: 'rgba(167,139,250,0.12)' },
          { label: 'Energy Saved', value: `${totalEnergySaved} kWh`, icon: 'fa-leaf', color: 'var(--color-status-ok)', bg: 'rgba(34,197,94,0.12)' },
          { label: 'Tickets Resolved', value: totalTickets, icon: 'fa-ticket', color: 'var(--color-accent-blue)', bg: 'rgba(56,189,248,0.12)' },
        ].map(c => (
          <div key={c.label} className="glass-card rich-hover p-4">
            <div className="flex items-center gap-3">
              <span className="flex items-center justify-center w-9 h-9 rounded-xl" style={{ background: c.bg }}>
                <i className={`fa-solid ${c.icon} text-sm`} style={{ color: c.color }}></i>
              </span>
              <div>
                <p className="text-[10px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>{c.label}</p>
                <p className="text-lg font-extrabold" style={{ color: 'var(--text-primary)' }}>{c.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="glass-card-static overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'var(--border-default)' }}>
          <div className="flex items-center gap-2">
            <i className="fa-solid fa-chart-bar text-accent-purple"></i>
            <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
              Weekly Management Report
            </h3>
          </div>
          <div className="flex gap-1">
            {(['overview', 'cost', 'energy'] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`text-[11px] font-semibold px-3 py-1.5 rounded-lg cursor-pointer transition-all ${activeTab === tab ? 'bg-primary-400/15 text-primary-400 border border-primary-400/30' : 'hover:bg-[var(--bg-card-hover)]'}`}
                style={activeTab !== tab ? { color: 'var(--text-tertiary)', border: '1px solid var(--border-subtle)' } : {}}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="p-5">
          {activeTab === 'overview' && (
            <div>
              <p className="text-xs mb-4" style={{ color: 'var(--text-tertiary)' }}>Health score trend and failures prevented over the past 4 weeks</p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={reports}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="weekLabel" tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} />
                  <YAxis tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} domain={[70, 100]} />
                  <Tooltip contentStyle={{ background: isDark ? '#111827' : '#fff', border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`, borderRadius: 10, fontSize: 12 }} />
                  <Line type="monotone" dataKey="healthScore" name="Health Score (%)" stroke="#2dd4bf" strokeWidth={2} dot={{ r: 4 }} />
                  <Line type="monotone" dataKey="avgEfficiency" name="Avg Efficiency (%)" stroke="#38bdf8" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {activeTab === 'cost' && (
            <div>
              <p className="text-xs mb-4" style={{ color: 'var(--text-tertiary)' }}>Cost savings from predictive maintenance per week</p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={reports}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="weekLabel" tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} />
                  <YAxis tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} />
                  <Tooltip contentStyle={{ background: isDark ? '#111827' : '#fff', border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`, borderRadius: 10, fontSize: 12 }} formatter={(value: any) => [`₹${Number(value).toLocaleString()}`, '']} />
                  <Bar dataKey="costSaved" name="Cost Saved (₹)" fill="#a78bfa" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {activeTab === 'energy' && (
            <div>
              <p className="text-xs mb-4" style={{ color: 'var(--text-tertiary)' }}>Energy savings from AI-optimized operations per week</p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={reports}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="weekLabel" tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} />
                  <YAxis tick={{ fill: tickColor, fontSize: 10 }} axisLine={{ stroke: gridColor }} />
                  <Tooltip contentStyle={{ background: isDark ? '#111827' : '#fff', border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`, borderRadius: 10, fontSize: 12 }} formatter={(value: any) => [`${Number(value)} kWh`, '']} />
                  <Bar dataKey="energySaved" name="Energy Saved (kWh)" fill="#22c55e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Weekly Breakdown Table */}
        <div className="px-5 pb-5">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                {['Week', 'Health', 'Failures Prevented', 'Cost Saved', 'Energy Saved', 'Tickets'].map(h => (
                  <th key={h} className="py-2 text-left text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.weekLabel} className="border-b hover:bg-[var(--bg-card-hover)] transition-colors" style={{ borderColor: 'var(--border-subtle)' }}>
                  <td className="py-2.5 font-medium" style={{ color: 'var(--text-primary)' }}>{r.weekLabel}</td>
                  <td className="py-2.5">
                    <span className={`font-semibold ${r.healthScore >= 90 ? 'text-status-ok' : r.healthScore >= 85 ? 'text-status-warn' : 'text-status-critical'}`}>{r.healthScore}%</span>
                  </td>
                  <td className="py-2.5 font-semibold text-primary-400">{r.failuresPrevented}</td>
                  <td className="py-2.5 font-semibold text-accent-purple">₹{r.costSaved.toLocaleString()}</td>
                  <td className="py-2.5 font-semibold text-status-ok">{r.energySaved} kWh</td>
                  <td className="py-2.5 font-semibold text-accent-blue">{r.ticketsResolved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
