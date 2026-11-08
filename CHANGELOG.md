# Changelog — KARSA-FIRE & BARA

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-alpha.5] - 2026-11-07

### Added
- **Notification lifecycle completion:**
  - `POST /api/events/<id>/resolve` records `resolved_by`, `resolved_at`, and an optional `resolution_note` without altering notification read state.
  - Notification status accepts `RESOLVED`; the dashboard now supports marking notifications back to `UNREAD`.
  - Notification detail displays resolution metadata.
- **Unlimited retention option:** `NOTIFICATION_MAX_RECORDS=0` and `NOTIFICATION_MAX_EVENTS=0` retain history without pruning.
- **Tests:** resolve workflow, token protection for resolve, UNREAD round-trip, RESOLVED notification status, and zero-limit retention.

### Security
- `VERIFY_TOKEN` now guards both `POST /api/events/<id>/verify` and `POST /api/events/<id>/resolve`.

### Verified
- `./.venv/bin/python -m unittest test_app.py test_monitoring.py test_notifications.py` — 39 tests PASS.
- `node test_frontend.cjs` — all suites PASS (including UNREAD and resolve actions).

---

## [0.1.0-alpha.4] - 2026-11-07

### Added
- **Notification System (N1–N7, MVP in-app):**
  - `notifications.py`: persistent JSON store with atomic writes, event identity/deduplication, severity rules, delivery log, bounded FIRMS background worker.
  - Severity levels `INFO`, `WASPADA`, `DARURAT`; automatic engine is capped at `WASPADA` so XGBoost Class 1 and single FIRMS hotspots can never self-declare an emergency.
  - Authorized `POST /api/events/<id>/verify` escalation to `DARURAT`, optionally protected by `VERIFY_TOKEN`.
  - Notification APIs: list/filter, summary, detail, read, read-all, status, events, and verification.
  - Notification Center drawer in the dashboard with unread badge, severity/status filters, read/acknowledge/dismiss actions, and map deep links.
  - `test_notifications.py` plus extended `test_frontend.cjs` coverage.
- **Configuration:** `WASPADA_MIN_SCORE`, `NOTIFICATION_FIRMS_INTERVAL`, `NOTIFICATION_MAX_RECORDS`, `NOTIFICATION_MAX_EVENTS`, `VERIFY_TOKEN` documented in `.env.example`.
- **Documentation:** Notification endpoint contract in `docs/current/API_SPEC.md`, notification schemas in `docs/DATA_DICTIONARY.md`, and operational notes.

### Changed
- `monitoring.py` now exposes optional `on_update`/`on_cycle` hooks; hook failures are isolated and never stop the monitoring loop.
- FIRMS cache access is serialized with a lock so background polling and request handlers cannot fetch concurrently.
- Active documentation now consistently names the deployed XGBoost model instead of CatBoost.

### Verified
- `./.venv/bin/python -m unittest test_app.py test_monitoring.py test_notifications.py` — 35 tests PASS.
- `node test_frontend.cjs` — all suites PASS (including notification escaping, filtering, and read/acknowledge actions).

---

## [0.1.0-alpha.3] - 2026-11-07

### Fixed
- **macOS Local Run (`project_pkmm-master/`):**
  - Documented and applied the OpenMP workaround for XGBoost: the `libomp.dylib` bundled with scikit-learn is copied into `xgboost/lib/`, with `@loader_path` added via `install_name_tool`. This removes the `xgboost._c_api.XGBoostError` crash on macOS without Homebrew.
- **Environment Configuration:**
  - Added `.env.example`; the active `.env` is now present locally and remains Git-ignored.

### Changed
- **Run Instructions:** `README.md` and `PETUNJUK.md` now describe the macOS virtual-environment workflow (`.venv/bin/python server.py`) and warn against opening `static/index.html` directly.

### Verified
- `python -m unittest test_app test_monitoring` — 16 tests PASS.
- `node test_frontend.cjs` — all frontend suites PASS.
- Live smoke test: `GET /`, `/api/status` (`firms_configured: true`), `/api/boundary`, `/api/hotspots` return HTTP 200.

---

## [0.1.0-alpha.2] - 2026-11-05

### Security & Bug Fixes (UI/UX Stage 1: P0 Criticals)
- **Frontend DOM Protection (`static/app.js`):**
  - Sanitized dynamic string injection on monitor headline and status messages via `escapeHTML()` to eliminate XSS surface.
- **Resource Optimization (`static/app.js`):**
  - Added `document.hidden` guards to background monitor polling (10s) and priority ordering polling (60s) to prevent tab background resource waste and API flooding.
- **Data Integrity & User Communication (`static/app.js`, `static/index.html`):**
  - Added `#tableNotice` banner communicating the 300-row limit on the active hotspot detection table with guidance to download CSV for full datasets.
- **Error State Styling (`static/style.css`, `static/app.js`):**
  - Added `.status-error` visual alert treatment for FIRMS, Sentinel STAC, and background monitor connection failures.

## [0.1.0-alpha.1] - 2026-11-05

### Added
- **Baseline Prototype Documentation (`docs/current/`):**
  - Added `docs/current/SYSTEM_MANUAL.md`: Preserved complete operational manual from `PETUNJUK.md` with English technical executive summary.
  - Added `docs/current/API_SPEC.md`: Formally documented live Flask REST endpoints (`/api/status`, `/api/boundary`, `/api/hotspots`, `/api/predict`, `/api/monitor`, `/api/priorities`).
  - Added `docs/current/ML_MODEL_CONTRACT.md`: Documented CatBoost 10-feature schema, SCL cloud-mask filtering rules, and reflectance scaling factors.
- **Architectural Decision Record (ADR-008):**
  - Formally recorded adoption of existing Sentinel-2 / CatBoost prototype in `project_pkmm-master/` as the functional baseline for KARSA-FIRE.
- **Agent Governance & Customizations (`.agents/`):**
  - Established persistent rules in `.agents/rules/` (`01-empirical-integrity.md`, `02-codebase-boundaries.md`, `03-geospatial-standards.md`).
  - Established reusable skills in `.agents/skills/` (`karsa-backend`, `karsa-geo`, `karsa-ml`).
- **Target Enterprise Specifications (`docs/future/`):**
  - Partitioned future scaling specs into `docs/future/` (`PRD_TARGET.md`, `ARCHITECTURE_TARGET.md`, `API_SPEC_TARGET.md`, `ML_SPEC_TARGET.md`, `UX_SPEC_TARGET.md`).

### Changed
- **Unified Root Instructions (`AGENTS.md`):**
  - Refactored root agent instructions to reflect the active prototype baseline, eliminating false greenfield workspace assumptions and broken `KarsaCipta` paths.
- **Project Index & Ledger (`README.md` & `docs/PROJECT_STATE.md`):**
  - Synchronized documentation indices and fact sheets with verified empirical code in `project_pkmm-master/`.
- **Data Dictionary (`docs/DATA_DICTIONARY.md`):**
  - Added Sentinel-2 L2A multispectral bands and SCL quality flags with explicit `IMPLEMENTED` vs. `PLANNED` status indicators.
- **Roadmap (`docs/ROADMAP.md`):**
  - Updated Phase 0 status to reflect completed baseline consolidation and verification gates.

---

## [0.1.0-alpha.0] - 2026-10-26

### Added
- Initial specifications for enterprise target architecture (PRD, Architecture, Data Dictionary, API Spec, ML Spec, UX Spec, Roadmap, ADR-001–007).
