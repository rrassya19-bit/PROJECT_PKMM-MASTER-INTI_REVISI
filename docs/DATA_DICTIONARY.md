# Data Dictionary & Schema Specification — KARSA-FIRE & BARA

> **Document Version:** 1.1.0  
> **Status:** Active Data Dictionary  
> **Coordinate Reference System:** WGS 84 (`EPSG:4326`) for geometries; Web Mercator (`EPSG:3857`) for map rendering.

---

## 1. Implemented Datasets (Active Prototype)

### 1.1 Sentinel-2 L2A Multispectral Surface Reflectance
- **Status:** `IMPLEMENTED`
- **Source:** AWS Earth Search STAC v1 (`sentinel-2-l2a`) via Cloud-Optimized GeoTIFFs (COGs).
- **Scale Factor:** $\text{Reflectance} = (\text{val} \times \text{scale} + \text{offset}) \times 10000$ (offset neutralized if `earthsearch:boa_offset_applied` is true).

| Band / Index | Asset Key | Central Wavelength | Spatial Res | Role in Fire Susceptibility Inference |
|---|---|---|---|---|
| `B2` | `blue` | $490\text{ nm}$ | $10\text{ m}$ | Blue reflectance; atmospheric scattering correction. |
| `B3` | `green` | $560\text{ nm}$ | $10\text{ m}$ | Green reflectance; used in standard McFeeters NDWI. |
| `B4` | `red` | $665\text{ nm}$ | $10\text{ m}$ | Red absorption; chlorophyll absorption contrast in NDVI. |
| `B8` | `nir` | $842\text{ nm}$ | $10\text{ m}$ | Near-infrared reflectance; canopy density and cell structure. |
| `B11` | `swir16` | $1610\text{ nm}$ | $20\text{ m}$ | Shortwave infrared-1; sensitive to vegetation moisture & dry fuel. |
| `B12` | `swir22` | $2190\text{ nm}$ | $20\text{ m}$ | Shortwave infrared-2; charcoal and burn scar detection. |
| `SCL` | `scl` | N/A | $20\text{ m}$ | Scene Classification Layer: filters clouds (8, 9), shadow (3), cirrus (10). |
| `NDVI` | Derived | N/A | $10\text{ m}$ | $\frac{B8 - B4}{B8 + B4}$ (Normalized Difference Vegetation Index). |
| `NDWI` | Derived | N/A | $10\text{ m}$ / $20\text{ m}$ | $\frac{B3 - B8}{B3 + B8}$ (default) or $\frac{B8 - B11}{B8 + B11}$ (Gao Moisture Index). |

### 1.2 NASA FIRMS Active Fire Data (Thermal Anomalies)
- **Status:** `IMPLEMENTED`
- **Source:** NASA FIRMS API (`VIIRS_SNPP_NRT`).

| Attribute | Type | Unit | Description |
|---|---|---|---|
| `latitude` | `float` | Degrees | Latitude of active fire pixel center (WGS 84, $-90.0$ to $+90.0$). |
| `longitude` | `float` | Degrees | Longitude of active fire pixel center (WGS 84, $-180.0$ to $+180.0$). |
| `confidence` | `string` | Code | Categorical confidence: `'l'` (low), `'n'` (nominal), `'h'` (high). |
| `frp` | `float` | Megawatts | Fire Radiative Power (MW) measuring radiant heat output. |
| `acq_date` | `string` | YYYY-MM-DD | Acquisition date in UTC. |
| `acq_time` | `string` | HHMM | Acquisition time in UTC. |
| `satellite` | `string` | Code | Satellite identifier (`'N'` for Suomi-NPP). |
| `daynight` | `string` | Code | Day (`'D'`) or Night (`'N'`). |

---

## 2. Planned Datasets (Target Architecture — Phase 1+)

### 2.1 ECMWF ERA5-Land Meteorological Reanalysis
- **Status:** `PLANNED`
- **Resolution:** $\sim 9\text{ km}$ ($0.1^\circ \times 0.1^\circ$).

| Parameter | Unit | Description |
|---|---|---|
| `t2m` | Kelvin (K) | Air temperature at 2 meters. |
| `d2m` | Kelvin (K) | Dewpoint temperature at 2 meters. |
| `u10`, `v10` | $\text{m/s}$ | 10-meter zonal and meridional wind speed components. |
| `swvl1` | $\text{m}^3/\text{m}^3$ | Topsoil volumetric moisture ($0 - 7\text{ cm}$). |
| `swvl2` | $\text{m}^3/\text{m}^3$ | Subsurface root-zone volumetric moisture ($7 - 28\text{ cm}$). |

### 2.2 CHIRPS Precipitation
- **Status:** `PLANNED`
- **Resolution:** $0.05^\circ \times 0.05^\circ$ ($\sim 5.5\text{ km}$).

| Field | Type | Description |
|---|---|---|
| `precip` | $\text{mm/day}$ | Daily total precipitation. |
| `consecutive_dry_days` | Days | Consecutive days with $\text{precip} < 1.0\text{ mm}$. |

### 2.3 Target PostGIS Relational Tables
- **Status:** `PLANNED`
- `hotspots`: Raw point observations partitioned by year/month.
- `h3_daily_aggregates`: Pre-aggregated daily rollups indexed by Uber H3 cells.
- `fire_risk_predictions`: Spatial-temporal predictions and SHAP feature attributions.

### 1.3 Notification State (Active Prototype, MVP)
- **Status:** `IMPLEMENTED`
- **Persistence:** `project_pkmm-master/notification_state.json` (single JSON document, atomic `.tmp` replacement, process lock, Git-ignored).
- **Retention:** `NOTIFICATION_MAX_RECORDS` notifications (default 2000) and `NOTIFICATION_MAX_EVENTS` events (default 1000); a value of `0` means unlimited retention. Open/monitoring events are never pruned.

#### `events[]`
| Attribute | Type | Description |
|---|---|---|
| `id` | `string` | Unique event identifier (`evt_...`). |
| `event_key` | `string` | Deduplication identity: source + ~1 km coordinate cell + time bucket. |
| `source` | `enum` | `FIRMS`, `SENTINEL2`, `XGBOOST`, `SYSTEM`. |
| `severity` | `enum` | Highest severity reached: `INFO`, `WASPADA`, `DARURAT`. |
| `latitude` / `longitude` | `float \| null` | Event coordinates, validated to WGS 84 ranges before storage. |
| `first_detected_at` / `last_detected_at` | `ISO 8601` | First and latest supporting evidence timestamps. |
| `status` | `enum` | `OPEN`, `MONITORING`, `VERIFIED`, `RESOLVED`, `DISMISSED`. |
| `verified_by` / `verified_at` | `string \| null` | Authorized verifier and timestamp for DARURAT escalation. |
| `resolved_by` / `resolved_at` | `string \| null` | Officer and timestamp for event resolution. |
| `resolution_note` | `string \| null` | Optional bounded resolution note (max 500 chars). |
| `evidence[]` | `array` | `{fingerprint, observed_at}` records; repeated fingerprints are ignored. |

#### `notifications[]`
| Attribute | Type | Description |
|---|---|---|
| `id` | `string` | Unique notification identifier (`ntf_...`). |
| `event_id` | `string` | Associated event. |
| `title` / `message` | `string` | Bounded (160 / 1200 chars) display text, escaped on render. |
| `severity` | `enum` | `INFO`, `WASPADA`, `DARURAT`. |
| `source` | `enum` | `FIRMS`, `SENTINEL2`, `XGBOOST`, `SYSTEM`. |
| `latitude` / `longitude` | `float \| null` | Coordinates for map display; invalid values stored as `null`. |
| `occurred_at` | `ISO 8601` | Time of the underlying observation. |
| `created_at` | `ISO 8601` | Time the notification was generated. |
| `read_at` | `ISO 8601 \| null` | First read/acknowledgement timestamp. |
| `status` | `enum` | `UNREAD`, `READ`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`. |

#### `deliveries[]`
| Attribute | Type | Description |
|---|---|---|
| `id` | `string` | Delivery record identifier (`dlv_...`). |
| `notification_id` | `string` | Associated notification. |
| `channel` | `enum` | `IN_APP` (implemented), `EMAIL`, `PUSH`, `TELEGRAM` (planned). |
| `recipient` | `string` | Intended recipient; dashboard for the MVP. |
| `delivery_status` | `enum` | `PENDING`, `SENT`, `FAILED`, `RETRYING`. |
| `attempted_at` | `ISO 8601` | Attempt timestamp. |
| `error_message` | `string \| null` | Failure details, without credentials. |

#### Severity rules (automatic engine)
| Level | Automatic trigger | Never triggered by |
|---|---|---|
| `INFO` | Cycle completed, monitoring state change, FIRMS unavailable, grid analysis failed | — |
| `WASPADA` | FIRMS confidence `h`/`n` within 24 h; XGBoost class 1 with score ≥ `WASPADA_MIN_SCORE` and scene ≤14 days; severity escalation/new evidence | Missing data or failed processing |
| `DARURAT` | Only `POST /api/events/<id>/verify` by a named verifier | Single FIRMS hotspot, XGBoost class 1, missing satellite data, cloud, processing failure |
