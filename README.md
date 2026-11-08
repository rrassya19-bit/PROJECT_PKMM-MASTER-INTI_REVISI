# KARSA-FIRE / BARA — Indonesia Fire Watch

> **Geospatial Hotspot Analysis & Early-Warning Wildfire Predictive Intelligence**  
> **Project Status:** Active Baseline Prototype (`project_pkmm-master/`) & Enterprise Architecture Roadmap (`docs/`)

---

## 1. Project Overview

**KARSA-FIRE**, developed in collaboration with PKMM as **BARA (Pantau Api Indonesia)**, is a geospatial intelligence system designed to support forest and land fire (*karhutla*) monitoring, early warning, and hazard analysis in Indonesia.

The project has two development tracks:

### 1.1 Active Implementation — BARA Prototype

The currently executable application is located in `project_pkmm-master/`.

Its existing capabilities include:

- **NASA FIRMS Integration:** Retrieves active fire detections from VIIRS S-NPP NRT (375m), including caching and Indonesian administrative boundary clipping.
- **Sentinel-2 Data Processing:** Extracts multispectral features from Sentinel-2 L2A Cloud-Optimized GeoTIFFs (COGs) through AWS Earth Search STAC.
- **Cloud and Shadow Filtering:** Uses the Scene Classification Layer (SCL) to reject unsuitable pixels.
- **Machine Learning Prediction:** Uses the currently deployed XGBoost model with 10 input features:
  `B2, B3, B4, B8, B11, B12, NDVI, NDWI, longitude, latitude`.
- **Background Monitoring:** Performs bounded automated monitoring using a 3 × 3 grid and persistent state through `monitor_state.json`.
- **Priority Monitoring:** Organizes monitoring results into two tiers:
  - Tier 1: Active FIRMS detections within the last 24 hours.
  - Tier 2: XGBoost Class 1 predictions within the last 14 days, with 1 km deduplication.
- **Operational Dashboard:** Uses Flask 3.x, Vanilla JavaScript, HTML, CSS, and Leaflet 1.9.4.

**Important:** FIRMS hotspots are satellite-detected thermal anomalies, not automatically confirmed wildfires. Sentinel-2 predictions indicate potential conditions and do not independently confirm an active fire. The current 3 × 3 grid is discrete point sampling, not continuous nationwide prediction.

### 1.2 Target Architecture — KARSA-FIRE Enterprise

The long-term architecture is documented separately in `docs/future/`.

The planned architecture includes:

- Next.js 14+ frontend with Deck.gl and MapLibre GL.
- FastAPI asynchronous geospatial backend.
- PostgreSQL 16 and PostGIS 3.4.
- Uber H3 spatial indexing at resolutions 7 and 8.
- Mapbox Vector Tiles through `ST_AsMVT`.
- ERA5-Land and CHIRPS weather and rainfall integration.
- Spatio-temporal machine learning with Purged Blocked Spatio-Temporal Cross Validation.

These are **future architectural plans**, not components of the currently running prototype.

---

## 2. Quickstart — Running the Active Prototype

### Prerequisites

- Python 3.11+
- Node.js (for frontend tests)
- NASA FIRMS API MAP_KEY

Request a free NASA FIRMS API key:

https://firms.modaps.eosdis.nasa.gov/api/map_key/

### Installation

```powershell
cd project_pkmm-master
python -m pip install -r requirements.txt
```

Configure the required environment variables in `.env` according to the existing application configuration. Copy `.env.example` to `.env` and fill in the values.

At minimum, provide the NASA FIRMS API key using the variable name expected by the current application. Do not commit `.env` or API credentials to Git.

#### macOS / Linux (recommended)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# macOS only: XGBoost needs OpenMP. Either `brew install libomp`, or reuse
# the libomp bundled with scikit-learn:
cp .venv/lib/python3.14/site-packages/sklearn/.dylibs/libomp.dylib \
   .venv/lib/python3.14/site-packages/xgboost/lib/
install_name_tool -add_rpath @loader_path \
   .venv/lib/python3.14/site-packages/xgboost/lib/libxgboost.dylib
```

### Launch

```powershell
python server.py
```

On macOS/Linux, use the virtual environment interpreter:

```bash
.venv/bin/python server.py
```

Open:

http://127.0.0.1:5000

On Windows, `start.bat` can also be used after dependencies have been installed.

### Running Tests

Execute the test suites from `project_pkmm-master/`:

```powershell
python -m unittest test_app.py
python -m unittest test_monitoring.py
python -m unittest test_notifications.py
node test_frontend.cjs
```

Run relevant tests again after modifying application behavior.

---

## 3. Notification System — Development Specification

> **Development Status: IMPLEMENTED (MVP, in-app delivery)**
>
> The notification system is now implemented in `project_pkmm-master/notifications.py` and the dashboard. This section remains the behavioral specification; MVP scope covers N1–N5 plus N7, with in-app delivery only. External delivery channels (email, push, Telegram) remain future extensions.

### 3.1 Objective

The notification system is intended to transform monitoring results into structured, traceable warnings that can be reviewed and acted upon by users.

It must not simply generate a notification every time the application retrieves new data.

The system should:

1. Detect relevant changes in monitoring results.
2. Evaluate whether an alert should be generated.
3. Classify the alert according to its severity.
4. Prevent duplicate notifications for the same event.
5. Store notification history.
6. Track read, delivery, and verification status.
7. Support additional delivery channels without coupling them to detection logic.

### 3.2 Notification Severity Levels

The system uses three levels.

| Level | Meaning | Expected Handling |
|---|---|---|
| INFO | General monitoring information | Display in Notification Center |
| WASPADA | Relevant indication requiring attention | Display and optionally send an external notification |
| DARURAT | Strong indication requiring urgent verification | Escalation only after defined criteria and authorized verification |

#### INFO

Examples:

- New monitoring results are available.
- A new analysis has completed.
- Satellite data is unavailable or unsuitable for analysis.
- Monitoring status has changed.

INFO notifications should communicate operational information without implying that a fire has occurred.

#### WASPADA

Examples:

- A qualifying FIRMS detection has been identified.
- A relevant XGBoost Class 1 result has been generated.
- An existing event has received new supporting evidence.

The notification should include the source, location, detection time, and reason for the warning.

**Important:** XGBoost Class 1 is an indication of potential risk, not confirmation of an active fire.

#### DARURAT

DARURAT is reserved for events that satisfy explicitly defined escalation criteria.

It must not be triggered solely by:

- A single FIRMS hotspot.
- An XGBoost Class 1 prediction.
- Missing satellite data.
- Failed Sentinel-2 processing.
- Cloud or shadow conditions.

A future emergency escalation workflow should require strong supporting evidence and verification by an authorized officer before treating an event as an emergency.

Do not present automatically generated alerts as official emergency declarations.

### 3.3 Proposed Notification Workflow

```text
FIRMS / Sentinel-2 Monitoring Results
                 |
                 v
        Notification Engine
                 |
                 v
       Evaluate Alert Rules
                 |
                 v
       Event Identification
                 |
                 v
       Duplicate Detection
                 |
                 v
       Severity Classification
                 |
                 v
       Store Notification
                 |
          +------+------+
          |             |
          v             v
   Notification     Delivery Service
      Center        (Future Channels)
          |             |
          v             v
    User Review     Delivery Log
          |
          v
   Verification / Follow-up
```

The detection process and notification delivery process should remain separate.

A delivery failure must not delete or invalidate a notification that has already been stored.

### 3.4 Event Management and Duplicate Prevention

One important requirement is preventing repeated notifications for the same event.

The implementation should introduce an event identity mechanism.

An event may be identified using relevant attributes such as:

- Data source.
- Geographic location or spatial proximity.
- Detection time.
- Satellite or sensor identifier.
- Event status.

A suitable event identifier or deduplication key should be designed after inspecting the actual FIRMS and monitoring data structures.

The implementation should support:

- Creating a new event when a genuinely new indication appears.
- Updating an existing event when additional evidence arrives.
- Avoiding duplicate notifications during repeated polling.
- Reopening or escalating an event only when justified by new evidence.
- Retaining historical event records.

Do not assume that two detections are the same event based only on their proximity. Time and source information must also be considered.

The existing 1 km priority deduplication behavior should be inspected before reusing or changing it. Notification deduplication must not silently alter the existing priority-monitoring logic.

### 3.5 Notification Center

The dashboard should provide a dedicated Notification Center.

The initial implementation should support:

- Displaying notification history.
- Showing severity levels.
- Showing notification titles and descriptions.
- Displaying event location and data source.
- Displaying occurrence and creation timestamps.
- Marking notifications as read or unread.
- Opening notification details.
- Filtering notifications by severity.
- Filtering by read status.
- Showing the associated event status when available.

Suggested notification statuses:

| Status | Description |
|---|---|
| UNREAD | Not yet read by the user |
| READ | Already opened or acknowledged |
| ACKNOWLEDGED | User has acknowledged the information |
| RESOLVED | The associated event has been resolved |
| DISMISSED | Notification has been dismissed according to application rules |

Read status and event status should be treated as separate concepts.

For example, reading a notification must not automatically mark a wildfire event as resolved.

### 3.6 Notification Data Structure

The following is a proposed logical structure. Adapt it to the current persistence mechanism after inspecting the existing codebase.

#### Notification

| Field | Purpose |
|---|---|
| id | Unique notification identifier |
| event_id | Associated event identifier |
| title | Notification title |
| message | Notification description |
| severity | INFO, WASPADA, or DARURAT |
| source | FIRMS, SENTINEL2, XGBOOST, or SYSTEM |
| latitude | Event latitude, if available |
| longitude | Event longitude, if available |
| occurred_at | Time the underlying event occurred |
| created_at | Time the notification was generated |
| read_at | Time the notification was read |
| status | Notification read/acknowledgement status |

#### Event

| Field | Purpose |
|---|---|
| id | Unique event identifier |
| event_key | Deduplication identity |
| source | Original data source |
| severity | Current event severity |
| latitude | Event latitude |
| longitude | Event longitude |
| first_detected_at | First detection time |
| last_detected_at | Latest supporting detection |
| status | Current event lifecycle status |
| verified_by | Authorized verifier, if applicable |
| verified_at | Verification timestamp, if applicable |

#### Notification Delivery Log

| Field | Purpose |
|---|---|
| id | Unique delivery record |
| notification_id | Associated notification |
| channel | IN_APP, EMAIL, PUSH, or TELEGRAM |
| recipient | Intended recipient |
| delivery_status | PENDING, SENT, FAILED, or RETRYING |
| attempted_at | Delivery attempt timestamp |
| error_message | Failure details, if any |

These structures are design proposals, not existing database tables. The implementation must first inspect the current persistence layer and choose a compatible solution.

### 3.7 Delivery Channels

Implement delivery in stages.

**Initial MVP:**

- In-app Notification Center.
- Persistent notification history.
- Read/unread status.
- Event and notification deduplication.
- Basic notification logs.

**Future extensions:**

- Browser push notifications.
- Email notifications.
- Telegram Bot notifications.

External delivery must be optional and configurable.

Credentials, bot tokens, and email passwords must be stored in environment variables, never hardcoded in source files or committed to Git.

The application must also record delivery failures and avoid creating a second notification simply because an external delivery attempt failed.

### 3.8 Reliability and Security Requirements

The notification system must:

- Prevent duplicate notifications during repeated polling.
- Preserve notification history across application restarts.
- Validate coordinates before displaying event locations on the map.
- Escape untrusted content before rendering HTML.
- Avoid unsafe HTML interpolation.
- Validate severity and source values against allowlists.
- Handle missing or incomplete monitoring data safely.
- Avoid classifying failed satellite processing as a safe condition.
- Keep external API credentials outside the repository.
- Record delivery failures without losing the original notification.
- Avoid blocking the existing monitoring process while sending external messages.

If asynchronous delivery is introduced, use a bounded and recoverable mechanism appropriate to the current Flask prototype. Do not introduce Celery, Redis, or other infrastructure solely because they appear in the future enterprise architecture.

### 3.9 Implementation Order

Develop the notification feature incrementally.

| Phase | Scope | Expected Result |
|---|---|---|
| N1 | Inspect existing monitoring and persistence contracts | Confirmed integration design |
| N2 | Notification Engine and event identity | Reliable alert generation |
| N3 | Notification persistence and deduplication | Persistent event and notification history |
| N4 | In-app Notification Center | Working dashboard notifications |
| N5 | Read status, filtering, and event details | Usable notification management |
| N6 | External delivery integration | Optional email, push, or Telegram |
| N7 | Testing and reliability hardening | Verified notification behavior |

**Implementation status:** N1–N5 and N7 are implemented in the active prototype with in-app delivery. Notification read state supports `UNREAD`, `READ`, `ACKNOWLEDGED`, `RESOLVED`, and `DISMISSED`; events can be resolved via `POST /api/events/<id>/resolve` without altering notification read state. N6 (email/push/Telegram) is intentionally deferred; `NotificationEngine.deliver()` and the `deliveries[]` log are the extension point. Persistence uses `notification_state.json` (atomic writes, Git-ignored), not a database.

**Operational settings:** `WASPADA_MIN_SCORE` (default `0.5`), `NOTIFICATION_FIRMS_INTERVAL` (default `900` seconds), `NOTIFICATION_MAX_RECORDS` (default `2000`), `NOTIFICATION_MAX_EVENTS` (default `1000`), and optional `VERIFY_TOKEN` for the DARURAT verification and event-resolution endpoints. Set a record limit to `0` for unlimited retention.

Do not skip N1. The implementation must be based on the actual code and data structures in `project_pkmm-master/`.

### 3.10 Notification Acceptance Criteria

The feature should not be considered complete until the following behavior has been tested:

- A qualifying new event generates a notification.
- Repeated polling does not generate duplicate notifications for the same event.
- New supporting evidence updates the appropriate event.
- INFO, WASPADA, and DARURAT follow their defined rules.
- XGBoost predictions alone cannot generate DARURAT.
- Missing or invalid satellite data does not generate a false safe status.
- Notifications persist after restarting the application.
- Read/unread changes persist.
- Delivery failure does not remove the stored notification.
- External delivery does not block the main monitoring workflow.
- Invalid coordinates and untrusted notification content are handled safely.
- Existing monitoring, prediction, priority, and frontend behavior remain functional.

---

## 4. Development Guidelines

### 4.1 Active Codebase Boundary

The executable prototype is located in:

```text
project_pkmm-master/
```

Before modifying code, inspect the actual implementation.

Do not assume that the target enterprise architecture is already implemented.

### 4.2 Preserve Existing Functionality

New notification functionality must not silently break:

- FIRMS data retrieval.
- Sentinel-2 scene discovery and processing.
- XGBoost inference.
- Background grid monitoring.
- Priority classification.
- Existing API response contracts.
- Dashboard interactions.
- CSV exports.

Any changes to existing contracts must be explicitly documented.

### 4.3 Work with Evidence

Before implementing a feature:

1. Inspect the relevant source files.
2. Identify the actual data structures and execution flow.
3. Confirm the existing persistence mechanism.
4. Identify the integration points.
5. Document assumptions and unresolved questions.

After implementation:

1. Run relevant automated tests.
2. Add tests for new behavior.
3. Report the exact files modified.
4. Report actual test commands and results.
5. Document known limitations.

Never claim that a feature is implemented or tested without evidence.

### 4.4 Scope Control

Do not use notification development as a reason to:

- Replace the current XGBoost model.
- Rewrite the entire Flask application.
- Migrate the application to FastAPI.
- Introduce PostgreSQL or PostGIS prematurely.
- Replace the existing frontend architecture.
- Invent unavailable monitoring data.
- Change existing model features or prediction semantics.

Keep the first notification implementation compatible with the active prototype.

---

## 5. Documentation Index

The repository documentation is organized to distinguish active implementation contracts from future architecture specifications.

### 5.1 Active Prototype — `docs/current/`

- [`docs/current/SYSTEM_MANUAL.md`](docs/current/SYSTEM_MANUAL.md): Operational guide, NASA FIRMS setup, grid monitoring, and priority definitions.
- [`docs/current/API_SPEC.md`](docs/current/API_SPEC.md): Existing Flask API contracts, including `/api/status`, `/api/boundary`, `/api/hotspots`, `/api/predict`, `/api/monitor`, and `/api/priorities`.
- [`docs/current/ML_MODEL_CONTRACT.md`](docs/current/ML_MODEL_CONTRACT.md): Active model schema, preprocessing, SCL filtering, and spectral index calculations.

### 5.2 Target Enterprise Architecture — `docs/future/`

- [`docs/future/PRD_TARGET.md`](docs/future/PRD_TARGET.md): Long-term product requirements, personas, and MVP boundaries.
- [`docs/future/ARCHITECTURE_TARGET.md`](docs/future/ARCHITECTURE_TARGET.md): Planned Next.js, FastAPI, PostGIS, H3, and asynchronous processing architecture.
- [`docs/future/API_SPEC_TARGET.md`](docs/future/API_SPEC_TARGET.md): Planned OpenAPI 3.1 REST and vector tile endpoints.
- [`docs/future/ML_SPEC_TARGET.md`](docs/future/ML_SPEC_TARGET.md): Planned spatio-temporal validation, weather feature store, and H3-based forecasting.
- [`docs/future/UX_SPEC_TARGET.md`](docs/future/UX_SPEC_TARGET.md): Planned dashboard design, UI wireframes, and design tokens.

### 5.3 Core Governance — `docs/`

- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md): Data definitions and schemas.
- [`docs/DECISIONS.md`](docs/DECISIONS.md): Architectural Decision Records.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): Engineering roadmap.
- [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md): Current project state, completed work, and blockers.
- [`AGENTS.md`](AGENTS.md): AI agent operating instructions, rules, and skills index.
- [`CHANGELOG.md`](CHANGELOG.md): Release history and documentation changes.

---

## 6. Important Operational Disclaimer

KARSA-FIRE / BARA is a decision-support and monitoring system.

Satellite thermal anomalies and machine learning predictions are not equivalent to field-confirmed fires. Cloud cover, missing pixels, data delays, and service failures can affect the availability and reliability of observations.

All warning levels must communicate their data source, uncertainty, and verification status clearly.

**The system must never present an unverified prediction as a confirmed wildfire or an official emergency declaration.**