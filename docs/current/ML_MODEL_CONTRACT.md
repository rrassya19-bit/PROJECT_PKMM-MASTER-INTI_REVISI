# Machine Learning Model Contract — Prototype (XGBoost)

> **Document Status:** IMPLEMENTED  
> **Source Artifact:** `project_pkmm-master/model_early_warning_sentinel2_xgb.joblib`  
> **Inference Engine:** XGBoost 3.4.1 / Scikit-Learn Pipeline Wrapper

---

## 1. Model Artifact Specifications

The model file is stored as a serialized joblib dictionary/estimator bundle.
- **Estimator Class:** `xgboost.XGBClassifier`
- **Output Classes:** `['0', '1']`
- **Target Interpretation:**
  - Class `0`: **Safe / Low Risk (Aman)** — Low likelihood of fire susceptibility under baseline spectral conditions.
  - Class `1`: **Potential Fire Hazard (Berpotensi Terbakar)** — Surface reflectance characteristics indicate elevated flammability or dry biomass.
  - *Disclaimer:* Output probabilities represent algorithmic scores, not empirical guarantees of wildfire outbreak or exact occurrence time.

---

## 2. Feature Schema & Preprocessing

The model requires exactly 10 features in dataframe column order:

| Feature Name | Type | Physical Source | Description & Formula | Value Range |
|---|---|---|---|---|
| `B2` | `float64` | Sentinel-2 L2A Band 2 | Blue surface reflectance scaled $\times 10000$ | $0 - 10000$ |
| `B3` | `float64` | Sentinel-2 L2A Band 3 | Green surface reflectance scaled $\times 10000$ | $0 - 10000$ |
| `B4` | `float64` | Sentinel-2 L2A Band 4 | Red surface reflectance scaled $\times 10000$ | $0 - 10000$ |
| `B8` | `float64` | Sentinel-2 L2A Band 8 | Broad NIR surface reflectance scaled $\times 10000$ | $0 - 10000$ |
| `B11` | `float64` | Sentinel-2 L2A Band 11 | SWIR-1 surface reflectance scaled $\times 10000$ | $0 - 10000$ |
| `B12` | `float64` | Sentinel-2 L2A Band 12 | SWIR-2 surface reflectance scaled $\times 10000$ | $0 - 10000$ |
| `NDVI` | `float64` | Computed Index | Normalized Difference Vegetation Index: $\frac{B8 - B4}{B8 + B4}$ | $-1.0 \text{ to } +1.0$ |
| `NDWI` | `float64` | Computed Index | Normalized Difference Water Index (see formula options below) | $-1.0 \text{ to } +1.0$ |
| `longitude`| `float64` | Geographic coordinate | Longitude of pixel center (WGS 84 EPSG:4326) | $94.0 \text{ to } 142.0$ |
| `latitude` | `float64` | Geographic coordinate | Latitude of pixel center (WGS 84 EPSG:4326) | $-12.0 \text{ to } 7.0$ |

*(Optional fallback: If the model bundle contains `dNBR`, it computes $\text{NBR}_{\text{prev}} - \text{NBR}_{\text{curr}}$ where $\text{NBR} = \frac{B8 - B12}{B8 + B12}$).*

---

## 3. Reflectance Harmonization & Offset Handling

When reading COGs from AWS Earth Search (`sentinel-2-l2a`):
```python
meta = asset.get('raster:bands', [{}])[0]
scale, offset = meta.get('scale', 0.0001), meta.get('offset', 0)
if item['properties'].get('earthsearch:boa_offset_applied'):
    offset = 0
values[band] = (val * scale + offset) * 10000
```
This guarantees that changes in the Sentinel-2 processing baseline (PB 04.00+ negative offset) are harmonized before multiplication by 10000.

---

## 4. NDWI Formulation Options

Controlled via the `NDWI_FORMULA` environment variable in `.env`:
1. `NDWI_FORMULA=green_nir` (Default, McFeeters):
   $$\text{NDWI} = \frac{B3 - B8}{B3 + B8}$$
2. `NDWI_FORMULA=nir_swir` (Gao Moisture Index):
   $$\text{NDWI} = \frac{B8 - B11}{B8 + B11}$$

---

## 5. Pixel Quality & SCL Filtering

Every extracted scene pixel must have its corresponding Scene Classification Layer (`scl`) inspected:
- **Reject codes:** `0` (NO_DATA), `1` (SATURATED_OR_DEFECTIVE), `3` (CLOUD_SHADOWS), `8` (CLOUD_MEDIUM_PROBABILITY), `9` (CLOUD_HIGH_PROBABILITY), `10` (THIN_CIRRUS), `11` (SNOW).
- **Accept codes:** `2` (DARK_AREA_PIXELS), `4` (VEGETATION), `5` (NOT_VEGETATED), `6` (WATER), `7` (UNCLASSIFIED).
If the SCL pixel is rejected, the pipeline tries the next scene in the acquisition window (up to 5 scenes).

