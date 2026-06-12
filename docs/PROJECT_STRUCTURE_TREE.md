# HVAC Predictive Maintenance — Complete Project Structure

> **Generated:** 2026-05-25  
> **Audience:** Human developers, AI assistants, hackathon judges  
> **Companion doc:** `FILE_AND_FOLDER_ANALYSIS.md` (deep-dive per-file analysis)

---

```
Promptathon-2026/
│
├── backend/                          # FastAPI Python Backend (Port :8000)
│   ├── .env                          # Environment variables (DB URL, CORS, SECRET_KEY, MODEL_PATH)
│   ├── config.py                     # Pydantic Settings — centralised, type-safe config singleton
│   ├── database.py                   # SQLAlchemy engine, session factory, get_db() DI dependency
│   ├── models.py                     # ORM model: SensorTelemetryLog (sensor_logs table)
│   ├── schemas.py                    # Pydantic v2 request/response contracts with physical-bounds validation
│   ├── crud.py                       # Data Access Object layer (create, read, aggregate)
│   ├── main.py                       # FastAPI app: lifespan, CORS, prediction endpoint, health check
│   ├── model.pkl                     # Trained Random Forest model artifact (loaded at startup)
│   ├── hvac_telemetry.db             # SQLite database file (auto-created on first run)
│   ├── Makefile                      # Developer commands (make run, make test, make clean)
│   ├── requirements.txt              # Pinned Python dependencies
│   └── tests/
│       └── test_api.py               # 121-test integration suite (3,144 lines)
│
├── frontend/                         # React + Vite + Tailwind Dashboard (Port :5175)
│   ├── index.html                    # HTML shell (Inter font, Font Awesome, #root mount)
│   ├── package.json                  # NPM manifest (React 19, Vite 8, Recharts, Tailwind 4)
│   ├── package-lock.json             # Deterministic dependency lockfile
│   ├── vite.config.ts                # Vite dev server config (port 5175, React + Tailwind plugins)
│   ├── tsconfig.json                 # TypeScript compiler options
│   ├── app.py                        # ⚠️ LEGACY: Original 3-field prototype (superseded by backend/)
│   │
│   ├── public/
│   │   └── 3d-assets/                # Pre-rendered 3D equipment image sequences
│   │       ├── ahu/                  # Air Handling Unit frames (192 PNGs, ~110 MB)
│   │       ├── chiller/              # Chiller unit frames (192 PNGs, ~110 MB)
│   │       └── compressor_ahu/       # Compressor unit frames (192 PNGs, ~110 MB)
│   │
│   └── src/
│       ├── main.tsx                  # React DOM entry — renders App into #root
│       ├── App.tsx                   # Master app: router, auth guards, data orchestration
│       ├── index.css                 # Global CSS: design tokens, themes, animations
│       │
│       ├── context/
│       │   ├── AuthContext.tsx        # Auth state (login/logout, admin/worker roles)
│       │   └── ThemeContext.tsx       # Dark/light theme toggle with localStorage
│       │
│       ├── data/
│       │   └── mockData.ts           # Static mock data + TypeScript interfaces
│       │
│       ├── services/
│       │   └── api.ts                # HTTP client (fetchHealth, fetchHistory, fetchStats, submitPrediction)
│       │
│       ├── components/               # Dashboard UI components
│       │   ├── LoginPage.tsx          # Authentication screen
│       │   ├── LandingPage.tsx        # Original inline landing page
│       │   ├── Sidebar.tsx            # Navigation sidebar
│       │   ├── TopBar.tsx             # Header bar with ML engine badge
│       │   ├── FleetStats.tsx         # KPI stat cards row
│       │   ├── CompressorTable.tsx    # Sortable equipment fleet table
│       │   ├── SensorCards.tsx        # Individual sensor metric cards
│       │   ├── SensorChart.tsx        # Recharts time-series line chart
│       │   ├── SymptomTimeline.tsx    # Degradation symptom timeline
│       │   ├── AlertFeed.tsx          # Live alert list with acknowledge
│       │   ├── AIDiagnostics.tsx      # AI analysis panel + ticket generation
│       │   ├── DigitalTwin.tsx        # Interactive ML simulator (calls POST /predict)
│       │   ├── MaintenanceScheduler.tsx # Maintenance calendar + tickets
│       │   ├── ReportsPanel.tsx       # Weekly health reports
│       │   ├── Card3D.tsx             # 3D equipment viewer (image sequence)
│       │   ├── ScrollTelling.tsx      # Scroll-driven animation component
│       │   │
│       │   ├── site/                  # Marketing landing page (merged from TanStack project)
│       │   │   ├── Header.tsx         # Landing nav (Log in / Dashboard buttons)
│       │   │   ├── Hero.tsx           # Hero section with headline + CTA
│       │   │   ├── Features.tsx       # Product feature cards
│       │   │   ├── HowItWorks.tsx     # Step-by-step workflow
│       │   │   ├── SocialProof.tsx    # Testimonials / trust indicators
│       │   │   ├── CTA.tsx            # Contact form section
│       │   │   └── Footer.tsx         # Landing page footer
│       │   │
│       │   └── ui/                    # shadcn/ui design system (43 primitives)
│       │       ├── button.tsx, card.tsx, dialog.tsx, input.tsx, table.tsx,
│       │       │   tabs.tsx, slider.tsx, select.tsx, checkbox.tsx, badge.tsx,
│       │       │   tooltip.tsx, accordion.tsx, alert.tsx, avatar.tsx, etc.
│       │       └── (43 reusable UI primitives total)
│       │
│       ├── routes/                    # TanStack file-based routing (landing page)
│       │   ├── __root.tsx             # Root layout: QueryClient, 404/error pages
│       │   └── index.tsx              # Landing page route ("/")
│       │
│       ├── routeTree.gen.ts           # Auto-generated TanStack route tree
│       └── router.tsx                 # TanStack router factory
│
├── ml_pipeline/                       # Machine Learning Training Environment
│   ├── simulate_pf_curve_data.py      # Synthetic P-F curve dataset generator (1,000 rows)
│   ├── hvac_sensor_data.csv           # Generated training dataset (1,000 rows × 11 cols)
│   ├── train_model.py                 # RF training pipeline → exports model.pkl
│   ├── inject_fault.py                # Demo utility — sends critical fault to API
│   └── requirements.txt               # ML deps (scikit-learn, pandas, numpy, joblib)
│
├── docs/                              # Project documentation
│   ├── 00_AUDIT_README.md             # Security and code quality audit overview
│   ├── DIMENSION_1_PROJECT_STRUCTURE.md
│   ├── VULNERABILITY_CHECKLIST.md     # Security vulnerability tracking
│   ├── PROJECT_STRUCTURE_TREE.md      # This file
│   └── FILE_AND_FOLDER_ANALYSIS.md    # Deep-dive per-file analysis
│
└── requirements.txt                   # Root instructions pointing to folder-specific deps
```

---

## Data Flow

```
ml_pipeline/simulate_pf_curve_data.py
        │ generates
        ▼
ml_pipeline/hvac_sensor_data.csv
        │ consumed by
        ▼
ml_pipeline/train_model.py ──▶ backend/model.pkl
                                      │
                                      ▼ loaded at startup
                               backend/main.py
                                 │         │
              POST /predict ◀────┘         └────▶ crud.py ──▶ SQLite DB
                    │
                    ▼
         PredictionResponse ──▶ frontend/src/App.tsx
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                   ▼
              SensorChart      CompressorTable      DigitalTwin
              AlertFeed        FleetStats           TopBar Badge
              SymptomTimeline  AIDiagnostics        ReportsPanel
```
