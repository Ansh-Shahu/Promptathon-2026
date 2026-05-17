const steps = [
  {
    title: "Sensor Data Collection",
    copy: "Edge gateways stream high-frequency vibration, temperature, pressure, and flow data from every asset.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
        <circle cx="12" cy="12" r="2" />
        <path d="M8 12a4 4 0 018-0M5 12a7 7 0 0114 0M2 12a10 10 0 0120 0" />
      </svg>
    ),
  },
  {
    title: "Cloud Analytics & AI Processing",
    copy: "Telemetry is normalized, modeled and benchmarked against millions of HVAC operating hours.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
        <rect x="3" y="4" width="18" height="6" rx="1.5" />
        <rect x="3" y="14" width="18" height="6" rx="1.5" />
        <circle cx="7" cy="7" r="0.8" fill="currentColor" />
        <circle cx="7" cy="17" r="0.8" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "AI Diagnostics & Pattern Recognition",
    copy: "Models identify wear signatures, drift, and anomaly patterns across your fleet in real time.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
        <path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2" />
        <rect x="7" y="7" width="10" height="10" rx="2" />
        <path d="M10 12h4M12 10v4" />
      </svg>
    ),
  },
  {
    title: "Predictive Alerts & Actions",
    copy: "Targeted recommendations land in your team's inbox, mobile, and CMMS — with context to act.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
        <rect x="6" y="2" width="12" height="20" rx="2.5" />
        <path d="M10 18h4" />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative overflow-hidden border-t border-border bg-secondary/40 py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-glow">How it works</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            From Raw Data to Real-Time Action.
          </h2>
        </div>

        <div className="relative mt-16 grid gap-6 lg:grid-cols-4">
          <div className="pointer-events-none absolute left-0 right-0 top-12 hidden h-px lg:block">
            <svg className="h-px w-full" preserveAspectRatio="none" viewBox="0 0 1000 1">
              <line x1="0" y1="0.5" x2="1000" y2="0.5" stroke="currentColor" strokeOpacity="0.25" strokeDasharray="6 6" className="text-primary animate-flow" />
            </svg>
          </div>

          {steps.map((s, i) => (
            <div key={s.title} className="relative rounded-2xl border border-border bg-card p-6 shadow-card transition-all hover:-translate-y-1 hover:shadow-elevated">
              <div className="flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-cta text-primary-foreground shadow-card">
                  {s.icon}
                </div>
                <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Step {i + 1}</span>
              </div>
              <h3 className="mt-5 text-base font-semibold text-foreground">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.copy}</p>

              {i === 3 && (
                <div className="mt-5 rounded-lg border border-accent/30 bg-accent/10 p-3 text-xs shadow-glow-accent">
                  <div className="font-semibold text-foreground">Predictive Alert</div>
                  <div className="text-muted-foreground">Comp-01 Bearing Wear • 14 days</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
