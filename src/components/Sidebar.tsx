import React, { useState } from 'react'
import carrierLogo from '../assets/carrier-logo.svg'

export type NavPage = 'dashboard' | 'fleet' | 'analytics' | 'alerts' | 'maintenance' | 'digital-twin' | 'reports' | 'settings'

interface SidebarProps {
  activePage: NavPage
  onNavigate: (page: NavPage) => void
  alertCount: number
}

const navItems: { id: NavPage; label: string; iconClass: string }[] = [
  { id: 'dashboard', label: 'Dashboard', iconClass: 'fa-solid fa-table-columns' },
  { id: 'fleet', label: 'Fleet Status', iconClass: 'fa-solid fa-server' },
  { id: 'analytics', label: 'Analytics', iconClass: 'fa-solid fa-chart-line' },
  { id: 'alerts', label: 'Alerts', iconClass: 'fa-solid fa-bell' },
  { id: 'maintenance', label: 'Maintenance', iconClass: 'fa-solid fa-calendar-check' },
  { id: 'digital-twin', label: 'Digital Twin', iconClass: 'fa-solid fa-cube' },
  { id: 'reports', label: 'Reports', iconClass: 'fa-solid fa-file-invoice' },
  { id: 'settings', label: 'Settings', iconClass: 'fa-solid fa-gear' },
]

export default function Sidebar({ activePage, onNavigate, alertCount }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={`glass-sidebar flex flex-col h-full transition-all duration-300 ease-in-out ${
        collapsed ? 'w-[72px]' : 'w-[240px]'
      }`}
      style={{ minHeight: '100vh' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center justify-center w-10 h-10 rounded-xl overflow-hidden flex-shrink-0" style={{ background: '#fff' }}>
          <img src={carrierLogo} alt="Carrier" className="w-9 h-9 object-contain" />
        </div>
        {!collapsed && (
          <div className="animate-fade-in overflow-hidden">
            <h1 className="text-sm font-bold tracking-tight whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>
              Carrier AI
            </h1>
            <p className="text-[10px] tracking-wide uppercase whitespace-nowrap" style={{ color: 'var(--text-tertiary)' }}>
              Command Center
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map(item => {
          const isActive = activePage === item.id
          const showBadge = item.id === 'alerts' && alertCount > 0

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                transition-all duration-200 cursor-pointer relative group
                ${isActive
                  ? 'bg-primary-400/15 text-primary-400 shadow-[inset_0_0_12px_rgba(45,212,191,0.05)]'
                  : 'hover:bg-[var(--bg-card-hover)]'
                }
              `}
              style={{
                color: isActive ? undefined : 'var(--text-secondary)',
              }}
            >
              <span className={`flex-shrink-0 w-5 flex justify-center ${isActive ? 'text-primary-400' : ''}`}>
                <i className={`${item.iconClass} text-[18px]`}></i>
              </span>
              {!collapsed && (
                <span className="whitespace-nowrap animate-fade-in">{item.label}</span>
              )}
              {showBadge && (
                <span className={`
                  flex items-center justify-center text-[10px] font-bold text-white bg-status-critical rounded-full
                  ${collapsed ? 'absolute -top-0.5 -right-0.5 w-4 h-4' : 'ml-auto w-5 h-5 shadow-lg shadow-status-critical/20'}
                `}>
                  {alertCount}
                </span>
              )}
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-primary-400 shadow-[0_0_8px_rgba(45,212,191,0.6)]" />
              )}
            </button>
          )
        })}
      </nav>

      {/* System health */}
      {!collapsed && (
        <div className="mx-3 mb-3 flex flex-col gap-2 animate-fade-in">
          {/* Component Selector */}
          <select 
            className="w-full bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[11px] font-semibold text-[var(--text-primary)] rounded-lg px-2 py-2 outline-none cursor-pointer hover:border-[var(--border-default)] transition-colors"
          >
            <option>All Systems</option>
            <option>Chiller Units</option>
            <option>Compressors</option>
            <option>AHUs</option>
            <option>Pumps</option>
          </select>
          
          <div className="px-4 py-3 rounded-xl" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center gap-2 mb-2">
              <i className="fa-solid fa-shield-halved text-status-ok text-xs"></i>
              <span className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>Overall System Health</span>
            </div>
            <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-input)' }}>
              <div className="h-full rounded-full bg-gradient-to-r from-primary-400 to-status-ok" style={{ width: '92%' }} />
            </div>
            <p className="text-[10px] mt-1.5" style={{ color: 'var(--text-muted)' }}>92% — All systems nominal</p>
          </div>
        </div>
      )}

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className="flex items-center justify-center py-3 border-t cursor-pointer transition-colors hover:bg-[var(--bg-card-hover)]"
        style={{ borderColor: 'var(--border-default)', color: 'var(--text-tertiary)' }}
      >
        <i className={`fa-solid ${collapsed ? 'fa-chevron-right' : 'fa-chevron-left'} text-xs`}></i>
      </button>
    </aside>
  )
}
