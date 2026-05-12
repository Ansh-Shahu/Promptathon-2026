import React from 'react'
import { useTheme } from '../context/ThemeContext'

interface TopBarProps {
  lastRefresh: Date
  countdown: number
  onManualRefresh: () => void
  searchQuery: string
  onSearchChange: (q: string) => void
  alertCount: number
}

export default function TopBar({
  lastRefresh,
  countdown,
  onManualRefresh,
  searchQuery,
  onSearchChange,
  alertCount,
}: TopBarProps) {
  const { theme, toggleTheme, isDark } = useTheme()
  const [liveTime, setLiveTime] = React.useState(new Date())

  React.useEffect(() => {
    const timer = setInterval(() => setLiveTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header
      className="flex items-center justify-between px-6 py-3 border-b backdrop-blur-md transition-colors duration-300"
      style={{
        background: isDark ? 'rgba(26,28,35,0.8)' : 'rgba(255,253,245,0.85)',
        borderColor: 'var(--border-default)',
      }}
    >
      {/* Left — Live indicator & refresh */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full rounded-full bg-status-ok opacity-75 animate-ping" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-status-ok" />
          </span>
          <span className="font-medium">Live Monitoring</span>
        </div>

        <div className="hidden md:flex items-center gap-2 text-[11px] px-3 py-1 rounded-full" style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>
          <i className={`fa-solid fa-arrows-rotate text-[10px] ${countdown <= 5 ? 'animate-spin text-primary-400' : ''}`}></i>
          <span>Refresh in <strong className="text-primary-400">{countdown}s</strong></span>
        </div>

        {/* Live Date and Time */}
        <div className="hidden lg:flex items-center gap-2 text-[11px] font-bold px-3 py-1 rounded-full border" 
          style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }}>
          <i className="fa-regular fa-clock text-accent-blue"></i>
          {liveTime.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>
      </div>

      {/* Center — Search */}
      <div className="hidden md:flex items-center gap-2 px-4 py-2 rounded-xl max-w-sm w-full mx-6 rich-hover"
        style={{
          background: 'var(--bg-input)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        <i className="fa-solid fa-magnifying-glass text-xs" style={{ color: 'var(--text-muted)' }}></i>
        <input
          type="text"
          placeholder="Search compressors, alerts..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]"
          style={{ color: 'var(--text-primary)' }}
        />
        <kbd className="hidden lg:inline text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'var(--bg-card)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
          ⌘K
        </kbd>
      </div>

      {/* Right — Actions */}
      <div className="flex items-center gap-3">
        {/* Manual refresh */}
        <button
          onClick={onManualRefresh}
          className="p-2 w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-200 cursor-pointer rich-hover"
          style={{ color: 'var(--text-secondary)' }}
          title="Refresh now"
        >
          <i className="fa-solid fa-arrows-rotate text-sm"></i>
        </button>

        {/* Alert bell */}
        <button className="relative p-2 w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-200 cursor-pointer rich-hover" style={{ color: 'var(--text-secondary)' }}>
          <i className="fa-solid fa-bell text-sm"></i>
          {alertCount > 0 && (
            <span className="absolute top-0 right-0 flex items-center justify-center w-4 h-4 text-[9px] font-bold text-white bg-status-critical rounded-full shadow-lg shadow-status-critical/30">
              {alertCount}
            </span>
          )}
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-200 cursor-pointer rich-hover"
          style={{ color: 'var(--text-secondary)' }}
          title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
        >
          {isDark ? <i className="fa-solid fa-sun text-sm"></i> : <i className="fa-solid fa-moon text-sm"></i>}
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border cursor-pointer transition-all rich-hover"
          style={{ borderColor: 'var(--border-default)' }}
        >
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-purple to-accent-rose flex items-center justify-center">
            <i className="fa-solid fa-user text-xs text-white"></i>
          </div>
          <div className="hidden lg:block text-left">
            <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>Neural Ninjas</p>
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Admin</p>
          </div>
        </div>
      </div>
    </header>
  )
}
