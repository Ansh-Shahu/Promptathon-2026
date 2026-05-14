# 🏗️ Workspace Structure & Dependency Audit

This document outlines the current state of the `e:\Promptathon-2026` workspace, highlighting structural clutter, dependency risks, and potential deployment blockers. Nothing has been deleted yet; this serves as an action plan for final clean-up.

---

## 1. ⚠️ Critical Deployment Risks

### The Root `requirements.txt` Issue
- **Location**: `e:\Promptathon-2026\requirements.txt`
- **Issue**: This file is currently acting as a "README" containing instructions on how to install dependencies in different folders. It does *not* contain actual Python package names.
- **Why it's dangerous**: Automated CI/CD pipelines and PaaS deployment platforms (like Render, Heroku, AWS, Vercel) automatically scan the root folder. If they see a `requirements.txt`, they will assume the entire project is a single Python backend and attempt to run `pip install -r requirements.txt`. Because the file contains English instructions instead of valid pip dependencies, the deployment will crash immediately.
- **Recommended Action**: Rename this file to `DEPENDENCY_SETUP.md` or move its contents into a `README.md`.

---

## 2. 📁 Nested Project Clutter (Frontend)

### The "App inside an App" Pattern
- **Location**: `e:\Promptathon-2026\frontend\Landing_page\intelligent-hvac-systems-main\`
- **Issue**: The Landing Page is a completely independent React application (with its own `package.json`, `node_modules`, `vite.config.ts`, and `tsconfig.json`) nested *inside* the main `frontend/` React dashboard folder.
- **Why it's a concern**: 
  1. **Tooling Confusion**: Linters (ESLint), formatters (Prettier), and TypeScript servers often get confused when looking for configurations, leading to false-positive IDE errors (like the `@tanstack/react-router` error we saw earlier).
  2. **Git/Vite Build Conflicts**: If not carefully excluded, the parent `frontend/` build process might attempt to bundle files from the nested `Landing_page`, or Git hooks might run in the wrong context.
- **Recommended Action**: For this hackathon, it is safe to leave as-is since we have verified both run independently on different ports (5175 and 8080). However, post-hackathon, the `Landing_page` folder should be moved up to the root level (e.g., `e:\Promptathon-2026\marketing-site\`) so it sits side-by-side with `frontend/`.

---

## 3. 🗑️ Obsolete & Stray Files

### `frontend/app.py`
- **Location**: `e:\Promptathon-2026\frontend\app.py`
- **Issue**: This is a leftover, experimental FastAPI script (34 lines) sitting in a React frontend directory. It contains a dummy heuristic prediction (`if vibration > 0.7...`).
- **Why it's a concern**: It creates confusion. A judge or teammate reviewing the codebase might think this is the actual backend API, whereas the *real* backend is correctly located in `backend/main.py`.
- **Recommended Action**: Delete `frontend/app.py`.

---

## 4. 📦 Data & ML Pipeline Cleanliness

### `model.pkl` Handoff
- **Location**: `e:\Promptathon-2026\backend\model.pkl`
- **Status**: The ML pipeline is correctly structured. `ml_pipeline/train_model.py` trains the random forest and explicitly saves the artifact directly into the `backend/` directory. This is excellent practice and requires no changes.

### `hvac_telemetry.db` Size
- **Location**: `e:\Promptathon-2026\backend\hvac_telemetry.db`
- **Status**: The SQLite database is currently ~1MB, meaning it is successfully holding a large set of seeded sensor logs. 
- **Recommended Action**: Leave as-is for the demo to ensure the dashboard has rich data to display. Do not run the `seed_database.py` script again unless you intend to wipe the current logs.

---

## Summary of Action Items

When you are ready to execute the clean-up, I recommend the following quick terminal commands:

1. **Rename the instruction file**:
   `Rename-Item -Path e:\Promptathon-2026\requirements.txt -NewName DEPENDENCY_SETUP.md`
2. **Remove the stray backend script**:
   `Remove-Item e:\Promptathon-2026\frontend\app.py -Force`

Let me know if you want me to execute these, or if you'd like to review the `Landing_page` folder structure further!
