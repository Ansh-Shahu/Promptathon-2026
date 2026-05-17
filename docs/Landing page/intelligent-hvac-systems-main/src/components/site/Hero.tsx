const stats = [
  { value: "99.9%", label: "Uptime" },
  { value: "24/7", label: "Active Monitoring" },
  { value: "15ms", label: "Latency" },
  { value: "40%", label: "Downtime Reduction" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-foreground text-background">
      {/* Background video */}
      <video
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        className="absolute inset-0 h-full w-full object-cover"
      >
        <source src="/hero-loop.mp4" type="video/mp4" />
      </video>
      {/* Overlays for legibility — strong tinted wash on left, fully clear on right */}
      <div className="absolute inset-y-0 left-0 w-1/2 bg-gradient-to-r from-foreground/95 via-foreground/80 to-transparent" />
      <div className="absolute inset-y-0 left-0 w-1/2 bg-gradient-to-br from-primary/25 via-primary/10 to-transparent mix-blend-overlay" />
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-foreground/60 to-transparent" />

      <div className="relative mx-auto max-w-7xl px-6 pt-24 pb-10 lg:pt-32 lg:pb-14">
        <div className="mr-auto max-w-2xl animate-fade-up text-left">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-background/80">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse-glow" />
            Carrier Systems Engineering
          </span>
          <h1 className="mt-5 text-balance text-5xl font-extrabold italic leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
            <span className="block">PREDICTIVE</span>
            <span className="block text-primary">INTELLIGENCE</span>
            <span className="block">FOR HVAC</span>
          </h1>
          <p className="mr-auto mt-6 max-w-md text-pretty text-base leading-relaxed text-background/75">
            Carrier&apos;s next-generation platform for autonomous maintenance and efficiency optimization across chillers, AHUs, pumps, and compressors.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-start gap-3">
            <a
              href="#solutions"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-gradient-cta px-7 text-sm font-bold uppercase tracking-wider text-primary-foreground shadow-elevated transition-all hover:-translate-y-0.5 hover:brightness-110"
            >
              Solutions
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </a>
            <a
              href="#demo"
              className="inline-flex h-12 items-center justify-center rounded-full border border-background/30 bg-background/5 px-7 text-sm font-bold uppercase tracking-wider text-background backdrop-blur transition-all hover:border-background/60"
            >
              Demo
            </a>
          </div>
        </div>

        {/* Stats bar */}
        <div className="relative mt-16 border-t border-background/15 pt-6 lg:mt-24">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            {stats.map((s, i) => (
              <div
                key={s.label}
                className="animate-fade-up"
                style={{ animationDelay: `${200 + i * 80}ms` }}
              >
                <div className="text-2xl font-extrabold italic text-background sm:text-3xl">
                  {s.value}
                </div>
                <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-primary">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
