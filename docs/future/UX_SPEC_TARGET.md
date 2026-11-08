# User Experience & Interface Specification (UX-SPEC) — KARSA-FIRE Enterprise Target

> **Document Status:** PLANNED (Target Architecture — Phase 2+)  
> **Target Framework:** Next.js 14 / Deck.gl / MapLibre GL  
> **Current Prototype UI:** Documented in `docs/current/SYSTEM_MANUAL.md` (Leaflet single-page dashboard)

---

## 1. UX Design Philosophy

KARSA-FIRE is an operational situational awareness and analytical workstation balancing:
1. **Immediate Visual Clarity:** High-contrast map layers differentiating raw satellite thermal anomalies from aggregated risk surfaces.
2. **Temporal Fluency:** Smooth temporal playback and scrubbing through historical fire seasons.
3. **Scientific Credibility & Explainability:** Providing contextual explanations for risk scores rather than opaque ratings.
4. **Accessible Aesthetics:** Modern, dark-mode-first UI using perceptually uniform, colorblind-safe palettes (avoiding red-green confusion).

---

## 2. Target Layout Architecture

```text
+---------------------------------------------------------------------------------------+
|  [LOGO] KARSA-FIRE    | Region: [ Riau Province v ] | Range: [ Last 30 Days v ] | User|
+---------------------------------------------------------------------------------------+
|  LAYER CONTROLS  |                                                      |  INSPECTION |
|  [v] Active Hotspots                                                    |  DRAWER     |
|      - VIIRS (375m)                                                     |             |
|      - MODIS (1km)                                                      |  H3 Cell:   |
|      Conf: [Nom / High]                                                 |  #8764a520  |
|  [v] H3 Density Grid                                                    |             |
|  [ ] Fire Risk Forecast                                                 |  Risk: 84%  |
|      Horizon: [ 24h v ]                                                 |  [EXTREME]  |
|  -----------------                                                      |             |
|  STATISTICS                                                             |  Drivers:   |
|  Total Hotspots: 1,420                                                  |  - Dryness  |
|  High Conf: 1,104                                                       |  - Peatland |
|  Peatland: 68%                                                          |  - Wind     |
|                                                                         |  [Export]   |
+-------------------------------------------------------------------------+-------------+
|  [ < Play > ] |====o====================================================| Oct 26 2026 |
|  Time-Series Scrubber & Fire Radiative Power Histogram (UTC+7)                        |
+---------------------------------------------------------------------------------------+
```

---

## 3. UI Component Specifications

### 3.1 Primary Header & Global Bar
- **Region Selector (`#control-region-select`):** Hierarchical dropdown allowing instant zoom to predefined provinces.
- **Date Range Picker (`#control-date-range`):** Quick presets (`Last 7 Days`, `Last 30 Days`, custom range).
- **System Health Indicator (`#status-pill`):** Displays data freshness timestamp.

### 3.2 Floating Layer & Filter Drawer (Left)
- **Sensor Toggles:** Independent switches for VIIRS (S-NPP / NOAA-20) and MODIS (Terra / Aqua).
- **Confidence Slider / Filter:** Radio-checkbox group (`High only`, `Nominal + High`, `All detections`).

### 3.3 Interactive Map Canvas (Center)
- **Rendering Engine:** WebGL2 via Deck.gl and MapLibre GL.
- **Hover Micro-interaction:** Tooltip with coordinates, timestamp, FRP, brightness, and peatland badge.
- **Click Behavior:** Pins the selected cell and expands the Inspection Drawer.

### 3.4 Temporal Scrubber & Playback Engine (Bottom)
- **Histogram-integrated Timeline (`#timeline-scrubber`):** Displays daily hotspot counts as micro-vertical bars. Draggable slider with playback controls (`Play`, `Pause`, `Speed: 1x, 2x, 5x`).

### 3.5 Detailed Cell Inspection Drawer (Right)
- **Cell Metadata:** H3 Hexagon ID, Administrative District.
- **Risk Attribution Breakdown:** Feature contributions (SHAP values).
- **Local Time-Series Trend:** 14-day historical trend of soil moisture and rainfall.

---

## 4. Visual Design Tokens & Palette (Colorblind-Safe)

| Hazard Level | Color Hex | Color Name | Luminance / Visual Appearance |
|---|---|---|---|
| **Low** | `#2cba00` / `#3b82f6` | Calm Blue-Green / Cool Azure | High legibility against dark slate basemap |
| **Moderate** | `#f59e0b` | Amber / Gold | Distinct intermediate threshold |
| **High** | `#ef4444` | Vivid Crimson | Sharp contrast against amber |
| **Extreme** | `#a855f7` | Ultraviolet / Neon Purple | Highest optical luminance, denotes peak emergency |

