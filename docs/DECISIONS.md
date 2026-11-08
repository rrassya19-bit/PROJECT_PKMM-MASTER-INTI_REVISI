# Architecture Decision Records (ADR) — KARSA-FIRE & BARA

> **Repository:** KARSA-FIRE  
> **Status:** Active  
> **Format:** Modified Michael Nygard ADR Template

---

## Index of Decisions

- [ADR-001: Strict Separation of Foundation Phase (Phase 0) from Feature Implementation](#adr-001-strict-separation-of-foundation-phase-phase-0-from-feature-implementation)
- [ADR-002: Next.js (TypeScript) and Deck.gl / MapLibre GL for Geospatial Client](#adr-002-nextjs-typescript-and-deckgl--maplibre-gl-for-geospatial-client)
- [ADR-003: FastAPI & PostgreSQL/PostGIS for Spatial Vector & Analytics Backend](#adr-003-fastapi--postgresqlpostgis-for-spatial-vector--analytics-backend)
- [ADR-004: Adoption of Uber H3 Hexagonal Discrete Global Grid System (DGGS)](#adr-004-adoption-of-uber-h3-hexagonal-discrete-global-grid-system-dggs)
- [ADR-005: Strict Blocked Spatio-Temporal Validation to Prevent Data Leakage](#adr-005-strict-blocked-spatio-temporal-validation-to-prevent-data-leakage)
- [ADR-006: Explicit Semantic Distinction Between Satellite Thermal Anomalies and Confirmed Wildfires](#adr-006-explicit-semantic-distinction-between-satellite-thermal-anomalies-and-confirmed-wildfires)
- [ADR-007: Open Architectural Decisions Pending User Clarification](#adr-007-open-architectural-decisions-pending-user-clarification)
- [ADR-008: Adoption of Existing Sentinel-2 / CatBoost Prototype as Functional Baseline](#adr-008-adoption-of-existing-sentinel-2--catboost-prototype-as-functional-baseline)

---

## ADR-001: Strict Separation of Foundation Phase (Phase 0) from Feature Implementation

### Status
Accepted

### Context
Geospatial and machine learning systems for natural hazard modeling carry significant risk of premature optimization, data contamination, and ungrounded architectural complexity if development begins before boundaries, validation methodologies, and data contracts are formalized.

### Decision
Enforce a strict Phase 0 (Foundation Only) checkpoint for the target enterprise architecture. No unapproved production code or simulated predictions are implemented until all foundational specifications are authored and reviewed by the project lead.

### Consequences
- **Positive:** Eliminates technical debt, prevents hallucinated metrics, ensures clean workspace preservation.
- **Negative:** Requires initial upfront documentation effort before visual feature demonstration.

---

## ADR-002: Next.js (TypeScript) and Deck.gl / MapLibre GL for Geospatial Client

### Status
Proposed (Target Architecture — Phase 2)

### Context
Rendering tens of thousands of historical thermal anomaly points alongside dynamic hexagonal density grids on a browser map requires hardware-accelerated graphics. Traditional DOM-based mapping libraries (such as Leaflet) choke when rendering $>5,000$ vector elements.

### Decision
Adopt Next.js 14+ (App Router, TypeScript) for the web application shell and Deck.gl paired with MapLibre GL for the mapping canvas in the enterprise phase.

---

## ADR-003: FastAPI & PostgreSQL/PostGIS for Spatial Vector & Analytics Backend

### Status
Proposed (Target Architecture — Phase 1)

### Context
The backend must handle high-volume spatio-temporal queries, bounding-box filtering, vector tile generation (`ST_AsMVT`), and seamless integration with Python-based geospatial and machine learning workflows.

### Decision
Select FastAPI (Python 3.11+) as the REST/Tile API service and PostgreSQL 16 + PostGIS 3.4 as the spatial persistence engine for the enterprise target.

---

## ADR-004: Adoption of Uber H3 Hexagonal Discrete Global Grid System (DGGS)

### Status
Proposed (Target Architecture — Phase 1)

### Context
Raw satellite active-fire observations are point events distributed irregularly in space and time based on orbital swaths. Aggregating these points and harmonizing them with gridded climate reanalysis requires a standardized spatial tessellation.

### Decision
Adopt Uber H3 hexagonal discrete global grid system (Resolution 7 $\approx 5.16\text{ km}^2$ or Resolution 8 $\approx 0.74\text{ km}^2$) as the core analytical and modeling cell unit.

---

## ADR-005: Strict Blocked Spatio-Temporal Validation to Prevent Data Leakage

### Status
Accepted

### Context
Standard random K-fold cross-validation on spatial-temporal data produces severe data leakage due to spatial and temporal autocorrelation, resulting in artificially high model accuracy metrics that fail in real-world deployment.

### Decision
Mandate Purged Blocked Spatio-Temporal Cross Validation:
1. Temporal partitioning: Models must be trained exclusively on historical years and tested on subsequent unseen future years.
2. Spatial partitioning: Geographic regions must be blocked and buffered (no training cells within 50 km of validation cells).
3. 7-day temporal embargo buffer between train and test windows.

---

## ADR-006: Explicit Semantic Distinction Between Satellite Thermal Anomalies and Confirmed Wildfires

### Status
Accepted

### Decision
1. System UI, data dictionaries, and APIs must label raw NASA FIRMS data explicitly as **Thermal Anomalies / Hotspots**, never as "Confirmed Fires".
2. Confidence levels (Low, Nominal, High) must be visibly surfaced.
3. Fire-risk predictions must be explicitly framed as **Fire Hazard / Occurrence Probability**, not certainty.

---

## ADR-007: Open Architectural Decisions Pending User Clarification

### Status
Open (Awaiting User Input)

### Pending Questions:
1. **Pilot Study Area:** What is the approved pilot region for initial data ingestion and model benchmarking? (Options: Riau, South Sumatra, Central Kalimantan, National).
2. **Machine Learning Target & Temporal Horizon:** Operational forecast horizon (24h, 72h, or 7d) and target formulation (binary vs. continuous FRP).
3. **Deployment Strategy:** Local Docker Compose vs. cloud-hosted managed services (AWS / GCP).

---

## ADR-008: Adoption of Existing Sentinel-2 / CatBoost Prototype as Functional Baseline

### Status
Accepted

### Context
A fully functional, tested prototype application (BARA) exists in `project_pkmm-master/`. It executes live AWS STAC Sentinel-2 L2A COG sampling via Rasterio, applies SCL cloud-masking, performs CatBoost inference on 10 spectral features, manages background grid monitoring, and displays an interactive Leaflet frontend.

### Decision
1. Formally adopt `project_pkmm-master/` as the primary functional baseline of the repository.
2. Document current prototype operations in `docs/current/`.
3. Plan the target enterprise architecture (Next.js, FastAPI, PostGIS, H3, ERA5-Land) in `docs/future/` as an evolutionary progression from this baseline.

### Consequences
- **Positive:** Acknowledges existing empirical code and prevents hallucinating that no code exists. Provides immediate local demo and testing capabilities.
- **Negative:** Requires maintaining two clear tiers of documentation until migration is executed.
