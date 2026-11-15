# 🔥 ALAZ // MODIS & VIIRS 2D/3D Historical Anomaly Center

> **NASA Space Apps Challenge Project**  
> * word origin: **Alaz** (Old Turkic) — Flame, blazing fire spreading across the land.*

**ALAZ** is an interactive 2D/3D geospatial command center and multi-decadal wildfire analytics platform (2000–2026). It harmonizes active fire and thermal anomaly observations from NASA's **MODIS** ($1\text{ km}$) and **VIIRS** ($375\text{ m}$) satellite instruments, filters out persistent industrial heat sources, and provides real-time spatial querying, 3D terrain visualization, and historical anomaly benchmarking.

---

## 🔗 Project Links

- 🌐 **Live Web Application:** [https://albay05.github.io/sistem_odevleri/](https://albay05.github.io/sistem_odevleri/) *(or replace with your custom deployment URL)*
- 💻 **GitHub Repository:** [https://github.com/Albay05/sistem_odevleri](https://github.com/Albay05/sistem_odevleri)
- 📊 **Project Presentation (Google Slides):** [View Presentation Deck](https://docs.google.com/presentation/d/1C1AWhCjd8ulii4JeAeKQ3uI92vNq7v6W3HoCe6gSy3w/edit?usp=sharing)

---

## 🎯 Problem & Scientific Approach

Raw satellite active fire datasets suffer from a fundamental continuity problem when analyzing long-term climate and wildfire trends:
1. **Sensor Resolution & Over-Counting Bias:** Legacy **MODIS** ($1\text{ km}$, since 2000) and newer **VIIRS** ($375\text{ m}$, since 2012) sensors have vastly different pixel footprints. A single wildfire often triggers multiple overlapping VIIRS pixels, artificially inflating raw hotspot counts in post-2012 records.
2. **Industrial & False-Positive Contamination:** Cement plants, steel mills, gas flares, and solar farms continuously trigger thermal anomalies, skewing regional wildfire statistics.

### How ALAZ Solves This:
* **Spatio-Temporal Event Clustering & FRP Harmonization:** ALAZ merges redundant raw satellite pixels into unified **Fire Events** and calibrates Fire Radiative Power (FRP) across MODIS and VIIRS using quantile mapping, achieving an overlap agreement of $R^2 = 0.9057$ and reducing cross-sensor error from $\text{RMSE}_{\text{raw}} = 17.04\text{ MW}$ down to $\text{RMSE}_{\text{harm}} = 1.36\text{ MW}$.
* **Static Industrial Masking:** Automatically identifies and masks **$30,244$ persistent industrial/anthropogenic cells** while applying dynamic micro-fire energy thresholds ($\tau_{\text{day}} = 4.7\text{ MW}$, $\tau_{\text{night}} = 6.0\text{ MW}$).

---

## ✨ Key Features

- **🗺️ Dual 2D Top-Down & 3D Terrain Engine:** Opens in a fast, crisp **2D Top-Down** analytical view by default and seamlessly transitions into a **3D DEM Terrain** perspective with $1.8\times$ elevation exaggeration.
- **🔥 Multi-Layer Thermal Visualization:**
  - **Thermal Heatmap:** Energy-weighted (FRP) continuous density rendering.
  - **3D FRP Extrusion Columns:** 3D hexagonal/grid columns scaled by total radiative energy ($\text{MW}$).
  - **Sensor Track Footprints:** Color-coded differentiation between `MODIS (1km)`, `VIIRS (375m)`, and `Joint` detections.
  - **Burned Area Footprint:** Dynamic estimation of high-persistence burned perimeters.
- **📐 Interactive Area of Interest (AOI) Bounding Box:** Draw any custom rectangular bounding box on the map (via the **Select Area (AOI)** tool or `Shift + Drag`) to dynamically recalculate all 26-year historical charts, anomalies, and KPIs for that exact region.
- **📈 26-Year Historical Analytics Drawer (2000–2026):**
  - **Monthly & Yearly Burning Matrix:** Interactive heatmap of every month from 2000 to 2026; click any cell to time-travel directly to that period.
  - **Multi-Year Trend & Same-Period Baseline:** Compares harmonized fire events against raw pixel counts and multi-decadal averages.
  - **Historical Anomaly ($\pm\%$):** Calculates whether the selected year/month is above or below the 26-year norm.
  - **Seasonal Burning Pattern:** Highlights peak fire seasons alongside current-year monthly activity.
- **📥 One-Click Scientific Exports:**
  - **Hotspots Data (`.CSV`):** UTF-8 CSV export of filtered hotspots enriched with historical regional FRP ratios.
  - **Regional Analytics (`.JSON`):** Structured metadata, calibration metrics, and anomaly report for the active AOI.
  - **4-Chart Analytics Poster (`.PNG`):** High-resolution ($1600 \times 1060\text{ px}$) composite poster of all four analytical charts for direct use in reports and presentations.
- **🌍 Bilingual Interface:** Instant switching between **Turkish (`TR`)** and **English (`EN`)**.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **2D / 3D WebGL Map Engine** | [MapLibre GL JS v4.7.1](https://maplibre.org/) |
| **Analytical Charts & Matrix** | [Apache ECharts v5.5.0](https://echarts.apache.org/) |
| **UI Styling & Glassmorphism** | [Tailwind CSS](https://tailwindcss.com/) |
| **Typography** | [Google Fonts — Inter](https://fonts.google.com/specimen/Inter) |
| **Architecture** | Zero-build, self-contained HTML5 / Vanilla ES6+ JavaScript |

---

## 🚀 Running Locally

Because ALAZ is built as a lightweight, zero-dependency static web application, you can run it locally in seconds using any static HTTP server:

```bash
# 1. Clone the repository
git clone https://github.com/Albay05/sistem_odevleri.git
cd sistem_odevleri

# 2. Start a local web server (Python 3 example)
python -m http.server 8000
```

Then open `http://localhost:8000` in your browser.

---

## 📚 Data & Map Attributions (Credits)

ALAZ gratefully acknowledges the following open science, satellite, and geospatial data providers:

- **Active Fire & Thermal Anomaly Data:**  
  *NASA Fire Information for Resource Management System (FIRMS)* — MODIS Collection 6.1 ($1\text{ km}$) & VIIRS S-NPP / NOAA-20 ($375\text{ m}$) Active Fire Products.
- **2D Dark Vector Base Map:**  
  *© CARTO (Dark Matter GL Style)* & *© OpenStreetMap contributors*.
- **High-Resolution Satellite Imagery:**  
  *Esri World Imagery* — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community.
- **3D Digital Elevation Model (DEM / Terrain):**  
  *Mapzen Terrarium Elevation Tiles* hosted via the *Registry of Open Data on AWS*.
- **Visualization Libraries:**  
  *MapLibre GL JS* (BSD-3-Clause License) & *Apache ECharts* (Apache-2.0 License).

---

