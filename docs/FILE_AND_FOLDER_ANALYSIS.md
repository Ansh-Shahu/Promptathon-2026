# HVAC Predictive Maintenance — Master File & Folder Analysis

> **Generated:** 2026-05-26
> **Audience:** Developers, AI Assistants, Hackathon Judges

To bypass token and quota constraints while preserving maximum detail, the full file-by-file analysis has been split into dedicated, exhaustive documents. 

No files or folders have been minimised. Every component, config, and script across the monorepo is documented with its **Purpose**, **Why it exists**, **What it uses**, **Error Resilience**, **Anomalies**, and **Future Scope / Improvements**.

---

## 📚 The Deep Dive Documentation Suite

Please read the following documents for exhaustive analysis of their respective domains:

### 1. [Root & ML Pipeline Analysis](file:///e:/Promptathon-2026/docs/analysis_root_ml.md)
*Covers the root `requirements.txt` and the entire `ml_pipeline/` directory (P-F curve simulator, dataset, training script, fault injector).*

### 2. [Backend Analysis](file:///e:/Promptathon-2026/docs/analysis_backend.md)
*Covers the FastAPI application (`backend/`), including environment configs, Pydantic schemas, SQLAlchemy ORM, CRUD layers, dependency injection, routing, the model artifact, and the 3,144-line integration test suite.*

### 3. [Frontend Core & Services Analysis](file:///e:/Promptathon-2026/docs/analysis_frontend.md)
*Covers frontend configuration (Vite, TypeScript, NPM), root files, contexts (Auth/Theme), API service layers, static mock data, and 3D assets.*

### 4. [Frontend Components & Routing Analysis](file:///e:/Promptathon-2026/docs/analysis_frontend_components.md)
*Covers the 16+ dashboard UI widgets, the marketing landing page components, the 43 shadcn/ui design system primitives, and the dual routing setups (react-router-dom vs TanStack).*

---

## 🚨 Top 5 Critical Anomalies Discovered (Summary)

For the full list of anomalies, consult the individual documents above. These are the immediate blockers:

1. **P0 SECURITY:** `backend/.env` uses a placeholder `SECRET_KEY`.
2. **P1 CRASH RISK:** 43 shadcn components in `frontend/src/components/ui/` import `@/lib/utils` which **does not exist** in the repository.
3. **P1 DEAD CODE:** `frontend/app.py` is a deprecated 3-field prototype script that must be deleted.
4. **P1 VERSION MISMATCH:** `ml_pipeline/requirements.txt` uses `scikit-learn==1.6.1` while `backend/requirements.txt` uses `1.8.0`. This will cause model deserialization failures.
5. **P2 DEPLOYMENT BLOCKER:** `frontend/src/services/api.ts` hardcodes the backend URL to `http://localhost:8000`.

---

**Companion Document:** Review the visual directory map and data flow in [PROJECT_STRUCTURE_TREE.md](file:///e:/Promptathon-2026/docs/PROJECT_STRUCTURE_TREE.md).
