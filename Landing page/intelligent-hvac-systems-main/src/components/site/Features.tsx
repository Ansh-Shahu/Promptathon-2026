import ahu from "@/assets/comp-ahu.jpg";
import chiller from "@/assets/comp-chiller.jpg";
import pump from "@/assets/comp-pump.jpg";
import compressor from "@/assets/comp-compressor.jpg";

const items = [
  { img: ahu, title: "Smart Air Handling", tag: "AHU", copy: "Optimized airflow, coil health tracking, and fan speed prediction to ensure air quality and comfort without waste." },
  { img: chiller, title: "Precision Chillers", tag: "Chiller", copy: "COP maximization, refrigerant level monitoring, and tube scaling prediction to maintain peak performance." },
  { img: pump, title: "Hydronic Efficiency", tag: "Pump", copy: "Vibration monitoring, seal failure prediction, and variable speed pump optimization to keep water moving reliably." },
  { img: compressor, title: "Compression Integrity", tag: "Compressor", copy: "Real-time valve and seal health diagnostics for scroll/screw compressors, predicting failures before they occur." },
];

export function Features() {
  return (
    <section id="features" className="border-t border-border bg-background py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-glow">Component Intelligence</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Deep Component Insights. Total System Visibility.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Every asset on your plant floor, instrumented and understood — so you can act before things break.
          </p>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((it) => (
            <article key={it.tag} className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-card transition-all hover:-translate-y-1 hover:shadow-elevated">
              <div className="relative aspect-square overflow-hidden bg-secondary">
                <img src={it.img} alt={it.title} loading="lazy" width={800} height={800} className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105" />
                <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-md bg-card/95 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-foreground shadow-card backdrop-blur">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-glow" /> {it.tag}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-2 p-6">
                <h3 className="text-lg font-semibold text-foreground">{it.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{it.copy}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
