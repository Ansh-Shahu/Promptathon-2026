import React, { useEffect, useRef, useState } from 'react';
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

export default function ScrollTelling() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [currentStage, setCurrentStage] = useState(0);
  
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const imageCache = useRef<Map<string, HTMLImageElement>>(new Map());

  const getImagePath = (transitionIndex: number, frame: number) => {
    const safeTrans = Math.max(0, Math.min(2, transitionIndex));
    const safeFrame = Math.max(1, Math.min(FRAMES_PER_TRANSITION, frame));
    const folder = FOLDERS[safeTrans];
    const paddedFrame = safeFrame.toString().padStart(5, '0');
    return `/sequences/${folder}/${paddedFrame}.png`;
  };

  const drawImage = (img: HTMLImageElement) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width: canvasWidth, height: canvasHeight } = canvas;
    const { width: imgWidth, height: imgHeight } = img;

    const scale = Math.min(canvasWidth / imgWidth, canvasHeight / imgHeight);
    const x = (canvasWidth / 2) - (imgWidth / 2) * scale;
    const y = (canvasHeight / 2) - (imgHeight / 2) * scale;

    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    ctx.drawImage(img, x, y, imgWidth * scale, imgHeight * scale);
  };

  const loadImageAndDraw = (path: string) => {
    if (imageCache.current.has(path)) {
      drawImage(imageCache.current.get(path)!);
      return;
    }
    const img = new Image();
    img.src = path;
    img.onload = () => {
      imageCache.current.set(path, img);
      drawImage(img);
    };
  };

  const prevProgress = useRef(0);
  const isLocked = useRef(false);
  const lockedProgress = useRef<number | null>(null);

  useEffect(() => {
    const preventScroll = (e: WheelEvent | TouchEvent) => {
      if (isLocked.current) {
        e.preventDefault();
      }
    };

    window.addEventListener('wheel', preventScroll, { passive: false });
    window.addEventListener('touchmove', preventScroll, { passive: false });

    return () => {
      window.removeEventListener('wheel', preventScroll);
      window.removeEventListener('touchmove', preventScroll);
    };
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      if (!containerRef.current) return;
      
      const { top, height } = containerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      
      const scrollY = -top;
      const scrollableHeight = height - viewportHeight;
      
      let progress = scrollY / scrollableHeight;
      progress = Math.max(0, Math.min(1, progress));
      
      const containerAbsoluteTop = window.scrollY + top; 

      if (isLocked.current && lockedProgress.current !== null) {
        // Force progress to stay at the locked milestone
        progress = lockedProgress.current;
        window.scrollTo({ top: containerAbsoluteTop + progress * scrollableHeight, behavior: 'auto' });
      } else {
        // Check if we crossed a milestone (1/3 or 2/3) where a transformation completes
        const milestones = [0.333, 0.666, 0.99];
        let crossedMilestone = -1;

        for (const m of milestones) {
          // Check if we crossed the threshold in either direction
          if (
            (prevProgress.current < m && progress >= m) || 
            (prevProgress.current > m && progress <= m)
          ) {
            crossedMilestone = m;
            break;
          }
        }

        if (crossedMilestone !== -1 && !(window as any).isNavigating) {
          isLocked.current = true;
          lockedProgress.current = crossedMilestone;
          progress = crossedMilestone; 
          
          const targetScroll = containerAbsoluteTop + crossedMilestone * scrollableHeight;
          window.scrollTo({ top: targetScroll, behavior: 'auto' });

          setTimeout(() => {
            isLocked.current = false;
            lockedProgress.current = null;
          }, 500);
        }
      }

      prevProgress.current = progress;

      // Use linear progress for smooth continuous morphing
      const totalFrames = FOLDERS.length * FRAMES_PER_TRANSITION; 
      const currentGlobalFrame = Math.floor(progress * (totalFrames - 1));
      
      const transitionIndex = Math.min(2, Math.floor(currentGlobalFrame / FRAMES_PER_TRANSITION));
      const localFrame = (currentGlobalFrame % FRAMES_PER_TRANSITION) + 1;
      
      let stage = Math.round(progress * 3);

      setCurrentStage(stage);
      const imagePath = getImagePath(transitionIndex, localFrame);
      loadImageAndDraw(imagePath);
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
  }, []);

  useEffect(() => {
    for (let i = 1; i <= 10; i++) {
      const img = new Image();
      img.src = getImagePath(0, i);
      imageCache.current.set(img.src, img);
    }
  }, []);

  return (
    <section 
      id="components"
      ref={containerRef} 
      className="relative bg-white" 
      style={{ height: '800vh' }}
    >
      <div className="sticky top-0 h-screen w-full flex items-center justify-center overflow-hidden">
        
        {/* Background Ambient Glow */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[80%] h-[80%] bg-primary/5 rounded-full blur-[150px]" />
        </div>

        {/* Text Container (Left & Right) */}
        <div className="absolute inset-0 z-10 flex items-center justify-between px-6 md:px-12 lg:px-20 pointer-events-none">
          {/* Left Text - Strictly constrained to prevent overlap */}
          <div className="w-[280px] lg:w-[320px] shrink-0">
            {STAGES.map((stage, i) => (
              <div 
                key={i} 
                className={`transition-all duration-700 absolute top-1/2 -translate-y-1/2 left-6 md:left-12 lg:left-20 w-[280px] lg:w-[320px] ${currentStage === i ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'}`}
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

          {/* Right Timeline Component Nav */}
          <div className="absolute right-6 md:right-12 lg:right-20 top-1/2 -translate-y-1/2 z-20">
            <div className="relative flex flex-col gap-[64px] items-center">
              
              {/* Background Line */}
              <div className="absolute left-1/2 -translate-x-1/2 top-[12px] bottom-[32px] w-[2px] bg-slate-300 -z-10" />
              
              {/* Active Orange Line */}
              <div 
                className="absolute left-1/2 -translate-x-1/2 top-[12px] w-[2px] bg-primary transition-all duration-700 ease-in-out -z-10"
                style={{ height: `calc(${currentStage} * 33.33%)` }}
              />

              {STAGES.map((stage, i) => {
                const isActive = currentStage === i;
                const isPassed = currentStage > i;
                
                // Shorten AHU for the timeline label
                const shortTitle = stage.title.includes('AHU') ? 'AHU' : stage.title;

                return (
                  <div key={i} className="relative flex flex-col items-center gap-2">
                    {/* Circle Indicator */}
                    <div className={`relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300 bg-white
                      ${isActive ? 'border-[#f97316] shadow-[0_0_15px_rgba(249,115,22,0.8)]' : 
                        isPassed ? 'border-[#f97316]' : 'border-slate-300'}
                    `}>
                      {isActive ? (
                        <div className="h-3 w-3 rounded-full bg-[#f97316]" />
                      ) : isPassed ? (
                        <div className="h-2 w-2 rounded-full bg-[#f97316]" />
                      ) : null}
                    </div>

                    {/* Label Below */}
                    <div className={`transition-all duration-300 text-center text-xs font-bold uppercase tracking-widest whitespace-nowrap
                      ${isActive ? 'text-[#f97316]' : 'text-slate-800'}
                    `}>
                      {shortTitle}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Center Canvas - Removed drop-shadow to blend background */}
        <div className="relative z-0 w-full md:w-[75%] lg:w-[65%] h-full flex items-center justify-center pointer-events-none">
          <canvas 
            ref={canvasRef} 
            className="w-full h-[90vh] object-contain"
          />
        </div>

        {/* Access Dashboard Button */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20">
          <button 
            onClick={() => {
              if (isAuthenticated && user?.role === 'admin') {
                navigate('/dashboard');
              } else {
                navigate('/login');
              }
            }}
            className="inline-flex h-12 items-center justify-center gap-3 rounded-full bg-gradient-cta px-8 text-sm font-semibold text-primary-foreground shadow-elevated-lp transition-all hover:brightness-110 hover:scale-105"
          >
            {isAuthenticated && user?.role === 'admin' ? (
              <>
                <Activity className="h-5 w-5" />
                Enter Predictive Dashboard
              </>
            ) : (
              <>
                <LogIn className="h-5 w-5" />
                Login to Access Dashboard
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
