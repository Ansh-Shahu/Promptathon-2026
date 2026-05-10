# HVAC Compressor Fleet - Deep Data Analysis & Generation Prompt

## 📊 DEEP DATA ANALYSIS

### 1. **Dataset Overview**
- **Total Compressors**: 15 active units
- **Geographic Distribution**: 5 sectors
- **Status Breakdown**: 12 Normal, 2 Critical, 1 Damaged (0 Warning after cleanup)
- **Models**: Carrier brand (30XA, 30HXC, 06T, 30RB, 30XW, 30MPA, 06N, 19DV, 30XV, 23RV, AquaForce, 30KAV, 30CX variations)
- **Data Collection Date**: May 2026

### 2. **Compressor Fleet Composition**

#### By Sector Distribution
- **Commercial**: 3 units (20%) - Mall, Buildings A & B
- **Industrial**: 3 units (20%) - Manufacturing, Warehouse, Plant Floor
- **Residential**: 2 units (13%) - Tower, Hotel
- **Data Center**: 4 units (27%) - Server rooms, Data halls, Omega
- **Healthcare**: 3 units (20%) - Hospital, Clinics

#### By Location Types
- Rooftops, Basements, Server Rooms, Warehouses, Plant Floors
- Buildings, Towers, Hospitals, Hotels, Data Centers, Malls, Manufacturing Facilities

### 3. **Sensor Data Patterns & Ranges**

#### Temperature (°F)
- **Normal Status**: 68-75°F (optimal range)
- **Warning Status**: 75-80°F (elevated)
- **Critical Status**: 85-88°F (dangerous)
- **Damaged Status**: 78-81°F (degraded)
- **Safe Range**: 65-75°F (AI predicted optimal)
- **Formula Pattern**: Higher runtime/lower efficiency → higher temperature

#### Vibration (mm/s)
- **Normal Status**: 1.0-2.9 mm/s (healthy)
- **Warning Status**: 2.8-3.1 mm/s (bearing wear)
- **Critical Status**: 3.9-4.2 mm/s (imminent failure)
- **Damaged Status**: 3.1 mm/s (degraded bearing)
- **Critical Threshold**: >3.5 mm/s
- **Warning Threshold**: 2.5-3.5 mm/s
- **Optimal Range**: <2.0 mm/s

#### Pressure (PSI)
- **Normal Status**: 125-135 PSI (optimal)
- **Critical Status**: 110-112 PSI (failed/low)
- **Damaged Status**: 118 PSI (degraded)
- **Safe Range**: 125-140 PSI
- **Low Pressure = Bad**: Indicates refrigerant leak or compressor failure

#### Power Draw (kW)
- **Small Units**: 32-45 kW (residential/healthcare)
- **Medium Units**: 48-70 kW (commercial/data center)
- **Large Units**: 85-95 kW (industrial/hospital)
- **Efficiency Impact**: Higher power draw with lower efficiency = problems
- **Range Observed**: 32.5-95.0 kW

#### Efficiency (%)
- **Excellent**: >96% (premium models CMP-006, CMP-004, CMP-013)
- **Good**: 92-96% (most commercial units)
- **Fair**: 85-92% (industrial/older units)
- **Poor**: <85% (critical/damaged units)
- **Correlation**: Efficiency ↓ indicates bearing wear, refrigerant loss, or inefficient load

#### Runtime (hours)
- **Low**: <5,000 hours (newer units or light duty)
- **Medium**: 5,000-10,000 hours (standard operation)
- **High**: 10,000-15,000 hours (heavy duty, industrial)
- **Pattern**: Industrial > Data Center > Commercial > Healthcare > Residential

### 4. **Status Correlation Matrix**

| Status | Temp | Vibration | Pressure | Efficiency | Runtime | Critical Indicator |
|--------|------|-----------|----------|------------|---------|-------------------|
| Normal | 68-75 | 1.0-2.0 | 128-135 | 92-98% | 2-15k | None |
| Critical | 85-88 | 3.9-4.2 | 110-112 | 78-82% | 12-14k | Multiple failures |
| Damaged | 78-81 | 3.1 | 118 | 85.7% | 9.8k | Physical damage |

### 5. **Maintenance Cycles**

#### Pattern Analysis
- **Interval**: Typically 3 months (90 days)
- **Format**: MM-DD dates in 2026
- **Scheduling**: Last maintenance → Next maintenance (future date)
- **Emergency Units**: Overdue maintenance (old dates like 2025-10-20, 2025-11-10)
- **Predictive**: Next maintenance scheduled before predicted failure

### 6. **Model Distribution**
- **Primary Brand**: Carrier (all units)
- **Model Types**:
  - Screw Compressors (30XA, 30HXC, 30XW, 23RV, 30KAV, 30CX)
  - Reciprocating (06T, 06N)
  - Centrifugal (19DV)
  - Specialty (30RB, 30MPA, 30XV, AquaForce)

### 7. **Sensor & Alert Generation Patterns**

#### Symptoms (6 active)
- Abnormal vibration patterns (high confidence 90%+)
- Pressure threshold violations
- Temperature anomalies
- Bearing wear signatures (FFT analysis)
- Oil pressure fluctuations
- Power draw overages

#### Alerts (4 types)
- **Predictive**: AI failure probability
- **Threshold**: Sensor breach
- **Anomaly**: ML-detected irregular patterns
- **Status**: Acknowledged vs. Unacknowledged

### 8. **Ticket & Maintenance Insights**

#### Cost Estimation Formula
- Emergency repairs: ₹4,500-₹8,200 (bearing replacement)
- Preventive maintenance: ₹450-₹2,100 (adjustments/lubrication)
- Sensor calibration: ₹450
- Inspections: ₹850

#### Assignment Pattern
- Senior Technicians: Critical/Emergency jobs
- Mid-level Technicians: Medium priority
- Specialists: Specific sensor/bearing work

#### Time-to-Resolution
- Critical: 0-2 hours (emergency shutdown)
- High: 1-3 days
- Medium: 2-5 days
- Low: 5-14 days

---

## 🤖 ALL-ROUNDER DATA GENERATION PROMPT

```
You are a data generation specialist for HVAC compressor fleet monitoring systems.
Generate a realistic and comprehensive compressor fleet dataset following these specifications:

### DATASET PARAMETERS

**Total Compressors**: [USER_DEFINED, default 15-20]

**Sectors** (distribute evenly):
- Commercial (20%)
- Industrial (20%)
- Residential (13%)
- Data Center (27%)
- Healthcare (20%)

**Status Distribution** (realistic breakdown):
- Normal: 70-80%
- Critical: 10-15%
- Damaged: 5-10%
- Warning: 0-5% (optional)

### COMPRESSOR ENTITY STRUCTURE

Generate each compressor with:

1. **Identification**
   - id: CMP-[000-999] (unique, sequential)
   - name: [Carrier Brand] [Model] [Variant]
   - model: Carrier [Series]
   - sector: One of [Commercial, Industrial, Residential, Data Center, Healthcare]

2. **Location** (realistic, sector-specific)
   - Commercial: "Building [A-Z] — [Rooftop/Basement/Floor 1-5]", "Mall Complex Roof", "Logistics Hub"
   - Industrial: "Plant Floor [A-C, 1-3]", "Manufacturing Plant", "Warehouse — [Wing/Section]"
   - Residential: "Tower [A-Z] — [Rooftop/Penthouse/Basement]", "Hotel [Name]", "Apartment Complex"
   - Data Center: "Data Hall [Codename]", "Server Room [Letter]", "Data Center [Name]"
   - Healthcare: "Hospital [Building/Wing]", "Clinic [Name/Annex]", "Medical Center — [Floor]"

3. **Status & Health Metrics** (correlated)
   ```
   For NORMAL status:
   - temperature: 65-75°F (normally 68-72)
   - vibration: 1.0-2.5 mm/s (low variation)
   - pressure: 128-135 PSI (stable)
   - efficiency: 92-98% (high)
   - runtime: 2,000-15,000 hours (varied)
   - Ensure: temp + vibration + pressure align (all low/normal)

   For CRITICAL status:
   - temperature: 84-89°F (high, strained)
   - vibration: 3.7-4.5 mm/s (high, dangerous)
   - pressure: 108-115 PSI (low, failing)
   - efficiency: 75-82% (poor)
   - runtime: 10,000-15,000 hours (long, worn)
   - Ensure: ALL metrics indicate failure (hot + shaky + low pressure + inefficient)

   For DAMAGED status:
   - temperature: 78-83°F (moderately elevated)
   - vibration: 2.8-3.3 mm/s (bearing wear)
   - pressure: 115-122 PSI (low-normal range)
   - efficiency: 84-88% (degraded)
   - runtime: 7,000-11,000 hours (moderate-high)
   - Ensure: Physical damage signature (temp+vibration elevated, pressure compromised)

   For WARNING status (optional):
   - temperature: 75-80°F (slightly elevated)
   - vibration: 2.5-3.2 mm/s (approaching threshold)
   - pressure: 120-128 PSI (borderline)
   - efficiency: 86-94% (fair to good)
   - runtime: 6,000-12,000 hours
   - Ensure: Early warning signs (one or two metrics slightly off)
   ```

4. **Power Draw (kW)** (sector & model-specific)
   - Healthcare/Residential Small: 30-45 kW
   - Commercial/Retail: 45-65 kW
   - Data Center: 55-75 kW
   - Industrial: 60-95 kW
   - Correlation: (powerDraw inversely correlates with efficiency when status is poor)

5. **Maintenance Dates** (ISO 8601 format: YYYY-MM-DD)
   - lastMaintenance: Random date in last 6 months (2025-10 to 2026-04)
   - nextMaintenance: Always 3 months after last maintenance
   - Critical units: nextMaintenance should be OVERDUE (past date) if status is critical
   - Pattern: Predictive = schedule maintenance before predicted failure
   - Example: lastMaintenance: "2026-03-15" → nextMaintenance: "2026-06-15"

### SENSOR DATA GENERATION

**Temperature Patterns**:
- If status = Normal AND sector = Data Center: bias toward 68-72°F (tight control)
- If status = Critical: ensure >84°F
- If sector = Industrial: +2-4°F higher (harder work)
- Add realistic ±1-2°F variance

**Vibration Patterns**:
- Normal = 1.0-2.0: steady, low frequency
- Bearing wear = 2.5-3.0: increasing but controlled
- Critical = 3.8-4.2: chaotic, multiple frequencies
- Industrial units naturally higher than healthcare

**Pressure Signatures**:
- Normal = 130±5 PSI (stable)
- Low pressure = indicator of refrigerant leak or failing compressor
- Never mix high-efficiency with very low pressure (contradicts physics)

**Efficiency Calculation**:
- Formula: 100 - ((temperature - 70) * 0.5 + (vibration - 1.5) * 5 + (130 - pressure) * 0.3 + random variance)
- Clamp to 70-99% range
- Verify: Higher runtime generally = lower efficiency (wear pattern)

**Runtime Logic**:
- Healthcare/Residential: 2,000-8,000 hours (lighter duty)
- Commercial: 5,000-12,000 hours (standard)
- Data Center: 4,000-10,000 hours (high control)
- Industrial: 8,000-15,000 hours (heavy duty)
- Correlation: Long runtime + poor metrics = critical/damaged

### DERIVED DATA (Symptoms, Alerts, Tickets)

**For each CRITICAL compressor, generate**:
- 2 detected symptoms (high confidence >85%, critical severity)
- 1-2 active alerts (predictive or threshold type)
- 1 open or in-progress ticket (priority = critical, cost >₹4,000)

**For each DAMAGED compressor, generate**:
- 1-2 symptoms (bearing wear, temperature elevation)
- 1 alert (threshold or anomaly type)
- 1 emergency ticket auto-raised

**For each NORMAL compressor, generate**:
- 0-1 symptom (optional, low confidence <50%)
- 0 unacknowledged alerts (or 1 old acknowledged alert)
- 0-1 resolved maintenance ticket

**Ticket Metadata**:
- id: MT-[4000-5000] (sequential)
- createdAt: Recent dates (last 14 days)
- priority: "critical" for status=Critical/Damaged, else "medium"/"low"
- costEstimate: ₹450-₹8,200 (scale with severity)
- assignee: Rotate between ["Mike Rivera", "Sarah Chen", "James Park", "Lisa Wong", "Alex Kumar"]

### OUTPUT FORMAT

Generate a TypeScript array of Compressor objects with full correlation:
```typescript
export const compressors: Compressor[] = [
  {
    id: 'CMP-001',
    name: 'Carrier 30XA-252',
    location: 'Building A — Rooftop',
    sector: 'Commercial',
    status: 'Normal',
    temperature: 72,
    vibration: 1.8,
    pressure: 132,
    powerDraw: 45.2,
    runtime: 8420,
    efficiency: 94.2,
    lastMaintenance: '2026-03-15',
    nextMaintenance: '2026-06-15',
    model: 'Carrier 30XA',
  },
  // ... more units
]
```

### VALIDATION RULES

✓ All 5 sectors represented proportionally
✓ No impossible combinations (e.g., high efficiency + critical status)
✓ Temperature, vibration, pressure align with status
✓ Runtime correlates with efficiency decline
✓ Maintenance dates are logical (3-month intervals, no circular dates)
✓ Power draw matches sector/model appropriately
✓ At least 1 critical and 1 damaged unit in fleet
✓ Unique IDs and locations for all compressors
✓ Dates in 2026 only (current year in dataset)

### CUSTOMIZATION OPTIONS

Users can specify:
- Fleet size: 10-50 compressors
- Status distribution: % Normal, % Critical, % Damaged, % Warning
- Sector focus: All vs. single sector emphasis
- Severity level: Healthy fleet (mostly normal) vs. Challenged fleet (more critical/damaged)
- Realism level: Balanced (realistic patterns) vs. Extreme (push boundaries)
- Geographic region: Customize location naming (US, UK, EU, Asia, etc.)

### NOTES FOR DATA GENERATION

1. **Realistic Degradation**: Units don't jump from Normal → Critical overnight. Use intermediate states.
2. **Sector Realism**: Data centers are over-cooled (68°F), industrial is hot (75°F+).
3. **Model Variations**: Carrier models have real-world performance profiles (research if needed).
4. **Maintenance Gaps**: Overdue maintenance → higher probability of Critical/Damaged status.
5. **Stochastic Variation**: Add ±5% random noise to all continuous values (except dates, status).
6. **Coherence**: If generating alerts/symptoms, ensure they match compressor status and sensor readings.
```

---

## 📋 QUICK REFERENCE: DATA ELEMENT CORRELATIONS

### Status Transition Probabilities
```
Normal → Critical: Triggered by (temp >84°F AND vibration >3.5) OR pressure <115
Normal → Damaged: Sudden mechanical failure (all metrics degrade simultaneously)
Normal → Warning: Gradual degradation (temp 75-80, vibration 2.5-3.0)
```

### Sector Performance Baseline
```
Healthcare: Highest efficiency (95-98%), lowest power draw, tight temperature control
Data Center: High efficiency (93-97%), controlled power, precise pressure
Commercial: Medium efficiency (90-95%), moderate power
Residential: Varies (86-98%), lower power draw
Industrial: Lower efficiency (85-92%), high power draw, higher vibration tolerance
```

### Maintenance Cost Ranges
```
Routine check: ₹450-₹1,000
Bearing replacement: ₹4,500-₹8,200
Sensor calibration: ₹450-₹800
Refrigerant recharge: ₹1,200-₹2,500
Emergency repair: ₹2,000-₹6,500
```

---

## 🎯 USE CASES FOR THIS DATA

1. **Dashboard Testing**: Realistic fleet scenarios
2. **ML Model Training**: Sensor data with known outcomes (status)
3. **Alert Tuning**: Threshold calibration and false positive reduction
4. **Capacity Planning**: Load distribution across sectors
5. **Cost Forecasting**: Maintenance budget estimation
6. **Predictive Analytics**: Failure prediction model validation

---

**Generated**: May 4, 2026  
**Fleet ID**: PROMTATHON-V1  
**Data Version**: 1.0
