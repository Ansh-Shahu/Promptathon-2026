# HVAC Digital Twin — Thermal Ambient Penalty Blueprint

> **Author:** Antigravity AI Agent  
> **Date:** 2026-07-17  
> **Status:** ⏸️ AWAITING HUMAN APPROVAL — No code will be modified until authorised.

---

## 1. Discovery: The Ambient Gap

### Current State

The `ambient_temp` field is:
- ✅ Extracted from the payload in `compute_risk_from_payload()` (line 617)
- ✅ Stored as a variable (`ambient_temp: float`)
- ❌ **Never consumed by any downstream calculation**
- ❌ Not fed into compression ratio, discharge pressure, volumetric efficiency, power draw, or risk score

This means that two identical sensor readings — one at 65°F ambient and one at 120°F ambient — produce **identical risk scores**. In reality, a heatwave at 120°F would increase condenser saturation pressure by ~40-60 PSI, increase the compression ratio by 15-25%, degrade volumetric efficiency, spike power draw by 20-30%, and elevate discharge temperature by 20-40°F. The current engine is completely blind to this.

### Data Lineage of `ambient_temp`

```
simulate_pf_curve_data.py → diurnal sine wave: 75 ± 10°F with σ=1.5°F noise
        │
        ▼
hvac_sensor_data.csv → column "ambient_temp" (65–85°F range)
        │
        ▼
client_simulator.py → build_payload() → float(row["ambient_temp"])
        │
        ▼
POST /api/v1/predict → schemas.py::SensorPayload.ambient_temp (ge=-60, le=140)
        │
        ▼
main.py → payload.model_dump() → physics_engine.compute_risk_from_payload()
        │
        ▼
physics_engine.py line 617: ambient_temp = float(payload_dict["ambient_temp"])
        │
        ▼ 🚫 DEAD END — variable is assigned but never read by any function
```

---

## 2. Mathematical Formulations — Ambient Penalty Model

### 2.1 Physical Mechanism: Condenser Heat Rejection

In a water-cooled centrifugal chiller, the condenser must reject the sum of evaporator load + compressor work to the cooling tower water. The cooling tower's heat rejection capacity is bounded by the ambient wet-bulb temperature. As ambient dry-bulb temperature rises:

1. **Condenser water return temperature rises** → condenser saturation temperature rises
2. **Condenser saturation pressure (R-134a) rises** → discharge pressure increases
3. **Compression ratio increases** → volumetric efficiency drops, discharge temp rises, power draw increases
4. **All cascading effects amplify the risk score**

### 2.2 Condenser Pressure Penalty — Antoine-Derived Approximation

For R-134a, the saturation pressure-temperature relationship can be approximated using a linearised Antoine correlation within the operating range:

$$P_{condenser}(T_{amb}) = P_{condenser,design} + K_{amb} \cdot \max(0, T_{amb} - T_{amb,design})$$

Where:
- `P_condenser,design = 172 PSI` (discharge pressure at design ambient 75°F)  
- `T_amb,design = 75.0°F` (ARI 550/590 standard rating condition)
- `K_amb` = ambient-to-pressure sensitivity coefficient

**Deriving K_amb from R-134a properties:**

The R-134a saturation curve slope at condenser conditions (~105°F sat temp) is approximately 2.5 PSI/°F. With a typical cooling tower approach of 7°F and condenser approach of 5°F, the effective transmission gain from ambient to condenser is ~0.65:

$$K_{amb} = 2.5 \times 0.65 = 1.625 \text{ PSI/°F}$$

So at 120°F ambient (45°F above design):

$$\Delta P = 1.625 \times 45 = 73.1 \text{ PSI}$$
$$P_{discharge} = 172 + 73.1 = 245.1 \text{ PSI}$$

This is physically realistic — well within the schema's 600 PSI upper bound and consistent with field data from rooftop chiller installations.

### 2.3 Suction Pressure Penalty

As ambient temperature rises, the evaporator load increases slightly (building cooling load grows). This causes a minor suction pressure rise:

$$P_{suction}(T_{amb}) = P_{suction,raw} + K_{suction} \cdot \max(0, T_{amb} - T_{amb,design})$$

Where `K_suction = 0.15 PSI/°F` (much smaller than condenser effect — evaporator is indoors and buffered by the building's thermal mass).

### 2.4 Cascading Integration into Existing Functions

The ambient penalty does NOT require new functions. It modifies the **inputs** to existing functions:

```
ambient_temp
    │
    ├──► compute_ambient_condenser_penalty(ambient_temp)
    │       Returns: (delta_p_discharge, delta_p_suction)
    │
    ├──► Effective discharge_press += delta_p_discharge
    ├──► Effective suction_press += delta_p_suction  (minor)
    │
    └──► These modified pressures flow into the EXISTING pipeline:
            compute_compression_ratio(p_suction_eff, p_discharge_eff)
                → compute_volumetric_efficiency(ratio)
                    → compute_mass_flow_rate(eta_v)
                        → compute_power_draw_physics(...)
                            → compute_vibration_rms_physics(...)
                                → risk score (automatically elevated)
```

### 2.5 Ambient Contribution to Risk Score

The ambient penalty also introduces a **5th normalised deviation factor** for environmental stress:

$$\sigma_{amb} = \text{clamp}\left(\frac{T_{amb} - T_{amb,healthy\_max}}{T_{amb,critical} - T_{amb,healthy\_max}}, 0, 1\right)$$

Where `T_amb,healthy_max = 95°F` and `T_amb,critical = 130°F`.

**Updated risk weight vector:**

| Factor | Old Weight | New Weight | Rationale |
|--------|-----------|------------|-----------|
| Vibration | 0.40 | 0.35 | Still dominant P-F indicator |
| Temperature | 0.25 | 0.22 | Slightly reduced to make room |
| Power | 0.20 | 0.18 | Slightly reduced |
| Oil | 0.15 | 0.13 | Slightly reduced |
| **Ambient** | **—** | **0.12** | **New environmental stress factor** |
| **Total** | 1.00 | 1.00 | Normalised |

### 2.6 Context-Aware Alert — Ambient Branch

When `sigma_amb` is the dominant driver, the alert system will produce:

> ⚠️ HIGH RISK (78%): Environmental Heat Stress — ambient temperature at 118.5°F (design: 75°F). Contributing factors: power draw at 412.3 kW. Recommended action: activate auxiliary condenser fan staging and verify cooling tower water flow. Schedule maintenance within 72 hours.

---

## 3. Architecture & State Justification

### No New Dependencies Required

The ambient penalty uses simple linear and polynomial arithmetic. No CoolProp, no scipy. Pure `math` stdlib is sufficient.

### Stateless Architecture Preserved

The ambient penalty is a pure function of the current payload's `ambient_temp` field. No historical state, no moving averages, no thermal inertia tracking. Each request remains fully independent.

### Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/physics_engine.py` | **MODIFY** | Add `compute_ambient_condenser_penalty()` function; integrate pressure adjustments into `compute_risk_from_payload()`; add `sigma_amb` to risk score; add ambient alert branch; update weight constants |
| `backend/main.py` | **MODIFY** | Update health endpoint's fallback `prediction_mode` string from `"Mock Mode (ISO 10816 Heuristic)"` to `"Physics Engine (Thermodynamic Digital Twin)"` |

### Files NOT Modified

| File | Reason |
|------|--------|
| `schemas.py` | All ambient-penalized outputs stay within existing bounds |
| `models.py` | No new ORM columns |
| `crud.py` | No CRUD changes |
| `database.py` | No session changes |
| `requirements.txt` | No new dependencies |

---

## 4. Passive Diagnostic Report — Secondary Issues Identified

> ⚠️ These are **read-only diagnostics**. No code changes will be made for these items.

### 4.1 Unmodeled Thermodynamic Phenomena

| # | Phenomenon | Severity | Description |
|---|-----------|----------|-------------|
| D1 | **Compressor Short-Cycling** | Medium | Rapid on/off cycling causes liquid slugging and thermal shock. Not modeled — would require stateful tracking of start/stop events. |
| D2 | **Refrigerant Undercharge** | Medium | Low refrigerant charge reduces suction pressure, increases superheat, and degrades capacity. Currently the engine assumes full charge. |
| D3 | **Psychrometric / Humidity Impact** | Low | Cooling tower performance degrades at high humidity (wet-bulb approaches dry-bulb). The engine uses dry-bulb only, which is conservative but not maximally accurate. |
| D4 | **Condenser Fouling** | Medium | Scale buildup on condenser tubes increases approach temperature. Would need a fouling factor that degrades with runtime. Currently unmodeled. |
| D5 | **Variable Frequency Drive (VFD) Effects** | Low | Modern chillers modulate compressor RPM. The engine assumes fixed 3600 RPM. |
| D6 | **Part-Load Performance** | Low | At partial cooling loads, the chiller operates at different efficiency curves. The engine assumes full-load operation. |

### 4.2 Architectural Observations

| # | Issue | Impact | Location |
|---|-------|--------|----------|
| A1 | **Health endpoint still says "Mock Mode (ISO 10816 Heuristic)"** | Misleading — the physics engine replaced the heuristic in the previous sprint | `main.py` L442-446 |
| A2 | **`ISO_10816_VIBRATION_THRESHOLD_MMS` constant is orphaned in main.py** | The threshold was consumed by the deleted RNG branch. It is still referenced in the module-level docstring but not by any executable code in `main.py`. The physics engine has its own `ISO_10816_THRESHOLD` constant. | `main.py` L104-105 |
| A3 | **Dual-docstring anachronism in `_predict()`** | The `_predict()` docstring (L288-307) and the route handler docstring (L504-535) both reference "mock mode" and `_mock_predict()` which no longer exist. | `main.py` L288, L521-528 |

---

## 5. Implementation Checklist

### `physics_engine.py` Modifications

- [ ] Add ambient design-point constants (`T_AMB_DESIGN`, `K_AMB_PRESSURE`, `K_SUCTION_PRESSURE`)
- [ ] Add `compute_ambient_condenser_penalty(ambient_temp)` function
- [ ] Add `W_AMBIENT` weight constant, re-balance existing weights to sum to 1.0
- [ ] In `compute_risk_from_payload()`: inject pressure adjustments BEFORE compression ratio calculation
- [ ] In `compute_risk_from_payload()`: compute `sigma_amb` normalised deviation
- [ ] In `compute_risk_from_payload()`: add `W_AMBIENT * sigma_amb` to risk score
- [ ] In `_build_dynamic_alert()`: add ambient driver tuple to the alert system
- [ ] Update module docstring to document ambient penalty

### `main.py` Modifications

- [ ] Update prediction_mode string in health endpoint
- [ ] Remove orphaned `ISO_10816_VIBRATION_THRESHOLD_MMS` constant
- [ ] Update stale docstrings referencing "mock mode"

---

> ### 🛑 EXECUTION HALTED
> 
> Blueprint and diagnostic report are complete. Awaiting explicit human authorisation before proceeding to Phase 3 (code modification).
