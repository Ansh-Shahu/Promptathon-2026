export function Footer() {
  const cols = [
    { h: "Product", links: ["Features", "Solutions", "Pricing", "Integrations"] },
    { h: "Company", links: ["About", "Careers", "Press", "Contact"] },
    { h: "Resources", links: ["Blog", "Case Studies", "Documentation", "Support"] },
  ];
  return (
    <footer className="border-t border-border bg-background py-16">
      <div className="mx-auto grid max-w-7xl gap-10 px-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-cta text-primary-foreground shadow-card">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 8h6a3 3 0 013 3v6"/><path d="M20 16h-6a3 3 0 01-3-3V7"/></svg>
            </span>
            <span className="text-[15px] font-bold tracking-tight">HVAC-IQ <span className="font-medium text-muted-foreground">Solutions</span></span>
          </div>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-muted-foreground">
            Predictive intelligence for industrial HVAC systems. Built by mechanical engineers and data scientists.
          </p>
          <div className="mt-5 flex gap-3 text-muted-foreground">
            {["in", "x", "yt"].map((s) => (
              <a key={s} href="#" className="grid h-9 w-9 place-items-center rounded-md border border-border transition-colors hover:border-primary/40 hover:text-foreground">
                <span className="text-xs font-bold uppercase">{s}</span>
              </a>
            ))}
          </div>
        </div>
        {cols.map((c) => (
          <div key={c.h}>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-foreground">{c.h}</h4>
            <ul className="mt-4 space-y-2.5">
              {c.links.map((l) => (
                <li key={l}><a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">{l}</a></li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mx-auto mt-12 flex max-w-7xl flex-col items-center justify-between gap-3 border-t border-border px-6 pt-6 text-xs text-muted-foreground sm:flex-row">
        <p>© {new Date().getFullYear()} HVAC-IQ Solutions. All rights reserved.</p>
        <p>hello@hvac-iq.com • +1 (415) 555-0142</p>
      </div>
    </footer>
  );
}
