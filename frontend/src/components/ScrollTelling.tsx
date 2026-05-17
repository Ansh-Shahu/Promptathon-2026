import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Activity, Gauge, Zap, ThermometerSun, LogIn } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const STAGES = [
  {
    title: "Chiller",
    left: "A chiller removes heat from a liquid via a vapor-compression cycle. Crucial for large-scale cooling. Damage often occurs from low refrigerant, scaling, or condenser fouling.",
    right: ["Coolant Temperature", "Suction/Discharge Pressure", "Flow Rate", "Energy Consumption"]
  },
  {
    title: "Compressor",
    left: "The heart of the HVAC system, compressing refrigerant gas to raise its temperature and pressure. Vulnerable to liquid slugging, overheating, and electrical issues.",
    right: ["Discharge Temp", "Suction Pressure", "Vibration Analysis", "Power Draw"]
  },
  {
    title: "AHU (Air Handling Unit)",
    left: "Circulates and regulates conditioned air. Contains filters, coils, and blowers. Damage typically stems from clogged filters, belt wear, or fan motor failure.",
    right: ["Airflow Velocity", "Supply/Return Temp", "Filter Differential Pressure", "Fan RPM"]
  },
  {
    title: "Pump",
    left: "Moves water or coolant through the HVAC piping system. Mechanical wear can lead to severe issues like cavitation, seal leaks, or bearing failure over time.",
    right: ["Flow Rate", "Head Pressure", "High-Frequency Vibration", "Motor Current"]
  }
];

const ICONS = [ThermometerSun, Gauge, Activity, Zap];

const FOLDERS = ["chiller_compressor", "compressor_ahu", "ahu_pump"];
const FRAMES_PER_TRANSITION = 192;
const TOTAL_FRAMES = FOLDERS.length * FRAMES_PER_TRANSITION;

export default function ScrollTelling() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const lineRef = useRef<HTMLDivElement>(null);
  const [currentStage, setCurrentStage] = useState(0);

  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const imageCache = useRef<Map<string, HTMLImageElement>>(new Map());
  const currentFrameRef = useRef(0);
  const clickAnimRef = useRef<number | null>(null);
  const isClickAnimating = useRef(false);
  const isLocked = useRef(false);
  const lockedScrollY = useRef<number | null>(null);
  const prevProgress = useRef(0);

  // ─── Image helpers ────────────────────────────────────────────────

  const getImagePath = (transitionIndex: number, frame: number) => {
    const safeTrans = Math.max(0, Math.min(2, transitionIndex));
    const safeFrame = Math.max(1, Math.min(FRAMES_PER_TRANSITION, frame));
    return `/sequences/${FOLDERS[safeTrans]}/${safeFrame.toString().padStart(5, '0')}.png`;
  };

  const getPathForGlobalFrame = (globalFrame: number) => {
    const sf = Math.max(0, Math.min(TOTAL_FRAMES - 1, globalFrame));
    const ti = Math.min(2, Math.floor(sf / FRAMES_PER_TRANSITION));
    const lf = (sf % FRAMES_PER_TRANSITION) + 1;
    return getImagePath(ti, lf);
  };

  const drawImage = useCallback((img: HTMLImageElement) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const { width: cw, height: ch } = canvas;
    const { width: iw, height: ih } = img;
    const scale = Math.min(cw / iw, ch / ih);
    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(img, (cw - iw * scale) / 2, (ch - ih * scale) / 2, iw * scale, ih * scale);
  }, []);

  const loadAndDraw = useCallback((path: string) => {
    if (imageCache.current.has(path)) {
      drawImage(imageCache.current.get(path)!);
      return;
    }
    const img = new Image();
    img.src = path;
    img.onload = () => { imageCache.current.set(path, img); drawImage(img); };
  }, [drawImage]);

  // Update tracking line via DOM ref (no re-render needed)
  const updateLine = useCallback((progress: number) => {
    if (!lineRef.current) return;
    // Line goes from top:12px to bottom:32px of the container.
    // Full track height = 100% - 44px. We want progress fraction of that.
    const pct = progress * 100;
    const px = progress * 44;
    lineRef.current.style.height = `calc(${pct}% - ${px}px)`;
  }, []);

  const renderFrame = useCallback((globalFrame: number) => {
    currentFrameRef.current = globalFrame;
    const p = globalFrame / (TOTAL_FRAMES - 1);
    const stage = Math.min(3, Math.round(p * 3));
    setCurrentStage(stage);
    updateLine(p);
    loadAndDraw(getPathForGlobalFrame(globalFrame));
  }, [loadAndDraw, updateLine]);

  // ─── Preload ──────────────────────────────────────────────────────

  useEffect(() => {
    for (let i = 1; i <= 15; i++) {
      const path = getImagePath(0, i);
      if (!imageCache.current.has(path)) {
        const img = new Image();
        img.src = path;
        img.onload = () => imageCache.current.set(path, img);
      }
    }
  }, []);

  // ─── Prevent scroll during lock (but NOT during navbar nav) ───────

  useEffect(() => {
    const preventScroll = (e: WheelEvent | TouchEvent) => {
      if ((window as any).__navbarNav) return; // let navbar scroll pass through
      if (isLocked.current || isClickAnimating.current) e.preventDefault();
    };
    window.addEventListener('wheel', preventScroll, { passive: false });
    window.addEventListener('touchmove', preventScroll, { passive: false });
    return () => {
      window.removeEventListener('wheel', preventScroll);
      window.removeEventListener('touchmove', preventScroll);
    };
  }, []);

  // ─── Listen for navbar navigation end → snap to nearest stage ─────

  useEffect(() => {
    const onNavEnd = () => {
      if (!containerRef.current) return;
      const { top, height } = containerRef.current.getBoundingClientRect();
      const scrollableHeight = height - window.innerHeight;
      let progress = (-top) / scrollableHeight;
      progress = Math.max(0, Math.min(1, progress));
      // Snap to nearest stage boundary (no animation)
      const nearestStage = Math.round(progress * 3);
      const snapped = nearestStage / 3;
      const globalFrame = Math.round(snapped * (TOTAL_FRAMES - 1));
      renderFrame(globalFrame);
      prevProgress.current = snapped;
    };
    window.addEventListener('navbar-nav-end', onNavEnd);
    return () => window.removeEventListener('navbar-nav-end', onNavEnd);
  }, [renderFrame]);

  // ─── Scroll-driven animation ──────────────────────────────────────

  useEffect(() => {
    const handleScroll = () => {
      if (isClickAnimating.current) return;
      // Skip ALL processing during navbar navigation (no locking, no frame updates)
      if ((window as any).__navbarNav) return;
      if (!containerRef.current) return;

      const { top, height } = containerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const scrollableHeight = height - viewportHeight;
      const containerAbsoluteTop = window.scrollY + top;

      let progress = (-top) / scrollableHeight;
      progress = Math.max(0, Math.min(1, progress));

      // Milestone snap
      if (isLocked.current && lockedScrollY.current !== null) {
        window.scrollTo({ top: lockedScrollY.current, behavior: 'auto' });
        return;
      }

      const milestones = [1 / 3, 2 / 3, 1];
      for (const m of milestones) {
        if (
          (prevProgress.current < m && progress >= m) ||
          (prevProgress.current > m && progress <= m)
        ) {
          isLocked.current = true;
          const snapScroll = containerAbsoluteTop + m * scrollableHeight;
          lockedScrollY.current = snapScroll;
          window.scrollTo({ top: snapScroll, behavior: 'auto' });
          setTimeout(() => { isLocked.current = false; lockedScrollY.current = null; }, 500);
          break;
        }
      }

      prevProgress.current = progress;
      const globalFrame = Math.floor(progress * (TOTAL_FRAMES - 1));
      renderFrame(globalFrame);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    const handleResize = () => {
      if (canvasRef.current) {
        const rect = canvasRef.current.parentElement?.getBoundingClientRect();
        if (rect) {
          canvasRef.current.width = rect.width;
          canvasRef.current.height = rect.height;
          handleScroll();
        }
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
  }, [renderFrame]);

  // ─── Click-driven animation (dots) ────────────────────────────────

  const handleDotClick = useCallback((targetStageIndex: number) => {
    if (clickAnimRef.current !== null) {
      cancelAnimationFrame(clickAnimRef.current);
      clickAnimRef.current = null;
    }

    const targetFrame = Math.round((targetStageIndex / 3) * (TOTAL_FRAMES - 1));
    const startFrame = currentFrameRef.current;
    if (startFrame === targetFrame) return;

    isClickAnimating.current = true;
    isLocked.current = false;

    const DURATION = 3500;
    const startTime = performance.now();
    const easeInOut = (t: number) => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

    const animate = (now: number) => {
      const t = Math.min((now - startTime) / DURATION, 1);
      renderFrame(Math.round(startFrame + (targetFrame - startFrame) * easeInOut(t)));

      if (t < 1) {
        clickAnimRef.current = requestAnimationFrame(animate);
      } else {
        clickAnimRef.current = null;
        if (containerRef.current) {
          const { top, height } = containerRef.current.getBoundingClientRect();
          const scrollableHeight = height - window.innerHeight;
          const targetScroll = window.scrollY + top + (targetStageIndex / 3) * scrollableHeight;
          window.scrollTo({ top: targetScroll, behavior: 'auto' });
          prevProgress.current = targetStageIndex / 3;
        }
        setTimeout(() => { isClickAnimating.current = false; }, 300);
      }
    };

    clickAnimRef.current = requestAnimationFrame(animate);
  }, [renderFrame]);

  // ─── JSX ──────────────────────────────────────────────────────────

  return (
    <section id="components" ref={containerRef} className="relative bg-white" style={{ height: '300vh' }}>
      <div className="sticky top-16 h-[calc(100vh-64px)] w-full flex items-center justify-center overflow-hidden">

        {/* Background Ambient Glow */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[80%] h-[80%] bg-primary/5 rounded-full blur-[150px]" />
        </div>

        {/* Headline */}
        <div className="absolute top-10 left-1/2 -translate-x-1/2 z-30 pointer-events-none text-center w-full">
          <h2 className="text-2xl md:text-3xl font-extrabold uppercase tracking-widest text-[#020617]">
            Component Selection
          </h2>
        </div>

        {/* Left Text */}
        <div className="absolute inset-0 z-10 flex items-center pointer-events-none px-6 md:px-12 lg:px-20">
          {STAGES.map((stage, i) => (
            <div
              key={i}
              className={`transition-all duration-700 absolute top-1/2 -translate-y-1/2 left-6 md:left-12 lg:left-20 w-[280px] lg:w-[320px] ${
                currentStage === i ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'
              }`}
            >
              <h3 className="text-4xl lg:text-5xl font-extrabold italic text-[#020617] mb-4 tracking-tight leading-none">
                <span className="text-primary block text-sm font-bold tracking-widest uppercase mb-2 not-italic">Component</span>
                {stage.title}
              </h3>
              <p className="text-slate-600 text-sm leading-relaxed border-l-2 border-primary pl-4 font-medium">
                {stage.left}
              </p>
            </div>
          ))}
        </div>

        {/* Right Timeline Nav */}
        <div
          className="absolute right-6 md:right-12 lg:right-20 top-1/2 -translate-y-1/2 z-[50]"
          style={{ pointerEvents: 'auto' }}
        >
          <div className="relative flex flex-col items-center" style={{ gap: '64px' }}>

            {/* Background grey line */}
            <div className="absolute left-1/2 -translate-x-1/2 top-[12px] bottom-[32px] w-[2px] bg-slate-300" style={{ zIndex: -1 }} />

            {/* Active orange line — continuous progress via ref */}
            <div
              ref={lineRef}
              className="absolute left-1/2 -translate-x-1/2 top-[12px] w-[2px] bg-[#f97316]"
              style={{ height: '0px', zIndex: -1, transition: 'height 0.15s ease-out' }}
            />

            {STAGES.map((stage, i) => {
              const isActive = currentStage === i;
              const isPassed = currentStage > i;
              const shortTitle = stage.title.includes('AHU') ? 'AHU' : stage.title;

              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleDotClick(i)}
                  title={`Navigate to ${stage.title}`}
                  style={{
                    pointerEvents: 'auto',
                    cursor: 'pointer',
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '16px',
                    margin: '-16px',
                    position: 'relative',
                    zIndex: 100,
                  }}
                  aria-label={`Go to ${stage.title}`}
                >
                  <div style={{
                    width: '24px', height: '24px', borderRadius: '50%',
                    border: `2px solid ${isActive || isPassed ? '#f97316' : '#cbd5e1'}`,
                    background: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: isActive ? '0 0 16px rgba(249,115,22,0.8)' : 'none',
                    transition: 'all 0.3s ease', flexShrink: 0,
                  }}>
                    <div style={{
                      width: isActive ? '12px' : '8px', height: isActive ? '12px' : '8px',
                      borderRadius: '50%', background: isActive || isPassed ? '#f97316' : '#e2e8f0',
                      transition: 'all 0.3s ease',
                    }} />
                  </div>
                  <span style={{
                    fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
                    letterSpacing: '0.1em', color: isActive ? '#f97316' : '#1e293b',
                    whiteSpace: 'nowrap', transition: 'color 0.3s ease',
                    pointerEvents: 'none', userSelect: 'none',
                  }}>
                    {shortTitle}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Center Canvas */}
        <div className="relative z-0 w-full md:w-[75%] lg:w-[65%] h-full flex items-center justify-center pointer-events-none">
          <canvas ref={canvasRef} className="w-full h-[80vh] object-contain" />
        </div>

        {/* Access Dashboard Button */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20">
          <button
            onClick={() => {
              if (isAuthenticated && user?.role === 'admin') navigate('/dashboard');
              else navigate('/login');
            }}
            className="inline-flex h-12 items-center justify-center gap-3 rounded-full bg-gradient-cta px-8 text-sm font-semibold text-primary-foreground shadow-elevated-lp transition-all hover:brightness-110 hover:scale-105"
          >
            {isAuthenticated && user?.role === 'admin' ? (
              <><Activity className="h-5 w-5" /> Enter Predictive Dashboard</>
            ) : (
              <><LogIn className="h-5 w-5" /> Login to Access Dashboard</>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
