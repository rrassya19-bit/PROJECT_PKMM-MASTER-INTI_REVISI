# Product Requirements Document (PRD) — KARSA-FIRE Enterprise Target

> **Document Status:** PLANNED (Target Architecture — Phase 2+)  
> **Target System:** KARSA-FIRE (Geospatial Wildfire & Hotspot Predictive Intelligence)  
> **Baseline Implementation:** Prototype in `project_pkmm-master/` (documented in `docs/current/`)

---

## 1. Problem Statement & Mission

Forest and land fires (karhutla) cause catastrophic ecological, economic, and respiratory health damage across tropical ecosystems and fire-prone landscapes. Existing public monitoring tools frequently present isolated thermal anomalies without comprehensive temporal aggregation, environmental context (soil moisture, rainfall deficits, wind vectors), or calibrated forward-looking predictive risk assessments.

**KARSA-FIRE** provides an integrated geospatial analytics and decision-support platform designed to:
1. Provide intuitive, high-performance exploration of historical thermal anomalies (hotspots) from NASA FIRMS.
2. Deliver spatial-temporal aggregations across administrative boundaries and standardized discrete hexagonal grids (Uber H3).
3. Compute and visualize forward-looking fire-risk scores derived from multi-source environmental covariates.

---

## 2. Requirements Categorization Framework

| Category | Definition |
|---|---|
| **FACT** | Established truth verified against physical/technical constraints or official datasets. |
| **PROPOSAL** | Architecturally reasoned recommendation pending formal user validation. |
| **ASSUMPTION** | Working premise used to design baseline specifications; subject to revision upon user input. |
| **OPEN DECISION** | Unresolved parameter or policy requiring explicit stakeholder determination. |

### 2.1 Verified Facts
- **FACT 1:** NASA FIRMS detects thermal anomalies (active fire pixels) using satellite sensors (MODIS on Terra/Aqua; VIIRS on Suomi-NPP, NOAA-20, NOAA-21).
- **FACT 2:** Satellite thermal anomalies represent radiant heat signatures and do not guarantee an active, ground-confirmed uncontrolled wildfire.
- **FACT 3:** VIIRS 375m spatial resolution provides significantly higher hotspot spatial fidelity than MODIS 1km resolution.
- **FACT 4:** ERA5-Land reanalysis products have an inherent latency (typically 5 days for ERA5T NRT), meaning zero-day real-time weather requires short-term NWP forecasts (e.g., GFS or ECMWF IFS).
- **FACT 5:** CHIRPS rainfall estimates have a 1-2 day to semi-monthly release cycle depending on the preliminary vs. final product tier.

### 2.2 Proposals
- **PROPOSAL 1:** Use Uber H3 resolution 7 (~5.16 km² hexagon area, edge length ~1.22 km) or resolution 8 (~0.74 km², edge length ~461 m) as the standard predictive and aggregation grid cell.
- **PROPOSAL 2:** Construct the client application with Next.js 14 (App Router, TypeScript) and Deck.gl / MapLibre GL for client-side spatial rendering.
- **PROPOSAL 3:** Implement the backend as a modular FastAPI microservice exposing GeoJSON, Mapbox Vector Tiles (MVT), and tabular aggregates backed by PostgreSQL/PostGIS.

### 2.3 Working Assumptions
- **ASSUMPTION 1:** The primary geographic focus is tropical Southeast Asia / Indonesia (specifically high-risk peatland provinces such as Riau, South Sumatra, Central Kalimantan, or West Kalimantan).
- **ASSUMPTION 2:** The target user base possesses basic GIS literacy (understands bounding boxes, time ranges, confidence thresholds, and risk score heatmaps).
- **ASSUMPTION 3:** The user environment supports modern WebGL2-compatible desktop browsers (Chrome, Firefox, Safari, Edge).

### 2.4 Open Decisions
- **DECISION 1:** Approved pilot study area (Specific province vs. national scope).
- **DECISION 2:** ML prediction target formalization (Binary occurrence in cell $c$ over window $t+\Delta t$ vs. continuous FRP density).
- **DECISION 3:** Operational forecast horizon ($\Delta t = 24\text{ hours}$, $72\text{ hours}$, or $7\text{ days}$).
- **DECISION 4:** Production deployment target (Self-hosted on-premise Docker vs. cloud-hosted managed services).

---

## 3. User Personas & Use Cases

### Persona 1: Disaster Management / Environmental Analyst
- **Profile:** GIS specialist or operational analyst at a regional disaster mitigation agency (e.g., BPBD/BNPB or environmental NGO).
- **Goals:** Monitor active hotspots, identify clusters crossing conservation or peatland boundaries, generate weekly historical trend reports, and anticipate high-risk zones for ground patrol deployment.

### Persona 2: Field Patrol Coordinator / Forestry Officer
- **Profile:** Operational team lead allocating patrol and suppression teams in the field.
- **Goals:** Rapidly check which sub-districts or grid cells have high fire-risk probability in the next 24 to 72 hours to stage firefighting equipment proactively.

### Persona 3: Data Science / Climate Researcher
- **Profile:** Quantitative researcher assessing climate trends and model fidelity.
- **Goals:** Access documented feature dictionaries, verify spatio-temporal validation metrics, inspect spatial cross-validation folds, and export clean historical data tables.

---

## 4. Scope & System Boundaries

### 4.1 In-Scope for Minimum Viable Product (MVP)
1. **Historical Hotspot Explorer:** Ingestion of NASA FIRMS active fire data across Indonesia; spatial/temporal filtering; confidence and sensor filtering.
2. **Hexagonal Spatial Aggregation (H3):** On-the-fly and pre-aggregated count/density and cumulative FRP per H3 hexagon.
3. **Fire-Risk Visualization:** Display of fire-hazard risk scores; cell inspection detailing environmental drivers.
4. **Summary Analytics Dashboard:** Time-series charts, regional vulnerability ranking tables, and data export.

### 4.2 Explicitly Out-of-Scope for MVP
- Real-time satellite downlinking or direct ground station telemetry.
- Autonomous dispatch or automated IoT siren/alarm integration.
- Smoke dispersion and atmospheric particulate ($PM_{2.5}$) plume dynamics modeling.
- Native mobile applications (iOS/Android).

---

## 5. Non-Functional Requirements (NFRs)
- **Map Vector Render Latency:** $\le 100\text{ ms}$ frame time when rendering $\le 50,000$ points via Deck.gl / WebGL.
- **Spatial API Response Time:** $\le 400\text{ ms}$ for typical regional aggregation queries.
- **Data Integrity & Traceability:** 100% of displayed points must trace back to raw sensor acquisition timestamp, satellite ID, and coordinates.
- **Accessibility & Design:** WCAG 2.1 Level AA compliance, colorblind-safe palettes.
- **System Availability:** 99.5% uptime during operational testing.

