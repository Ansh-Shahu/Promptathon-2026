# 🏗️ DIMENSION 1: PROJECT STRUCTURE STANDARDS

**Score: 6.5/10** | Status: Moderate | Action: Refactor before scaling

---

## 📋 Table of Contents

1. [Assessment Scores](#assessment-scores)
2. [Backend Structure (9/10 - Excellent)](#backend-structure)
3. [Frontend Structure (6/10 - Fair)](#frontend-structure)
4. [ML Pipeline Structure (5/10 - Weak)](#ml-pipeline-structure)
5. [Naming Conventions](#naming-conventions)
6. [Industry Standards Comparison](#industry-standards-comparison)
7. [Refactoring Recommendations](#refactoring-recommendations)
8. [Scalability Assessment](#scalability-assessment)

---

## 📊 Assessment Scores

```
┌─────────────────────────────────────────────┐
│      STRUCTURE & ORGANIZATION SCORES       │
├─────────────────────────────────────────────┤
│ Backend                    █████████░ 9/10 │
│ Frontend                   ██████░░░░ 6/10 │
│ ML Pipeline                █████░░░░░ 5/10 │
│ Naming Conventions         ████████░░ 8/10 │
│ Documentation              ██░░░░░░░░ 2/10 │
│ Configuration Management   ███░░░░░░░ 3/10 │
│ Scalability (100+ devs)    ████░░░░░░ 4/10 │
├─────────────────────────────────────────────┤
│ OVERALL STRUCTURE SCORE    ████░░░░░░ 6.5/10
└─────────────────────────────────────────────┘
```

---

## ✅ Backend Structure (9/10)

### Current Layout

```
backend/
├── main.py                 ✅ Entry point - clear and explicit
├── config.py              ✅ Centralized configuration
├── database.py            ✅ DB setup isolated & reusable
├── models.py              ✅ ORM models grouped
├── schemas.py             ✅ Pydantic request/response schemas
├── crud.py                ✅ Repository layer (Create, Read, Update, Delete)
├── tests/                 ✅ Tests colocated with source
├── scripts/               ✅ Utility scripts organized
├── Makefile              ✅ Development tasks automated
├── pytest.ini
├── requirements.txt
├── .env
├── .env.local            (gitignored)
└── __pycache__
```

### Why This Works (Best Practices)

✅ **Clear Separation of Concerns**
- Router layer → Schema layer → CRUD layer → ORM models
- Data flows through distinct layers

✅ **FastAPI Idiom**
- All modules immediately importable (`from crud import ...`)
- Follows FastAPI documentation patterns

✅ **Database Layer Abstraction**
- `database.py` handles session management
- Easy to swap SQLite for PostgreSQL

✅ **Testing Colocated**
- `tests/` folder with parallel structure
- Easy to write and discover tests

### Scalability

**Current Readiness:** ✅ Can grow to 50-100 engineers  
**With minor refactoring:** Can handle 200+ engineers

**Recommended Enhancement (Optional):**
```
backend/
├── app/                              (NEW: Group by domain)
│   ├── core/                         (shared utilities)
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routers/
│   │   │   ├── schemas/
│   │   │   └── dependencies/
│   │   └── v2/
│   ├── models/
│   ├── crud/
│   ├── db/
│   └── schemas/
├── config.py
├── main.py
├── tests/
└── requirements.txt
```

---

## 🟡 Frontend Structure (6/10)

### Current Layout (Problems)

```
frontend/src/
├── components/            ❌ FLAT STRUCTURE (16 files)
│   ├── AIDiagnostics.tsx
│   ├── AlertFeed.tsx
│   ├── Card3D.tsx
│   ├── CompressorTable.tsx
│   ├── DigitalTwin.tsx
│   ├── FleetStats.tsx
│   ├── LandingPage.tsx
│   ├── LoginPage.tsx
│   ├── MaintenanceScheduler.tsx
│   ├── ReportsPanel.tsx
│   ├── ScrollTelling.tsx
│   ├── SensorCards.tsx
│   ├── SensorChart.tsx
│   ├── Sidebar.tsx
│   ├── SymptomTimeline.tsx
│   └── TopBar.tsx
├── services/              ✅ API calls isolated
│   └── api.ts
├── context/               ✅ State management
│   ├── AuthContext.tsx
│   └── ThemeContext.tsx
├── data/                  ✅ Mock data
│   └── mockData.ts
├── App.tsx
└── main.tsx
```

### Problems Identified

🔴 **16 unrelated files in flat `components/` folder**
- Hard to navigate at scale
- No feature boundaries
- Related components separated

🔴 **No custom hooks library**
- `use-mobile.tsx` orphaned in `hooks/`
- Should be in `context/hooks/`

🔴 **No shared utilities**
- No `shared/utils/` for reusable functions
- Type utilities scattered

🔴 **Feature pages mixed with UI components**
- `AIDiagnostics.tsx` (business logic)
- `SensorChart.tsx` (UI component)
- Should be in separate directories

### Recommended Refactor (Feature-Based)

**BEFORE (Flat):** Will hit scaling issues at ~20 components

```
frontend/src/
├── components/
│   ├── AIDiagnostics.tsx   (Business logic)
│   ├── SensorChart.tsx     (Business logic)
│   ├── AlertFeed.tsx       (Business logic)
│   ├── Sidebar.tsx         (UI Component)
│   └── TopBar.tsx          (UI Component)
```

**AFTER (Feature-Based):** Scales cleanly to 100+ components

```
frontend/src/
├── features/                                  (NEW)
│   ├── dashboard/                            (Feature: Dashboard page)
│   │   ├── components/
│   │   │   ├── DashboardLayout.tsx
│   │   │   ├── MetricsPanel.tsx
│   │   │   └── ChartsSection.tsx
│   │   ├── hooks/
│   │   │   ├── useDashboardData.ts
│   │   │   └── useDashboardFilters.ts
│   │   ├── services/
│   │   │   └── dashboardApi.ts
│   │   ├── types.ts
│   │   ├── constants.ts
│   │   └── index.ts
│   │
│   ├── alerts/                               (Feature: Alerts)
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types.ts
│   │   └── index.ts
│   │
│   ├── auth/                                 (Feature: Authentication)
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types.ts
│   │   └── index.ts
│   │
│   ├── scheduler/                            (Feature: Maintenance Scheduler)
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types.ts
│   │   └── index.ts
│   │
│   └── reports/                              (Feature: Reports)
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── types.ts
│       └── index.ts
│
├── shared/                                    (NEW: Reusable across features)
│   ├── components/
│   │   ├── Button.tsx       (Generic UI)
│   │   ├── Card.tsx
│   │   ├── Modal.tsx
│   │   └── Alert.tsx
│   ├── hooks/                                (Shared hooks library)
│   │   ├── use-mobile.tsx   (Moved from root)
│   │   ├── use-fetch.ts
│   │   ├── use-debounce.ts
│   │   └── use-local-storage.ts
│   ├── utils/
│   │   ├── formatting.ts
│   │   ├── validation.ts
│   │   └── helpers.ts
│   ├── constants/
│   │   ├── routes.ts
│   │   └── api.ts
│   └── types/
│       └── common.ts
│
├── core/                                     (NEW: App-wide setup)
│   ├── context/             (Moved from root)
│   │   ├── AuthContext.tsx
│   │   ├── ThemeContext.tsx
│   │   └── NotificationContext.tsx
│   ├── services/            (Moved from root)
│   │   └── api.ts
│   ├── config/
│   │   └── config.ts
│   └── types/
│       └── index.ts
│
├── App.tsx
├── main.tsx
├── vite-env.d.ts
└── index.css
```

### Scalability

**Current:** Breaks at 20+ components  
**Refactored:** ✅ Handles 50+ components easily  
**With API separation:** ✅ Scales to 200+ developers

**Key Benefits:**
- Features are independent packages
- Easy to find related code
- Clear feature boundaries
- Shared utilities centralized

---

## 🔴 ML Pipeline Structure (5/10)

### Current Layout (Problems)

```
ml_pipeline/
├── hvac_sensor_data.csv         ❌ Dataset in root
├── train_model.py               ❌ No organization
├── simulate_pf_curve_data.py    ❌ Windows-specific paths
└── inject_fault.py              ✅ Utility (OK)
```

### Problems

🔴 **No versioning for artifacts**
- `model.pkl` is single, unversioned
- Cannot rollback to previous model
- No experiment tracking

🔴 **Data and scripts mixed**
- No separation of raw, processed, splits
- Hard to reproduce results

🔴 **No notebook support**
- No EDA (Exploratory Data Analysis)
- No feature engineering notebooks
- No analysis artifacts

🔴 **Windows path hardcoding**
- Will fail on CI/CD (Linux)
- Not portable

### Recommended Structure (MLOps Standard)

```
ml_pipeline/
├── data/                                     (NEW: Data management)
│   ├── raw/
│   │   └── hvac_sensor_data.csv             (Original, never modify)
│   ├── processed/
│   │   ├── train_set.csv
│   │   ├── test_set.csv
│   │   └── validation_set.csv
│   └── splits/
│       ├── 80_20_split.pkl
│       └── stratified_split.pkl
│
├── models/                                   (NEW: Versioned artifacts)
│   ├── v001_baseline/
│   │   ├── model.pkl
│   │   ├── metadata.json
│   │   │   {
│   │   │     "version": "v001",
│   │   │     "timestamp": "2026-05-13T10:30:00",
│   │   │     "accuracy": 0.876,
│   │   │     "f1_score": 0.834,
│   │   │     "hyperparameters": {...},
│   │   │     "feature_importance": {...}
│   │   │   }
│   │   ├── metrics.json
│   │   ├── confusion_matrix.png
│   │   └── feature_importance.png
│   │
│   ├── v002_tuned/
│   │   ├── model.pkl
│   │   ├── metadata.json
│   │   └── metrics.json
│   │
│   ├── v003_production/
│   │   ├── model.pkl
│   │   └── metadata.json
│   │
│   └── current_production → v003_production/    (Symlink)
│
├── notebooks/                                (NEW: Analysis & EDA)
│   ├── 01_eda.ipynb                         (Exploratory analysis)
│   ├── 02_feature_engineering.ipynb         (Feature creation)
│   ├── 03_model_comparison.ipynb            (Model selection)
│   └── 04_error_analysis.ipynb              (Failure analysis)
│
├── src/                                      (NEW: Reusable code)
│   ├── __init__.py
│   ├── data_pipeline.py                      (Loading + preprocessing)
│   ├── feature_engineering.py                (Feature creation)
│   ├── model_training.py                     (Model training)
│   ├── model_evaluation.py                   (Evaluation metrics)
│   ├── model_deployment.py                   (Deployment logic)
│   └── utils.py                              (Helper functions)
│
├── config/                                   (NEW: Configuration)
│   ├── default.yaml                          (Shared config)
│   ├── development.yaml
│   ├── staging.yaml
│   └── production.yaml
│
├── scripts/                                  (NEW: Executables)
│   ├── train_model.py                        (Orchestrator)
│   ├── evaluate_model.py                     (Evaluation)
│   ├── generate_data.py                      (Data generation)
│   ├── deploy_model.py                       (Deployment)
│   └── inject_fault.py                       (Already exists - good)
│
├── tests/                                    (NEW: Tests)
│   ├── test_data_pipeline.py
│   ├── test_feature_engineering.py
│   ├── test_model_training.py
│   └── test_model_evaluation.py
│
├── requirements.txt                          (Already exists)
├── requirements-dev.txt                      (NEW: Dev dependencies)
│   # pytest, jupyter, notebook, etc.
│
└── README.md                                 (NEW: Documentation)
    # Model description, usage, performance
```

### Scalability

**Current:** Single researcher only  
**Refactored:** ✅ Team of 3-5 data scientists  
**With proper MLOps:** ✅ Scales to large ML team

---

## 📝 Naming Conventions

### Backend Python (✅ PEP-8 Compliant)

```python
# Constants (UPPER_SNAKE_CASE) ✅ Correct
DATABASE_URL = "sqlite://..."
MAX_CONNECTIONS = 100
TIMEOUT_SECONDS = 30

# Functions (lower_snake_case) ✅ Correct
def create_user(db: Session, user_schema: UserCreate) -> User:
    pass

def fetch_sensor_readings(skip: int = 0, limit: int = 100):
    pass

# Classes (PascalCase) ✅ Correct
class UserRepository:
    pass

class SensorDataProcessor:
    pass

# Variables (lower_snake_case) ✅ Correct
user_id = 123
is_active = True
sensor_readings = []
```

**Status:** ✅ Consistent across backend

---

### Frontend TypeScript (✅ React/TS Conventions)

```typescript
// Components (PascalCase) ✅ Correct
export const UserDashboard = () => {}
export const SensorChart = () => {}

// Custom Hooks (use + PascalCase) ✅ Correct
export const useUserAuth = () => {}
export const useDashboardData = () => {}

// Constants (UPPER_SNAKE_CASE) ✅ Mostly Correct
const API_BASE_URL = "http://localhost:8000"
const MAX_RETRIES = 3

// Variables/Functions (camelCase) ✅ Correct
const handleSubmit = () => {}
const userName = "John"
const sensorReadings: SensorReading[] = []

// Types (PascalCase + Suffix) ✅ Correct
interface UserProps { }
interface SensorReadingProps { }
type UserStatus = "active" | "inactive"
```

**Status:** ✅ Mostly consistent | Minor variance in constants

---

## 🏢 Industry Standards Comparison

### How We Compare (Backend)

| Standard | Promptathon | Recommendation |
|----------|-----------|-----------------|
| **Organization** | ✅ Layer-based | Keep as-is |
| **Module import** | ✅ Flat | Good for this scale |
| **Naming** | ✅ PEP-8 | Excellent |
| **Testing** | 🟡 54% | Improve to 80%+ |
| **Documentation** | ❌ Missing | Add docstrings |

**We Follow:** FastAPI best practices ✅

---

### How We Compare (Frontend)

| Standard | Promptathon | Recommendation |
|----------|-----------|-----------------|
| **Organization** | 🔴 Flat | Refactor to features |
| **Module import** | 🟡 Mixed | Improve barrel exports |
| **Naming** | ✅ React conventions | Good |
| **Testing** | 🔴 0% | Add tests |
| **Documentation** | ❌ Missing | Add JSDoc |

**We Should Follow:** Next.js/Remix feature-based architecture for scale

---

## 🔧 Refactoring Recommendations

### Phase 1: Frontend Structure (Priority: HIGH)
**Before:** 16 files in flat `components/`  
**After:** Feature-based organization  
**Effort:** 2-3 days | **Impact:** Huge (prevents future scaling)

**Steps:**
```bash
# 1. Create new structure
mkdir -p frontend/src/features/{dashboard,alerts,auth,scheduler,reports}
mkdir -p frontend/src/shared/{components,hooks,utils,constants,types}
mkdir -p frontend/src/core/{context,services,config}

# 2. Move files to correct locations
mv AIDiagnostics.tsx → features/dashboard/components/
mv AlertFeed.tsx → features/alerts/components/
# ... etc

# 3. Update imports
# From: import AIDiagnostics from '../../../components'
# To: import { AIDiagnostics } from '@/features/dashboard'

# 4. Add barrel exports (index.ts)
# Each folder gets index.ts for clean imports
```

### Phase 2: ML Pipeline Organization (Priority: HIGH)
**Before:** Files in root  
**After:** Standard MLOps structure  
**Effort:** 3-4 hours | **Impact:** Better maintenance

### Phase 3: Backend Documentation (Priority: MEDIUM)
**Before:** No architecture docs  
**After:** Architecture.md + API docs  
**Effort:** 1-2 days | **Impact:** New dev onboarding

---

## 📈 Scalability Assessment

### Team Size Scaling

```
┌────────────────────────────────────────────────┐
│    ARCHITECTURE READINESS BY TEAM SIZE        │
├────────────────────────────────────────────────┤
│ Current (2-3 devs)        ✅ Works fine       │
│ 5-10 devs                 ✅ Works           │
│ 10-20 devs                🟡 Starting stress │
│ 20-50 devs                🔴 Will break      │
│ 50-100 devs               🔴 Major refactor  │
│ 100+ devs                 ❌ Not designed    │
└────────────────────────────────────────────────┘
```

### Specific Bottlenecks

**Frontend:**
- [ ] At 20 components → refactor to features (Critical)
- [ ] At 50 components → break into domain packages
- [ ] At 100 components → consider monorepo packages

**Backend:**
- [ ] At 50 endpoints → organize by API version + domain
- [ ] At 100 endpoints → consider microservices architecture
- [ ] Current structure fine → no immediate action needed

**ML Pipeline:**
- [ ] At 5 models → implement versioning (Critical)
- [ ] At 20 experiments → use MLFlow for tracking
- [ ] At 100 features → implement feature store

---

## ✅ Action Items

### This Sprint
- [ ] Review this document with team
- [ ] Decide: Refactor frontend now or later?

### Before Scaling to 20+ Developers
- [ ] Refactor frontend to feature-based structure
- [ ] Add comprehensive documentation
- [ ] Organize ML pipeline with versioning

### Long-term (MVP Complete)
- [ ] Consider monorepo structure (Turbo, Nx)
- [ ] Implement backend API versioning
- [ ] Set up MLOps infrastructure (MLFlow)

---

## 🔗 Related Documents

- [90_DAY_IMPLEMENTATION_ROADMAP.md](90_DAY_IMPLEMENTATION_ROADMAP.md) - Refactoring timeline
- [VULNERABILITY_CHECKLIST.md](VULNERABILITY_CHECKLIST.md) - Structure-related issues
- [00_AUDIT_README.md](00_AUDIT_README.md) - Back to overview

---

**Status:** ✅ Analysis Complete  
**Recommendation:** Refactor frontend before team grows beyond 10 developers  
**Effort to Fix:** 2-3 days for frontend, 3-4 hours for ML pipeline

Start refactoring! 🚀
