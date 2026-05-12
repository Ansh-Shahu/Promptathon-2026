import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  Activity, 
  Cpu, 
  ShieldCheck, 
  Zap, 
  ArrowRight, 
  Radio, 
  Cloud, 
  BrainCircuit, 
  Bell,
  LayoutDashboard,
  LogIn,
  User as UserIcon,
  LogOut
} from 'lucide-react';
import logo from '../assets/carrier-logo.png';
import ahu from '../assets/comp-ahu.jpg';
import chiller from '../assets/comp-chiller.jpg';
import pump from '../assets/comp-pump.jpg';
import compressor from '../assets/comp-compressor.jpg';
import ScrollTelling from './ScrollTelling';

// --- Sub-components (Header, Hero, etc.) consolidated for simplicity ---

function Header() {
  const navigate = useNavigate();
  const { user, logout, isAuthenticated } = useAuth();
  const nav = ["Vision", "Components", "Solutions", "Performance"];
  const [activeSection, setActiveSection] = React.useState("");

  React.useEffect(() => {
    const handleScroll = () => {
      const sections = nav.map(n => n.toLowerCase());
      let current = "";
      for (const section of sections) {
        const element = document.getElementById(section);
        if (element) {
          const rect = element.getBoundingClientRect();
          // Adjust threshold for what is considered "active"
          if (rect.top <= 200 && rect.bottom >= 200) {
            current = section;
          }
        }
      }
      setActiveSection(current);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [nav]);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-[#020617]/95 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <img src={logo} alt="Carrier" className="h-7 w-auto" />
          <span className="text-[15px] font-bold tracking-tight text-white">
            Carrier <span className="text-primary">Ai</span>
          </span>
        </div>
        <nav className="hidden items-center gap-8 md:flex">
          {nav.map((n) => {
            const isActive = activeSection === n.toLowerCase();
            return (
              <a
                key={n}
                href={`#${n.toLowerCase()}`}
                onClick={(e) => {
                  e.preventDefault();
                  (window as any).isNavigating = true;
                  setTimeout(() => { (window as any).isNavigating = false; }, 1500);
                  document.getElementById(n.toLowerCase())?.scrollIntoView({ behavior: 'smooth' });
                }}
                className={`text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${isActive ? 'text-orange-500' : 'text-white hover:text-white/80'}`}
              >
                {n}
              </a>
            );
          })}
        </nav>
        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 h-9 rounded-full bg-slate-50/10 border border-slate-200/20">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center">
                  <UserIcon className="h-3 w-3 text-primary" />
                </div>
                <span className="text-[11px] font-bold text-white uppercase tracking-wider">{user?.name}</span>
              </div>
              <button
                onClick={logout}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/20 bg-transparent text-white transition-colors hover:text-red-500 hover:border-red-500/30"
                title="Logout"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="hidden h-9 items-center justify-center gap-2 rounded-full border border-white/20 bg-transparent px-4 text-xs font-semibold uppercase tracking-wider text-white transition-colors hover:border-white/50 sm:inline-flex"
            >
              <LogIn className="h-3.5 w-3.5" />
              Log in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

function Hero() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const stats = [
    { value: "99.9%", label: "Uptime" },
    { value: "24/7", label: "Active Monitoring" },
    { value: "15ms", label: "Latency" },
    { value: "40%", label: "Downtime Reduction" },
  ];

  return (
    <section id="vision" className="relative overflow-hidden bg-[#020617] text-white">
      {/* Background video - clearer view */}
      <video
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 h-full w-full object-cover opacity-100"
      >
        <source src="/hero-loop.mp4" type="video/mp4" />
      </video>
      
      {/* Dark Blue Half Gradient Overlay (Solid to 0 opacity) */}
      <div className="absolute inset-0 bg-gradient-to-r from-[#020617]/90 via-[#020617]/60 to-transparent" />
      
      {/* Bottom fade */}
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-[#020617]/80 to-transparent" />

      <div className="relative mx-auto max-w-7xl px-6 pt-24 pb-10 lg:pt-32 lg:pb-14">
        <div className="mr-auto max-w-2xl animate-fade-up text-left">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-white/80">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse-glow" />
            Carrier Systems Engineering
          </span>
          <h1 className="mt-5 text-balance text-5xl font-extrabold italic leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl drop-shadow-2xl">
            <span className="block">PREDICTIVE</span>
            <span className="block text-primary">INTELLIGENCE</span>
            <span className="block">FOR HVAC</span>
          </h1>
          <p className="mr-auto mt-6 max-w-md text-pretty text-base leading-relaxed text-white/90">
            Carrier&apos;s next-generation platform for autonomous maintenance and efficiency optimization across chillers, AHUs, pumps, and compressors.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-start gap-3">
            <button
              onClick={() => navigate(isAuthenticated ? '/dashboard' : '/login')}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-gradient-cta px-7 text-sm font-bold uppercase tracking-wider text-primary-foreground shadow-elevated-lp transition-all hover:-translate-y-0.5 hover:brightness-110"
            >
              {isAuthenticated ? 'Go to Dashboard' : 'Get Started'}
              <ArrowRight className="h-4 w-4" />
            </button>
            {!isAuthenticated && (
              <button
                onClick={() => navigate('/login')}
                className="inline-flex h-12 items-center justify-center rounded-full border border-white/30 bg-white/5 px-7 text-sm font-bold uppercase tracking-wider text-white backdrop-blur transition-all hover:border-white/60"
              >
                Sign In
              </button>
            )}
          </div>
        </div>

        <div className="relative mt-16 border-t border-white/15 pt-6 lg:mt-24">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            {stats.map((s, i) => (
              <div
                key={s.label}
                className="animate-fade-up"
                style={{ animationDelay: `${200 + i * 80}ms` }}
              >
                <div className="text-2xl font-extrabold italic text-white sm:text-3xl">
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

function Features() {
  const items = [
    { img: ahu, title: "Smart Air Handling", tag: "AHU", copy: "Optimized airflow, coil health tracking, and fan speed prediction to ensure air quality and comfort without waste." },
    { img: chiller, title: "Precision Chillers", tag: "Chiller", copy: "COP maximization, refrigerant level monitoring, and tube scaling prediction to maintain peak performance." },
    { img: pump, title: "Hydronic Efficiency", tag: "Pump", copy: "Vibration monitoring, seal failure prediction, and variable speed pump optimization to keep water moving reliably." },
    { img: compressor, title: "Compression Integrity", tag: "Compressor", copy: "Real-time valve and seal health diagnostics for scroll/screw compressors, predicting failures before they occur." },
  ];

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
            <article key={it.tag} className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-card-lp transition-all hover:-translate-y-1 hover:shadow-elevated-lp">
              <div className="relative aspect-square overflow-hidden bg-secondary">
                <img src={it.img} alt={it.title} loading="lazy" className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105" />
                <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-md bg-card/95 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-foreground shadow-card-lp backdrop-blur">
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

function HowItWorks() {
  const steps = [
    { title: "Sensor Data Collection", copy: "Edge gateways stream data from every asset.", icon: <Radio className="h-6 w-6" /> },
    { title: "Cloud Analytics", copy: "Telemetry is normalized and benchmarked.", icon: <Cloud className="h-6 w-6" /> },
    { title: "AI Diagnostics", copy: "Models identify wear and anomaly patterns.", icon: <BrainCircuit className="h-6 w-6" /> },
    { title: "Predictive Alerts", copy: "Recommendations land in your team's inbox.", icon: <Bell className="h-6 w-6" /> },
  ];

  return (
    <section id="solutions" className="relative overflow-hidden border-t border-border bg-secondary/40 py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-glow">How it works</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            From Raw Data to Real-Time Action.
          </h2>
        </div>

        <div className="relative mt-16 grid gap-6 lg:grid-cols-4">
          {steps.map((s, i) => (
            <div key={s.title} className="relative rounded-2xl border border-border bg-card p-6 shadow-card-lp transition-all hover:-translate-y-1 hover:shadow-elevated-lp">
              <div className="flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-cta text-primary-foreground shadow-card-lp">
                  {s.icon}
                </div>
                <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Step {i + 1}</span>
              </div>
              <h3 className="mt-5 text-base font-semibold text-foreground">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.copy}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTA() {
  const navigate = useNavigate();
  return (
    <section id="performance" className="relative overflow-hidden bg-gradient-navy py-24 text-primary-foreground">
      <div className="relative mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-glow">Get Started</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl text-orange-500">
            Ready to Future-Proof Your HVAC Infrastructure?
          </h2>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-primary-foreground/75">
            Access the AI-powered command center to monitor chillers, AHUs, pumps, and compressors.
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-elevated-lp backdrop-blur-sm sm:p-8">
          <button 
            onClick={() => navigate('/dashboard')}
            className="inline-flex h-12 w-full items-center justify-center gap-3 rounded-md bg-gradient-cta text-sm font-semibold text-primary-foreground shadow-elevated-lp transition-all hover:brightness-110"
          >
            <Activity className="h-5 w-5" />
            Access AI Command Center
          </button>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border bg-background py-12">
      <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-2.5">
          <img src={logo} alt="Carrier" className="h-6 w-auto" />
          <span className="text-sm font-bold tracking-tight text-foreground">
            Carrier <span className="text-primary">Ai</span>
          </span>
        </div>
        <p className="text-xs text-muted-foreground">© 2024 Carrier Systems Engineering. All rights reserved.</p>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background font-sans selection:bg-primary/30 selection:text-foreground">
      <Header />
      <main>
        <Hero />
        <ScrollTelling />
        <Features />
        <HowItWorks />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
