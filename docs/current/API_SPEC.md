# REST API Specification — Prototype (Flask)

> **Document Status:** IMPLEMENTED  
> **Source Module:** `project_pkmm-master/server.py`, `project_pkmm-master/notifications.py`  
> **Base URL:** `http://127.0.0.1:5000`

---

## 1. System & Boundary Endpoints

### `GET /api/status`
- **Description:** Returns model metadata, expected features, classes, and FIRMS configuration flag.
- **Response `200 OK`:**
  ```json
  {
    "model": "XGBClassifier",
    "features": ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "longitude", "latitude"],
    "classes": ["0", "1"],
    "firms_configured": true
  }
  ```

### `GET /api/boundary`
- **Description:** Returns the cached GeoJSON Feature polygon for Indonesia (`indonesia.geojson`).
- **Response `200 OK`:** GeoJSON Feature with `MultiPolygon` geometry.

---

## 2. Active Fire & Remote Sensing Endpoints

### `GET /api/hotspots`
- **Description:** Fetches active thermal anomalies from NASA FIRMS VIIRS S-NPP NRT, filters for coordinates within Indonesian land boundaries, and caches the result for 300 seconds.
- **Query Parameters:**
  - `days` (optional, integer): Range in days (`1`, `2`, or `3`). Default is `1`.
- **Response `200 OK`:**
  ```json
  {
    "days": 1,
    "points": [
      {
        "lat": -2.2,
        "lon": 113.9,
        "confidence": "h",
        "frp": 12.5,
        "date": "2026-10-26",
        "time": "0615",
        "satellite": "N",
        "daynight": "D"
      }
    ],
    "retrieved_at": "2026-10-26T07:00:00Z",
    "source": "NASA FIRMS • VIIRS S-NPP NRT"
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: `{"error": "NASA FIRMS MAP_KEY belum diisi..."}`
  - `400 Bad Request`: `{"error": "Rentang waktu harus 1–3 hari."}`

### `POST /api/predict`
- **Description:** Queries AWS Earth Search STAC for the latest Sentinel-2 L2A scene over the target point, extracts surface reflectance across 6 bands, computes NDVI/NDWI, and returns XGBoost prediction.
- **Request Body (`application/json`):**
  ```json
  {
    "lon": 113.9,
    "lat": -2.2,
    "start": "2026-09-26",
    "end": "2026-10-26"
  }
  ```
- **Constraints:**
  - Target point must be on Indonesian land (`indonesia(lon, lat) == True`).
  - Date difference $(end - start) \le 90$ days.
  - Date cannot be in the future.
- **Response `200 OK`:**
  ```json
  {
    "label": "1",
    "probabilities": [0.18, 0.82],
    "classes": ["0", "1"],
    "features": {
      "B2": 635.5,
      "B3": 692.0,
      "B4": 790.5,
      "B8": 1325.5,
      "B11": 2117.5,
      "B12": 1728.0,
      "NDVI": 0.2528,
      "NDWI": -0.3140,
      "longitude": 113.9,
      "latitude": -2.2
    },
    "lon": 113.9,
    "lat": -2.2,
    "scene": {
      "id": "S2B_50LMR_20261018_0_L2A",
      "datetime": "2026-10-18T02:40:00Z",
      "cloud": 12.4
    },
    "warning": "Kelas 1 = berpotensi terbakar; kelas 0 = aman menurut model..."
  }
  ```

---

## 3. Monitoring & Scheduling Endpoints

### `GET /api/monitor`
- **Description:** Returns the active snapshot of the background grid monitor.
- **Response `200 OK`:**
  ```json
  {
    "enabled": true,
    "interval_minutes": 30,
    "bbox": [113.0, -3.0, 114.0, -2.0],
    "points": [
      {
        "id": "1-1",
        "lat": -2.83,
        "lon": 113.17,
        "status": "ok",
        "checked_at": "2026-10-26T07:15:00Z",
        "result": { ... },
        "error": null
      }
    ],
    "cursor": 5,
    "last_run": "2026-10-26T07:15:00Z",
    "next_run": "2026-10-26T07:45:00Z",
    "busy": false,
    "current": null,
    "batch_size": 5,
    "grid_size": 3
  }
  ```

### `POST /api/monitor`
- **Description:** Configures monitoring bounding box or executes control commands.
- **Configuration Request:**
  ```json
  {
    "action": "configure",
    "bbox": [113.0, -3.0, 114.0, -2.0],
    "interval_minutes": 30
  }
  ```
- **Control Request:**
  ```json
  {
    "action": "start | pause | run"
  }
  ```

### `GET /api/priorities`
- **Description:** Computes response ranking combining Tier 1 (active thermal anomalies $\le 24$h) and Tier 2 (Sentinel-2 XGBoost class 1 potential $\le 14$d with 1 km spatial deduplication). Also includes Tier 3 historical potentials.
- **Response `200 OK`:**
  ```json
  {
    "rows": [
      {
        "tier": 1,
        "category": "Indikasi kebakaran aktif",
        "lat": -2.2,
        "lon": 113.9,
        "observed_at": "2026-10-26T06:15:00Z",
        "confidence": "h",
        "frp": 15.4,
        "source": "NASA FIRMS / VIIRS",
        "reason": "Deteksi termal 24 jam terakhir; perlu konfirmasi lapangan."
      },
      {
        "tier": 2,
        "category": "Berpotensi terbakar",
        "lat": -2.83,
        "lon": 113.17,
        "observed_at": "2026-10-18T02:40:00Z",
        "score": 0.84,
        "source": "Sentinel-2 / XGBoost",
        "reason": "Kelas 1: prioritas pencegahan; skor model bukan kepastian kejadian."
      }
    ],
    "historical_potential": [],
    "active_count": 1,
    "potential_count": 1,
    "firms_updated_at": "2026-10-26T07:00:00Z",
    "warning": null,
    "note": "Prioritas 1: deteksi termal dalam 24 jam..."
  }
  ```


---

## 4. Notification System Endpoints

> **Status:** IMPLEMENTED (MVP, in-app delivery)  
> **Persistence:** `project_pkmm-master/notification_state.json` (Git-ignored, atomic writes)  
> **Source Module:** `project_pkmm-master/notifications.py`
>
> Retention defaults to 2.000 notifications / 1.000 events. Set
> `NOTIFICATION_MAX_RECORDS=0` or `NOTIFICATION_MAX_EVENTS=0` to retain without
> limit. Open/monitoring events are never pruned.

Notification severity is limited to `INFO`, `WASPADA`, and `DARURAT`. The
automatic engine never emits `DARURAT`; that level is created only by the
authorized verification endpoint. Notification read status is independent from
the associated event lifecycle status.

### `GET /api/notifications`
- **Query Parameters:** `severity` (`INFO|WASPADA|DARURAT`), `status`
  (`UNREAD|READ|ACKNOWLEDGED|RESOLVED|DISMISSED`), `read` (`true|false`),
  `limit` (1–200, default 50), `offset` (default 0).
- **Response `200 OK`:**
  ```json
  {
    "notifications": [
      {
        "id": "ntf_...",
        "event_id": "evt_...",
        "title": "Anomali termal terdeteksi (FIRMS)",
        "message": "Deteksi VIIRS N pada -2.2000, 113.9000 ...",
        "severity": "WASPADA",
        "source": "FIRMS",
        "latitude": -2.2,
        "longitude": 113.9,
        "occurred_at": "2026-11-07T06:15:00+00:00",
        "created_at": "2026-11-07T06:16:02+00:00",
        "read_at": null,
        "status": "UNREAD",
        "event_status": "OPEN",
        "event_severity": "WASPADA"
      }
    ],
    "total": 1,
    "unread_count": 1,
    "limit": 50,
    "offset": 0
  }
  ```

### `GET /api/notifications/summary`
Returns total and unread counts grouped by severity.

### `GET /api/notifications/<id>`
Returns the notification, its associated event, and all delivery-log records.

### `POST /api/notifications/<id>/read`
Marks an unread notification as `READ` and sets `read_at`. Does not change the
event status.

### `POST /api/notifications/<id>/status`
- **Body:** `{"status": "UNREAD | READ | ACKNOWLEDGED | RESOLVED | DISMISSED"}`
- Setting `UNREAD` clears `read_at`; setting read-like statuses preserves it.
- `RESOLVED` is an explicit notification acknowledgement; it does not automatically resolve the associated event.

### `POST /api/notifications/read-all`
Marks every unread notification as read. Returns `{"changed": <count>}`.

### `GET /api/events`
- **Query Parameters:** `status` (`OPEN|MONITORING|VERIFIED|RESOLVED|DISMISSED`),
  `limit` (1–500, default 100), `offset`.
- Returns events ordered by `last_detected_at` descending, including evidence.

### `GET /api/events/<id>`
Returns one event and all notifications associated with it.

### `POST /api/events/<id>/verify`
- **Purpose:** Authorized human escalation to `DARURAT`.
- **Body:** `{"verifier": "<nama petugas>"}` (minimum 2 characters).
- **Optional security:** when `VERIFY_TOKEN` is configured in the environment,
  the request must include header `X-Verify-Token: <token>`; otherwise `403`.
- **Response `200 OK`:** `{"event": {...}, "notification": {...}}` with the
  new `DARURAT` notification and `event.status = "VERIFIED"`.
- Verification is trust-based in this local prototype; there is no user
  authentication layer yet.

### `POST /api/events/<id>/resolve`
- **Purpose:** Close an event after review without changing notification read
  state.
- **Body:** `{"actor": "<nama petugas>", "note": "<catatan opsional>"}`
  (`actor` minimum 2 characters; `note` bounded to 500 characters).
- **Optional security:** same `VERIFY_TOKEN` / `X-Verify-Token` rule as verify.
- **Response `200 OK`:** `{"event": {...}}` with `status = "RESOLVED"`,
  `resolved_by`, `resolved_at`, and `resolution_note`.
- Resolving an already resolved event returns `400`. A new supporting evidence
  after resolution reopens the event and creates a fresh notification.

### Event Identity and Deduplication

| Source | `event_key` shape | Meaning |
|---|---|---|
| FIRMS | `firms:<satellite>:<lat2dp>:<lon2dp>:<acq_date>` | ~1 km cell + sensor + acquisition date |
| XGBoost | `xgboost:<lat2dp>:<lon2dp>:<scene_date>` | ~1 km cell + image acquisition date |
| SYSTEM | `system:<type>:<key>` | Operational INFO, deduplicated by key |

Repeated polling of the same FIRMS row or Sentinel-2 scene never creates a
duplicate notification. New supporting evidence updates `last_detected_at`;
a new notification is only created when severity escalates or a closed event
reopens. The existing Tier-1/Tier-2 1 km deduplication in `priorities()` is
untouched.
