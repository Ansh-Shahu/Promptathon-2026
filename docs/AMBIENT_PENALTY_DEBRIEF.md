# Phase 4: Architectural Debrief — Thermal Ambient Penalty Integration

> **Date:** 2026-07-21  
> **Status:** ✅ CODE COMPLETE — Primed for Rigorous Testing Phase

---

## 1. Filesystem Change Manifest

### Modified Files

| File | Lines Changed | Change Category |
|------|:---:|-------------|
| `backend/physics_engine.py` | +108 | **Core Integration** — Ambient penalty constants, `compute_ambient_condenser_penalty()` function, weight rebalancing, `σ_amb` factor, alert branch |
| `backend/main.py` | +7 / -12 | **Housekeeping** — Removed orphaned constant, updated prediction mode label, rewrote stale docstrings |

### Unchanged Files (Verified)

| File | Reason |
|------|--------|
| `schemas.py` | All physics outputs remain within existing Pydantic bounds |
| `models.py` | No ORM changes |
| `crud.py` | No CRUD changes |
| `database.py` | No session changes |
| `requirements.txt` | No new dependencies (pure `math` stdlib) |
| `ml_pipeline/*` | Not in scope |
| `frontend/*` | Not in scope |

---

## 2. Mathematical Modifications — Final State

### 2.1 Ambient Condenser Pressure Penalty (New)

```
ΔP_discharge = K_amb_condenser × max(0, T_amb - T_design)
ΔP_suction   = K_amb_suction   × max(0, T_amb - T_design)
```

| Constant | Value | Source |
|----------|-------|--------|
| `T_AMB_DESIGN` | 75.0°F | ARI 550/590 |
| `K_AMB_CONDENSER_PRESSURE` | 1.625 PSI/°F | R-134a sat curve × CT approach gain |
| `K_AMB_SUCTION_PRESSURE` | 0.15 PSI/°F | Evaporator load sensitivity |
| `T_AMB_HEALTHY_MAX` | 95.0°F | Operational comfort ceiling |
| `T_AMB_CRITICAL` | 130.0°F | Extreme heatwave / rooftop radiant |

### 2.2 Cascading Integration Path

```
ambient_temp (payload)
    │
    ▼
compute_ambient_condenser_penalty()
    │
    ├──► P_discharge_eff = P_discharge + ΔP_discharge  (clamped ≤599 PSI)
    ├──► P_suction_eff   = P_suction   + ΔP_suction    (clamped ≤199 PSI)
    │    └──► Defence: Ps_eff < Pd_eff - 5 enforced
    │
    ▼
compute_compression_ratio(Ps_eff, Pd_eff)     ← RATIO INCREASES
    │
    ├──► compute_volumetric_efficiency(ratio)  ← η_v DECREASES
    │        │
    │        ▼
    │    compute_mass_flow_rate(η_v)            ← ṁ DECREASES slightly
    │
    ├──► compute_discharge_temp_physics(Ts, ratio, k, η_is)  ← T_d INCREASES
    │
    ├──► compute_power_draw_physics(Ts, ratio, η_is, ṁ)      ← W INCREASES
    │        │
    │        ▼
    │    compute_vibration_rms_physics(W, D)                   ← v_rms INCREASES
    │
    ▼
σ_amb = normalised_deviation(T_amb, 95°F, 130°F)              ← DIRECT RISK
    │
    ▼
risk_score = 0.35·σ_v + 0.22·σ_t + 0.18·σ_p + 0.13·σ_o + 0.12·σ_amb
```

**Key insight:** The ambient penalty has **dual amplification** — it both:
1. **Indirectly** elevates risk through cascading thermodynamic effects (higher ratio → higher T_d, W, v_rms → higher σ_t, σ_p, σ_v)
2. **Directly** contributes to risk via its own `σ_amb × W_AMBIENT` term

### 2.3 Weight Vector Rebalancing (Final)

| Factor | Previous | Current | Δ |
|--------|:---:|:---:|:---:|
| Vibration (σ_v) | 0.40 | 0.35 | -0.05 |
| Temperature (σ_t) | 0.25 | 0.22 | -0.03 |
| Power (σ_p) | 0.20 | 0.18 | -0.02 |
| Oil (σ_o) | 0.15 | 0.13 | -0.02 |
| **Ambient (σ_amb)** | **—** | **0.12** | **+0.12** |
| **Total** | **1.00** | **1.00** | **0.00** |

---

## 3. Context-Aware Alert System — Updated Driver Matrix

The alert system now recognises **5 distinct failure mode drivers**:

| Driver | Trigger Condition | Example Alert Prefix |
|--------|------------------|---------------------|
| Bearing Vibration Critical | σ_v is dominant | "⚠️ HIGH RISK: Bearing Vibration Critical..." |
| Thermal Circuit Overload | σ_t is dominant | "⚠️ CRITICAL RISK: Thermal Circuit Overload..." |
| Compressor Overload | σ_p is dominant | "⚠️ HIGH RISK: Compressor Overload..." |
| Lubrication System Degradation | σ_o is dominant | "⚠️ HIGH RISK: Lubrication System Degradation..." |
| **Environmental Heat Stress** | **σ_amb is dominant** | **"⚠️ HIGH RISK: Environmental Heat Stress — ambient at 118.5°F (design: 75.0°F)..."** |

---

## 4. Defensive Boundary Safeguards

| Guard | Location | Protection |
|-------|----------|------------|
| `P_discharge_eff ≤ 599.0` | Step 0 | Prevents ambient penalty from breaching schema `le=600` |
| `P_suction_eff ≤ 199.0` | Step 0 | Prevents ambient penalty from breaching schema `le=200` |
| `Ps_eff < Pd_eff - 5.0` | Step 0 | Maintains thermodynamic cycle validity after penalty |
| `ratio ≥ 1.01` | `compute_compression_ratio()` | Prevents division by zero |
| `η_v ∈ [0.10, 1.0]` | `compute_volumetric_efficiency()` | Prevents zero/negative flow |
| `T_d ∈ [32, 399]°F` | `compute_discharge_temp_physics()` | Schema compliance |
| `W ∈ [0, 1499] kW` | `compute_power_draw_physics()` | Schema compliance |
| `v_rms ∈ [0.1, 499] mm/s` | `compute_vibration_rms_physics()` | Schema compliance |
| `P_oil ∈ [1.0, 199] PSI` | `compute_oil_pressure_physics()` | Schema compliance |
| `risk_score ∈ [0.0, 1.0]` | Step 12 + `_validate_outputs()` | Final clamp + assertion |
| Cold-side floor: `max(T_amb - T_design, 0)` | `compute_ambient_condenser_penalty()` | Zero penalty below design temp |

---

## 5. Housekeeping Resolutions

| Diagnostic | Resolution |
|-----------|------------|
| **A1** | Health endpoint now reads `"Physics Engine (Thermodynamic Digital Twin)"` |
| **A2** | Orphaned `ISO_10816_VIBRATION_THRESHOLD_MMS` removed from main.py |
| **A3** | Stale docstrings rewritten — references "Physics Engine Fallback" and "Model Mode (ML Inference)" |

---

## 6. Verification Readiness Statement

The codebase is **primed for the dedicated Rigorous Testing Phase** targeting:

1. **Extreme Heatwave Simulation** — ambient at 110–140°F
2. **Cold Ambient Baseline** — ambient at 40–75°F (zero penalty verification)
3. **Compound Stress** — high ambient × high runtime_hours
4. **Boundary Overflow Probes** — schema limit payloads
5. **Database Log Verification** — persisted risk scores reflect physics model
6. **Alert Content Verification** — correct driver surfaces per σ dominance
