import React from 'react'
import type { MaintenanceEvent, Ticket } from '../data/mockData'
import Card3D from './Card3D'

interface Props {
  events: MaintenanceEvent[]
  ticketHistory?: Ticket[]
}

export default function MaintenanceScheduler({ events, ticketHistory = [] }: Props) {
  const sorted = [...events].sort((a, b) => new Date(a.scheduledDate).getTime() - new Date(b.scheduledDate).getTime())
  const latestTickets = [...ticketHistory].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  const statusColors: Record<string, string> = {
    scheduled: 'bg-accent-blue/10 text-accent-blue border-accent-blue/20',
    'in-progress': 'bg-status-warn/10 text-status-warn border-status-warn/20',
    completed: 'bg-status-ok/10 text-status-ok border-status-ok/20',
    overdue: 'bg-status-critical/10 text-status-critical border-status-critical/20',
  }
  const typeColors: Record<string, { icon: string; color: string }> = {
    predictive: { icon: 'fa-brain', color: 'text-accent-purple' },
    preventive: { icon: 'fa-shield-halved', color: 'text-accent-blue' },
    corrective: { icon: 'fa-wrench', color: 'text-status-warn' },
  }

  const totalCost = events.reduce((s, e) => s + e.estimatedCost, 0)
  const upcoming = events.filter(e => e.status === 'scheduled').length
  const inProgress = events.filter(e => e.status === 'in-progress').length

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Events', value: events.length, icon: 'fa-calendar', color: 'var(--color-primary-400)', bg: 'rgba(45,212,191,0.12)' },
          { label: 'Upcoming', value: upcoming, icon: 'fa-clock', color: 'var(--color-accent-blue)', bg: 'rgba(56,189,248,0.12)' },
          { label: 'In Progress', value: inProgress, icon: 'fa-spinner', color: 'var(--color-status-warn)', bg: 'rgba(250,204,21,0.12)' },
          { label: 'Est. Total Cost', value: `₹${(totalCost / 1000).toFixed(1)}k`, icon: 'fa-indian-rupee-sign', color: 'var(--color-accent-purple)', bg: 'rgba(167,139,250,0.12)' },
        ].map(c => (
          <Card3D key={c.label} className="p-4" intensity={10}>
            <div className="flex items-center gap-3 depth-md">
              <span className="flex items-center justify-center w-10 h-10 rounded-xl" style={{ background: c.bg }}>
                <i className={`fa-solid ${c.icon}`} style={{ color: c.color }}></i>
              </span>
              <div>
                <p className="text-[10px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>{c.label}</p>
                <p className="text-xl font-extrabold" style={{ color: 'var(--text-primary)' }}>{c.value}</p>
              </div>
            </div>
          </Card3D>
        ))}
      </div>

      {/* Schedule Timeline */}
      <Card3D className="overflow-hidden" intensity={5}>
        <div className="flex items-center justify-between px-5 py-4 border-b depth-md" style={{ borderColor: 'var(--border-default)' }}>
          <div className="flex items-center gap-2">
            <i className="fa-solid fa-calendar-check text-primary-400"></i>
            <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
              Dynamic Maintenance Schedule
            </h3>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-400/10 text-primary-400 font-semibold shadow-sm">
            AI-Optimized
          </span>
        </div>

        <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
          {sorted.map((event, i) => {
            const tc = typeColors[event.type] || typeColors.preventive
            const isToday = event.scheduledDate === new Date().toISOString().split('T')[0]
            return (
              <div key={event.id} className={`px-5 py-4 flex items-start gap-4 transition-colors hover:bg-[var(--bg-card-hover)] animate-fade-in ${isToday ? 'border-l-2 border-l-primary-400' : ''}`}
                style={{ animationDelay: `${i * 60}ms`, borderBottomColor: 'var(--border-subtle)' }}
              >
                {/* Type Icon */}
                <div className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--bg-elevated)' }}>
                  <i className={`fa-solid ${tc.icon} ${tc.color}`}></i>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{event.compressorId}</span>
                    <span className={`text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded-full border ${statusColors[event.status]}`}>
                      {event.status}
                    </span>
                    <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>
                      {event.type}
                    </span>
                  </div>
                  <p className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{event.title}</p>
                  <p className="text-xs mb-2" style={{ color: 'var(--text-tertiary)' }}>{event.notes}</p>
                  <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    <span><i className="fa-solid fa-calendar mr-1"></i>{event.scheduledDate}</span>
                    <span><i className="fa-solid fa-user mr-1"></i>{event.assignee}</span>
                    <span className="font-semibold" style={{ color: 'var(--color-accent-purple)' }}>
                      <i className="fa-solid fa-indian-rupee-sign mr-0.5"></i>{event.estimatedCost.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Card3D>

      {/* Recent Maintenance Tickets */}
      <Card3D className="overflow-hidden" intensity={5}>
        <div className="flex items-center justify-between px-5 py-4 border-b depth-md" style={{ borderColor: 'var(--border-default)' }}>
          <div className="flex items-center gap-2">
            <i className="fa-solid fa-list-check text-accent-purple"></i>
            <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
              Recent Maintenance Tickets
            </h3>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-blue/10 text-accent-blue font-semibold shadow-sm">
            Latest first
          </span>
        </div>

        <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
          {latestTickets.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              No maintenance tickets have been raised yet.
            </div>
          ) : latestTickets.map((ticket, index) => (
            <div key={ticket.id} className="px-5 py-4 flex flex-col gap-2 hover:bg-[var(--bg-card-hover)] transition-colors" style={{ animationDelay: `${index * 40}ms` }}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-bold" style={{ color: 'var(--text-primary)' }}>{ticket.compressorId}</span>
                <span className="text-[11px] font-semibold rounded-full px-2 py-0.5" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>{ticket.title}</span>
                <span className="text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-full" style={{ background: ticket.priority === 'critical' ? 'rgba(239,68,68,0.12)' : ticket.priority === 'high' ? 'rgba(251,191,36,0.14)' : 'rgba(34,197,94,0.12)', color: ticket.priority === 'critical' ? '#b91c1c' : ticket.priority === 'high' ? '#b45309' : '#166534' }}>
                  {ticket.priority}
                </span>
                <span className="text-[9px] text-[var(--text-tertiary)]">{new Date(ticket.createdAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
              </div>
              <p className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>{ticket.description}</p>
              <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <span className="flex items-center gap-1"><i className="fa-solid fa-user"></i>{ticket.assignee}</span>
                <span className="flex items-center gap-1"><i className="fa-solid fa-indian-rupee-sign"></i>{ticket.costEstimate.toLocaleString()}</span>
                <span className={`px-2 py-0.5 rounded-full ${ticket.status === 'resolved' ? 'bg-status-ok/10 text-status-ok' : ticket.status === 'open' ? 'bg-accent-blue/10 text-accent-blue' : 'bg-status-warn/10 text-status-warn'}`}>
                  {ticket.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card3D>
    </div>
  )
}
