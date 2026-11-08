# API Specification — KARSA-FIRE Backend Service (Target)

> **Document Status:** PLANNED (Target Architecture — Phase 2+)  
> **Specification Standard:** OpenAPI 3.1.0  
> **Target Base URL:** `/api/v1`  
> **Current Prototype Endpoints:** Documented in `docs/current/API_SPEC.md`

---

## 1. Global Conventions & Error Schema

### 1.1 Standard Error Envelope
All error responses return an RFC-7807 compatible JSON structure:
```json
{
  "type": "https://karsa-fire.org/errors/invalid-parameter",
  "title": "Invalid Spatial Bounding Box",
  "status": 400,
  "detail": "The requested bounding box area exceeds the maximum allowed limit of 250,000 sq km.",
  "instance": "/api/v1/hotspots/points?bbox=...",
  "timestamp": "2026-10-26T14:30:00Z"
}
```

### 1.2 Common Query Parameters
- `bbox`: Comma-delimited coordinates `min_lon,min_lat,max_lon,max_lat` (EPSG:4326).
- `start_date`: ISO 8601 date string (`YYYY-MM-DD`).
- `end_date`: ISO 8601 date string (`YYYY-MM-DD`).
- `confidence`: Comma-delimited strings: `low,nominal,high`.
- `satellite`: Comma-delimited list: `VIIRS_SNPP,VIIRS_NOAA20,MODIS`.

---

## 2. Target Endpoint Specifications

### 2.1 System Health
- `GET /api/v1/health`: Service liveness, PostgreSQL/PostGIS connection status, and latest ingested hotspot timestamp.

### 2.2 Hotspot Observation Endpoints
- `GET /api/v1/hotspots/points`: Retrieve individual thermal anomaly points within a spatial-temporal window in GeoJSON format.
- `GET /api/v1/hotspots/tiles/{z}/{x}/{y}.pbf`: High-performance vector tile service delivering clipped Mapbox Vector Tiles (`ST_AsMVT`).

### 2.3 Spatial & Temporal Aggregations
- `GET /api/v1/hotspots/aggregates/time-series`: Daily/weekly/monthly hotspot count and FRP trend over time.
- `GET /api/v1/hotspots/aggregates/h3`: Hexagonal grid aggregation for density heatmaps and spatio-temporal binning at resolutions 6, 7, or 8.

### 2.4 Predictive Fire-Risk Endpoints
- `GET /api/v1/risk/predictions`: Fetch spatial fire-risk predictions for a designated target date and forecast horizon (24h, 72h, 168h) along with explainability top drivers.

---

## 3. Rate Limiting & Guardrails

| Constraint | Limit | Trigger Action |
|---|---|---|
| **Max Bounding Box Area** | $250,000\text{ km}^2$ | Returns `400 Bad Request` |
| **Max Query Limit** | 25,000 records | Clamped automatically with warning in header |
| **Rate Limit (Public Tier)** | 60 requests / minute | Returns `429 Too Many Requests` |

