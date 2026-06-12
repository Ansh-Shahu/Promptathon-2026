# HVAC Predictive Maintenance — Deep File & Folder Analysis: Frontend Components & Routing

> **Generated:** 2026-05-26
> **Scope:** `frontend/src/components/`, `site/`, `ui/`, `routes/`

---

## 1. Dashboard Application Components (`frontend/src/components/`)

These files define the operational interface of the Predictive Maintenance system.

### `LoginPage.tsx`
- **Purpose:** Renders the authentication screen.
- **Why it exists:** Protects the main dashboard behind a credential check.
- **Error Resilience:** Provides inline validation. If the `AuthContext.login()` fails, an error message is displayed directly on the form.
- **Future Scope / Improvements:** Add rate limiting, "forgot password" functionality, and a secure HTTP POST to the backend instead of local evaluation.

### `LandingPage.tsx`
- **Purpose:** The original marketing page.
- **Anomaly:** This file appears to be redundant given the presence of the `site/` folder (which contains a merged TanStack landing page).
- **Future Scope / Improvements:** Compare with `site/index.tsx` and delete this file if the TanStack migration fully replaced it.

### `Sidebar.tsx` & `TopBar.tsx`
- **Purpose:** Core navigation and layout headers.
- **Why it exists:** Provides consistent global navigation, search, and system status indicators.
- **What and why it uses:** `TopBar` displays the `prediction_mode` (ML vs Heuristic) dynamically fetched from the `/health` endpoint, so operators know if AI inference is active.
- **Future Scope / Improvements:** Make the Sidebar fully collapsible for mobile responsiveness.

### `FleetStats.tsx` & `CompressorTable.tsx`
- **Purpose:** High-level key performance indicators (KPIs) and the sortable grid view of all equipment.
- **Why it exists:** Operators need a top-down view to identify which specific chiller or compressor requires attention before diving into individual telemetry.
- **Error Resilience:** The table handles empty datasets cleanly and implements conditional row highlighting for critical status.
- **Future Scope / Improvements:** Add CSV export capabilities to the table and implement infinite scrolling or pagination for fleets larger than 1,000 units.

### `SensorCards.tsx` & `SensorChart.tsx`
- **Purpose:** Real-time data visualization.
- **Why it exists:** Translates raw database rows into visual trends (line charts) and instant-read gauges.
- **What and why it uses:** Uses `recharts` for highly performant, responsive SVG charting.
- **Future Scope / Improvements:** Add zooming and panning to the chart. Allow users to toggle specific sensors on/off.

### `AIDiagnostics.tsx` & `SymptomTimeline.tsx`
- **Purpose:** Explains the "why" behind an anomaly.
- **Why it exists:** ML models are often black boxes. These components map raw risk scores into human-readable symptoms (e.g., "Vibration > 4.5 mm/s") and generate structured maintenance tickets.
- **Future Scope / Improvements:** Feed the ticket generation into a real ITSM system (like ServiceNow or Jira) via an API integration.

### `AlertFeed.tsx` & `MaintenanceScheduler.tsx` & `ReportsPanel.tsx`
- **Purpose:** Operational workflows for acknowledging alerts, scheduling repairs, and viewing cost savings.
- **Why it exists:** Bridges the gap between passive monitoring and active workflow management.
- **Future Scope / Improvements:** Persist the "acknowledged" state of an alert to the backend database so it updates across all users' screens.

### `DigitalTwin.tsx` & `Card3D.tsx`
- **Purpose:** An interactive simulator and 3D viewer.
- **Why it exists:** Allows users to manually drag sliders (temp, vibration) and submit them to `POST /predict` to see how the Random Forest model reacts in real-time.
- **Future Scope / Improvements:** Replace the `Card3D` image sequence player with a true Three.js WebGL viewer to reduce network load.

### `ScrollTelling.tsx`
- **Purpose:** A presentation component using scroll position to trigger animations.
- **Future Scope / Improvements:** Ensure IntersectionObserver logic is fully cleaned up on component unmount to prevent memory leaks.

---

## 2. Marketing Landing Page Components (`frontend/src/components/site/`)

These components were ported over from a separate codebase to unify the marketing site and the dashboard into one repository.

### `Header.tsx`, `Hero.tsx`, `Features.tsx`, `HowItWorks.tsx`, `SocialProof.tsx`, `CTA.tsx`, `Footer.tsx`
- **Purpose:** Construct a modern, high-converting marketing landing page.
- **Why it exists:** To sell the product to potential clients before they log into the dashboard.
- **Error Resilience:** During migration, these files had broken `@/` imports. These were successfully patched to relative paths (e.g., `../../components/ui/button`).
- **Future Scope / Improvements:** Connect the `CTA.tsx` contact form to a backend mailing service (e.g., SendGrid) so demo requests are actually captured.

---

## 3. UI Primitives (`frontend/src/components/ui/`)

### `button.tsx`, `card.tsx`, `dialog.tsx`, `input.tsx`, etc. (43 files)
- **Purpose:** A complete, accessible design system (likely generated via `shadcn/ui`).
- **Why it exists:** Ensures pixel-perfect visual consistency across the app. Every component is built on headless Radix UI primitives for maximum screen-reader accessibility.
- **Anomaly:** Every single one of these 43 files imports a `cn()` utility function from `@/lib/utils` (or a relative equivalent) which **does not exist** in the repository.
- **Error Resilience:** In their current state, they will crash the React bundler if imported because of the missing dependency.
- **Future Scope / Improvements:** **P1 Priority Fix:** Create the missing `frontend/src/lib/utils.ts` file containing the `clsx` and `tailwind-merge` logic required by `shadcn/ui`.

---

## 4. TanStack Routing Setup (`frontend/src/routes/`)

### `routes/__root.tsx` & `routes/index.tsx`
- **Purpose:** File-based routing configuration for the landing page.
- **Anomaly 1:** `__root.tsx` imports a nonexistent CSS file (`../styles.css?url`).
- **Anomaly 2:** Contains boilerplate text like "Lovable Generated Project" in the SEO meta tags.
- **Future Scope / Improvements:** Remove the placeholder boilerplate. Fix the CSS import path.

### `routeTree.gen.ts` & `router.tsx`
- **Purpose:** Auto-generated route manifest for TanStack Router.
- **Anomaly:** `routeTree.gen.ts` references a `./start.ts` file that does not exist.
- **Overall TanStack Status:** Currently, the dashboard uses `react-router-dom` in `App.tsx`, and the TanStack setup exists in parallel. 
- **Future Scope / Improvements:** Decide on a single routing paradigm. Either refactor the dashboard to use TanStack Router, or port the landing page into `react-router-dom` and delete the `routes/` folder entirely. This will resolve all routing anomalies and reduce bundle size.
