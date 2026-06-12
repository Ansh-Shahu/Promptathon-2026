# HVAC Predictive Maintenance — Deep File & Folder Analysis: Frontend Core & Services

> **Generated:** 2026-05-26
> **Scope:** `frontend/` (Config, Core, Contexts, Services, Mock Data)

---

## 1. Frontend Configuration & Root Files

### `frontend/index.html`
- **Purpose:** The fundamental HTML shell served to the browser.
- **Why it exists:** Provides the mounting point (`<div id="root"></div>`) for the React application and loads external typography/icons.
- **What and why it uses:** Uses `Google Fonts` (Inter) for modern typography and `Font Awesome` for generic icons, ensuring fast visual loading before React fully boots.
- **Future Scope / Improvements:** Add preconnect links for backend API domains to accelerate DNS resolution. Move Font Awesome to local SVG imports (e.g., via `lucide-react`) to reduce the initial blocking render overhead.

### `frontend/package.json` & `package-lock.json`
- **Purpose:** NPM manifest tracking project metadata, scripts, and dependencies.
- **Why it exists:** Defines the exact ecosystem required to build and run the frontend.
- **Anomaly:** The project depends on **both** `react-router-dom` and `@tanstack/react-router`. This causes bloat and developer confusion.
- **Future Scope / Improvements:** Remove the unused router dependency to shrink the final JavaScript bundle size and standardise navigation logic.

### `frontend/vite.config.ts`
- **Purpose:** Configuration for the Vite bundler and development server.
- **Why it exists:** Replaces Webpack. Compiles TypeScript and CSS exponentially faster during development via ESBuild.
- **Error Resilience:** Hardcodes port `5175`. This ensures the backend CORS policies match a predictable frontend port.
- **Future Scope / Improvements:** Add path aliases (e.g., `resolve.alias: { "@": path.resolve(__dirname, "./src") }`) so the `@/` imports found in the TanStack code do not break the build.

### `frontend/tsconfig.json`
- **Purpose:** Strict TypeScript compiler configuration.
- **Anomaly:** Missing path alias definitions (`paths: { "@/*": ["./src/*"] }`), which means any component imported with `@/` will immediately throw a compiler error.
- **Future Scope / Improvements:** Sync the path aliases with `vite.config.ts`.

### `frontend/app.py` ⚠️ LEGACY
- **Purpose:** A legacy 3-field FastAPI prototype script.
- **Anomaly:** This file lives inside the frontend folder, is written in Python, uses deprecated Pydantic v1 imports, and is entirely superseded by the actual `backend/` application.
- **Future Scope / Improvements:** **Delete immediately.**

---

## 2. React Core (`frontend/src/`)

### `frontend/src/main.tsx`
- **Purpose:** The React DOM entry point.
- **Why it exists:** Bootstraps the `<App />` component and injects it into the DOM. Wraps the app in `<React.StrictMode>` to aggressively highlight potential lifecycle or state mutation bugs in development.

### `frontend/src/App.tsx`
- **Purpose:** Master application component and data orchestrator.
- **What and why it uses:** Uses `BrowserRouter` from `react-router-dom`. Handles the core layout structure and invokes the API fetching logic.
- **Error Resilience:** Features graceful degradation. If the backend API fetch fails, `App.tsx` seamlessly falls back to reading static objects from `mockData.ts`, rendering a "Static Data Mode" banner so the user is aware but not blocked.
- **Future Scope / Improvements:** Extract the heavy data transformation functions (like `historyToTrendData`) into a dedicated `utils/transformers.ts` file. Implement React `<ErrorBoundary>` components to prevent a single failing dashboard widget from crashing the entire page.

### `frontend/src/index.css`
- **Purpose:** Global styling and CSS Custom Properties (variables).
- **Why it exists:** Defines the central design tokens (colours, fonts, border radii) that make up the "Dark Mode" aesthetic and glassmorphism UI.
- **What and why it uses:** Uses Tailwind `@tailwind` directives combined with native CSS variables for dynamic theming.
- **Future Scope / Improvements:** Extract large custom animations into Tailwind plugins within `tailwind.config.ts` to keep the CSS file clean.

---

## 3. Context Providers (`frontend/src/context/`)

### `frontend/src/context/AuthContext.tsx`
- **Purpose:** Manages global authentication state.
- **Why it exists:** Avoids prop-drilling user permissions down to every dashboard component.
- **Error Resilience:** Provides distinct `admin` vs `worker` roles to conditionally render sensitive actions (like maintenance ticket approval).
- **Anomaly:** Credentials (`admin123`, `worker123`) are completely hardcoded. No backend auth API is hit. Session state lives only in React RAM, meaning a page refresh logs the user out.
- **Future Scope / Improvements:** Integrate actual JWT (JSON Web Token) authentication with the FastAPI backend. Store tokens securely in HttpOnly cookies or `localStorage`.

### `frontend/src/context/ThemeContext.tsx`
- **Purpose:** Manages the visual toggle between Light and Dark modes.
- **Error Resilience:** Uses lazy state initialization to read from `localStorage` on boot, ensuring the user's preference persists across tabs and reloads.
- **Future Scope / Improvements:** Add a `system` theme option that reads `window.matchMedia('(prefers-color-scheme: dark)')` to automatically match the user's OS settings.

---

## 4. Services & Data (`frontend/src/services/` & `data/`)

### `frontend/src/services/api.ts`
- **Purpose:** Centralized HTTP client.
- **Why it exists:** Keeps `fetch()` calls and URL construction out of the React components, ensuring a single place to handle networking errors and API versioning.
- **Anomaly:** `API_BASE_URL` is hardcoded to `http://localhost:8000`. This will fail as soon as the frontend is deployed to a server.
- **Future Scope / Improvements:** 
  - Change `API_BASE_URL` to dynamically read `import.meta.env.VITE_API_URL`.
  - Add request/response interceptors (using Axios or native fetch wrappers) to automatically attach auth headers or handle 401 Unauthorized responses globally.

### `frontend/src/data/mockData.ts`
- **Purpose:** Static fallback data and TypeScript interface definitions.
- **Why it exists:** Essential for rapid UI prototyping without needing a live backend. Also acts as the type-safety contract for all React components.
- **Future Scope / Improvements:** Separate the TypeScript `interface` definitions into a `types/` folder and keep `mockData.ts` strictly for data arrays.

---

## 5. Public Assets (`frontend/public/3d-assets/`)

### `3d-assets/ahu/`, `chiller/`, `compressor_ahu/`
- **Purpose:** Image sequences used to simulate 3D rotation in the `Card3D.tsx` component.
- **Why it exists:** Rendering actual WebGL/Three.js models can be computationally heavy. Scrubbing through an array of pre-rendered PNGs based on mouse position is a low-CPU alternative.
- **Anomaly:** There are nearly 600 PNG frames taking up over 330 MB of disk space. This is catastrophic for initial page load times over a network.
- **Future Scope / Improvements:** 
  - Convert all images to `.webp` format, which should reduce the size by up to 70% with negligible quality loss.
  - Alternatively, build a real lightweight `<canvas>` 3D viewer using `@react-three/fiber` and `.gltf` model files.
