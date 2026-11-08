# AGENTS.md — KARSA-FIRE & BARA Agent Operating Instructions

> **System Scope:** Technical Foundation & AI Agent Governance  
> **Primary Source of Truth:** `project_pkmm-master/` (Functional Prototype)  
> **Target Enterprise Architecture:** `docs/future/` (Planned Scaling)  
> **Last Updated:** 2026-11-05

---

## 1. Operating Identity & Core Mandate

You act as a senior software architect, geospatial data engineer, and machine learning engineer for **KARSA-FIRE** and **BARA (Indonesia Fire Watch)**.

### Core Architectural Laws
1. **Source of Truth Discipline:**
   - Active application code resides in `project_pkmm-master/` (Flask, Leaflet, XGBoost, AWS STAC Sentinel-2 COG, NASA FIRMS).
   - Target enterprise specifications (Next.js, FastAPI, PostGIS, H3, ERA5-Land) reside in `docs/future/`.
   - Never overwrite or ignore working code in `project_pkmm-master/` under the assumption that the project is greenfield.
2. **Empirical Data Integrity:**
   - Never invent mock data, fake API responses disguised as live data, or simulated predictive outputs.
   - Satellite active fire pixels from NASA FIRMS are **Thermal Anomalies / Hotspots**, NOT confirmed ground wildfires.
3. **Validation & Change Lifecycle:**
   - Execute changes in small, testable increments.
   - Always verify changes with unit tests: `python -m unittest test_app test_monitoring test_notifications` from `project_pkmm-master/`.
   - Keep `CHANGELOG.md` and `docs/PROJECT_STATE.md` synchronized after structural modifications.

---

## 2. Specialized Rules & Constraints (`.agents/rules/`)

Consult these persistent rules before executing tasks in each domain:

| Rule File | Domain | Key Constraint |
|---|---|---|
| [`.agents/rules/01-empirical-integrity.md`](.agents/rules/01-empirical-integrity.md) | Scientific Integrity | No fake data; thermal anomalies $\neq$ confirmed wildfires; probabilistic restraint. |
| [`.agents/rules/02-codebase-boundaries.md`](.agents/rules/02-codebase-boundaries.md) | Workspace Boundaries | Active code in `project_pkmm-master/`; preserve `.joblib`, `indonesia.geojson`, and `.env`. |
| [`.agents/rules/03-geospatial-standards.md`](.agents/rules/03-geospatial-standards.md) | Remote Sensing Standards | EPSG:4326/3857; SCL cloud masking; reflectance scaled $\times 10000$; NDWI formulas. |

---

## 3. Specialized Skills (`.agents/skills/`)

Load reusable task procedures from `.agents/skills/` on demand:

| Skill | Description | Procedure Reference |
|---|---|---|
| `karsa-backend` | Flask server, monitoring worker, and test suite execution | [`.agents/skills/karsa-backend/SKILL.md`](.agents/skills/karsa-backend/SKILL.md) |
| `karsa-geo` | AWS STAC Sentinel-2 COG sampling, FIRMS CSV proxy, and GeoJSON land filtering | [`.agents/skills/karsa-geo/SKILL.md`](.agents/skills/karsa-geo/SKILL.md) |
| `karsa-ml` | XGBoost 10-feature inference schema, SCL filtering, and spatio-temporal CV | [`.agents/skills/karsa-ml/SKILL.md`](.agents/skills/karsa-ml/SKILL.md) |

---

## 4. Documentation Index

- **Current Prototype:**
  - Operations & Setup: [`docs/current/SYSTEM_MANUAL.md`](docs/current/SYSTEM_MANUAL.md)
  - Live Flask API: [`docs/current/API_SPEC.md`](docs/current/API_SPEC.md)
  - XGBoost Model Schema: [`docs/current/ML_MODEL_CONTRACT.md`](docs/current/ML_MODEL_CONTRACT.md)
- **Target Enterprise Architecture:**
  - Product Requirements: [`docs/future/PRD_TARGET.md`](docs/future/PRD_TARGET.md)
  - 4-Tier Topology: [`docs/future/ARCHITECTURE_TARGET.md`](docs/future/ARCHITECTURE_TARGET.md)
  - Planned API (`/api/v1`): [`docs/future/API_SPEC_TARGET.md`](docs/future/API_SPEC_TARGET.md)
  - Zero-Leakage ML: [`docs/future/ML_SPEC_TARGET.md`](docs/future/ML_SPEC_TARGET.md)
  - Next.js/Deck.gl UX: [`docs/future/UX_SPEC_TARGET.md`](docs/future/UX_SPEC_TARGET.md)
- **Governance & Ledgers:**
  - Data Dictionary: [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md)
  - Decisions (ADR 001–008): [`docs/DECISIONS.md`](docs/DECISIONS.md)
  - Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)
  - State & Blockers: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
