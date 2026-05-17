const logos = ["Tishman Speyer", "Cushman & Wakefield", "Hilton", "Marriott", "Equinix", "Brookfield"];

export function SocialProof() {
  return (
    <section id="case-studies" className="border-t border-border bg-background py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-glow">Trust</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Trusted by Industry Leaders.</h2>
        </div>

        <div className="mt-12 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
          {logos.map((l) => (
            <div key={l} className="flex h-24 items-center justify-center bg-card px-4 text-center text-sm font-semibold tracking-tight text-muted-foreground transition-colors hover:text-foreground">
              {l}
            </div>
          ))}
        </div>

        <figure className="mx-auto mt-14 max-w-3xl rounded-2xl border border-border bg-card p-8 shadow-card sm:p-10">
          <svg viewBox="0 0 24 24" className="h-8 w-8 text-primary-glow" fill="currentColor"><path d="M9 7H5a2 2 0 00-2 2v4a2 2 0 002 2h2v2a4 4 0 01-4 4v2a6 6 0 006-6V9a2 2 0 00-2-2zm12 0h-4a2 2 0 00-2 2v4a2 2 0 002 2h2v2a4 4 0 01-4 4v2a6 6 0 006-6V9a2 2 0 00-2-2z"/></svg>
          <blockquote className="mt-4 text-pretty text-lg leading-relaxed text-foreground sm:text-xl">
            HVAC-IQ reduced our cooling energy consumption by 18% in the first quarter and predicted three major pump failures before they shut down our facility. The ROI is undeniable.
          </blockquote>
          <figcaption className="mt-6 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-full bg-gradient-cta text-sm font-semibold text-primary-foreground">DR</div>
            <div>
              <div className="text-sm font-semibold text-foreground">Daniel Reyes</div>
              <div className="text-xs text-muted-foreground">VP Facilities, Atlas Commercial Properties</div>
            </div>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
