export function CTA() {
  return (
    <section id="contact" className="relative overflow-hidden bg-gradient-navy py-24 text-primary-foreground">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,oklch(0.78_0.2_145/0.18),transparent_50%),radial-gradient(circle_at_80%_80%,oklch(0.55_0.15_255/0.25),transparent_55%)]" />
      <div className="relative mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-glow">Get Started</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
            Ready to Future-Proof Your HVAC Infrastructure?
          </h2>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-primary-foreground/75">
            Request a custom platform demo and system audit for your facility. Our solutions team will be in touch within one business day.
          </p>
          <ul className="mt-8 space-y-3 text-sm">
            {["Free 30-day pilot deployment", "Dedicated solutions engineer", "Integration with your existing CMMS"].map((b) => (
              <li key={b} className="flex items-center gap-3 text-primary-foreground/85">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-accent text-accent-foreground">
                  <svg viewBox="0 0 20 20" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 10l3.5 3.5L15 7"/></svg>
                </span>
                {b}
              </li>
            ))}
          </ul>
        </div>

        <form
          onSubmit={(e) => e.preventDefault()}
          className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-elevated backdrop-blur-sm sm:p-8"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full Name" name="name" />
            <Field label="Company" name="company" />
            <Field label="Work Email" name="email" type="email" />
            <Field label="Phone" name="phone" type="tel" />
          </div>
          <label className="mt-4 block">
            <span className="text-xs font-medium text-primary-foreground/75">Tell us about your facility</span>
            <textarea name="message" rows={4} className="mt-1.5 w-full resize-none rounded-md border border-white/15 bg-white/5 px-3.5 py-2.5 text-sm text-primary-foreground placeholder:text-primary-foreground/40 focus:border-accent focus:outline-none" placeholder="Square footage, equipment count, current pain points…" />
          </label>
          <button type="submit" className="mt-5 inline-flex h-12 w-full items-center justify-center rounded-md bg-gradient-cta text-sm font-semibold text-primary-foreground shadow-elevated transition-all hover:brightness-110">
            Send Request
          </button>
          <p className="mt-3 text-center text-xs text-primary-foreground/50">We respond within 1 business day.</p>
        </form>
      </div>
    </section>
  );
}

function Field({ label, name, type = "text" }: { label: string; name: string; type?: string }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-primary-foreground/75">{label}</span>
      <input
        name={name}
        type={type}
        className="mt-1.5 w-full rounded-md border border-white/15 bg-white/5 px-3.5 py-2.5 text-sm text-primary-foreground placeholder:text-primary-foreground/40 focus:border-accent focus:outline-none"
      />
    </label>
  );
}
