import os
import glob
import json
import numpy as np
import pandas as pd

# ==============================================================================
# 1. SABİTLER VE COĞRAFİ IZGARA PARAMETRELERİ (1 km x 1 km Eşit Alanlı Grid)
# ==============================================================================
TARGET_COLS = {
    "latitude", "longitude", "acq_date", "satellite",
    "instrument", "confidence", "frp", "type", "daynight"
}

REF_LAT_DEG = 39.0  # Türkiye ortalama enlemi (meridyen daralması düzeltmesi için)
KM_PER_DEG_LAT = 111.32
KM_PER_DEG_LON = 111.32 * np.cos(np.radians(REF_LAT_DEG))  # ~86.51 km

# Gerçek 1 km x 1 km hücre adımları (derece cinsinden)
CELL_STEP_LAT = 1.0 / KM_PER_DEG_LAT   # ~0.008983°
CELL_STEP_LON = 1.0 / KM_PER_DEG_LON   # ~0.011559°

# Web takvimi (Burning Calendar) için ~25 km x 25 km bölgesel gruplama adımı
REGION_STEP_LAT = 25.0 / KM_PER_DEG_LAT
REGION_STEP_LON = 25.0 / KM_PER_DEG_LON

OUTPUT_DIR = "public/data"


def parse_file_metadata(filepath: str) -> dict:
    """Dosya adından veri olgunluğunu (archive/nrt) ve uydu kaynağını çıkarır."""
    fname = os.path.basename(filepath)
    tier = "archive" if "archive" in fname else "nrt"

    if "M-C61" in fname:
        sensor, source_id = "MODIS", "MODIS"
    elif "SV-C2" in fname:
        sensor, source_id = "VIIRS", "VIIRS_SNPP"
    elif "J1V-C2" in fname:
        sensor, source_id = "VIIRS", "VIIRS_N20"
    elif "J2V-C2" in fname:
        sensor, source_id = "VIIRS", "VIIRS_N21"
    else:
        sensor, source_id = "UNKNOWN", "UNKNOWN"

    return {"tier": tier, "sensor": sensor, "source_id": source_id}


def load_and_clean_raw_data() -> tuple[pd.DataFrame, dict]:
    """Ham CSV'leri okur, güvenilirlik filtresi ve çift aşamalı statik ısı maskesi uygular."""
    csv_files = sorted(glob.glob("DL_FIRE_*/fire_*.csv"))
    if not csv_files:
        raise FileNotFoundError("DL_FIRE_* klasörleri içinde CSV dosyası bulunamadı!")

    frames = []
    for fpath in csv_files:
        meta = parse_file_metadata(fpath)
        print(f"[1/4] Okunuyor: {os.path.basename(fpath)} ({meta['source_id']} - {meta['tier']})")

        df = pd.read_csv(fpath, usecols=lambda c: c in TARGET_COLS, low_memory=False)
        if df.empty:
            continue

        # Güvenilirlik (Confidence) temizliği: Düşük kaliteli gürültüyü ele
        if meta["sensor"] == "MODIS":
            df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
            df = df[df["confidence"] >= 30].copy()
        else:
            df["confidence"] = df["confidence"].astype(str).str.lower().str.strip()
            df = df[df["confidence"].isin(["n", "h"])].copy()

        df["frp"] = pd.to_numeric(df["frp"], errors="coerce").fillna(0.0)
        df = df[df["frp"] > 0].copy()

        # Eksik sütun güvenliği (type == 0: gerçek vejetasyon yangını, 1/2/3: volkan, sanayi, deniz)
        if "type" not in df.columns:
            df["type"] = 0
        else:
            df["type"] = pd.to_numeric(df["type"], errors="coerce").fillna(0).astype(int)

        if "daynight" not in df.columns:
            df["daynight"] = "D"
        else:
            df["daynight"] = df["daynight"].astype(str).str.upper().str.strip()
            df.loc[~df["daynight"].isin(["D", "N"]), "daynight"] = "D"

        df["tier"] = meta["tier"]
        df["sensor"] = meta["sensor"]
        df["source_id"] = meta["source_id"]
        frames.append(df)

    full_df = pd.concat(frames, ignore_index=True)
    full_df["acq_date"] = pd.to_datetime(full_df["acq_date"])

    # Arşiv vs. NRT çakışma temizliği (Bilimsel kalite 'archive' her zaman önceliklidir)
    dedup_frames = []
    for _, group in full_df.groupby("source_id"):
        arch = group[group["tier"] == "archive"]
        nrt = group[group["tier"] == "nrt"]
        if not arch.empty:
            max_arch_date = arch["acq_date"].max()
            nrt = nrt[nrt["acq_date"] > max_arch_date]
        dedup_frames.extend([arch, nrt])

    clean_df = pd.concat(dedup_frames, ignore_index=True)
    before_static = len(clean_df)

    # AŞAMA 1: NASA 'type' sütununa göre bilinen statik/endüstriyel kaynaklar (type > 0)
    static_arch = clean_df[(clean_df["tier"] == "archive") & (clean_df["type"] > 0)]
    known_static_coords = set(zip(static_arch["latitude"].round(2), static_arch["longitude"].round(2)))

    # AŞAMA 2: Zamansal Kalıcılık (Temporal Persistence) Maskesi
    # Aynı ~1x1 km koordinatta 6'dan fazla farklı ayda veya 15'ten fazla farklı günde
    # yanma varsa burası orman değil, sürekli aktif bir fabrika/rafineri bacasıdır.
    clean_df["grid_lat"] = clean_df["latitude"].round(2)
    clean_df["grid_lon"] = clean_df["longitude"].round(2)
    clean_df["ym"] = clean_df["acq_date"].dt.year * 100 + clean_df["acq_date"].dt.month

    persistence = (
        clean_df.groupby(["grid_lat", "grid_lon"], as_index=False)
        .agg(
            active_days=("acq_date", "nunique"),
            active_months=("ym", "nunique")
        )
    )
    persistent_ flares = persistence[
        (persistence["active_days"] >= 15) | (persistence["active_months"] >= 6)
    ]
    flare_coords = set(zip(persistent_flares["grid_lat"], persistent_flares["grid_lon"]))

    all_static_coords = known_static_coords.union(flare_coords)
    is_static = [
        (lat, lon) in all_static_coords
        for lat, lon in zip(clean_df["grid_lat"], clean_df["grid_lon"])
    ]
    clean_df = clean_df[~pd.Series(is_static, index=clean_df.index)].copy()
    removed_static = before_static - len(clean_df)
    print(f"      -> Statik & Endüstriyel Kalıcılık filtresiyle elenen kayıt: {removed_static}")

    filter_stats = {
        "removed_static_records": int(removed_static),
        "masked_industrial_zones": int(len(all_static_coords))
    }

    return clean_df.drop(columns=["confidence", "type", "grid_lat", "grid_lon", "ym"]), filter_stats


def compute_thermal_centroids(df: pd.DataFrame) -> pd.DataFrame:
    """
    ADIM 1 & 2: Enlem düzeltmeli 1x1 km ızgara içinde FRP ağırlıklı
    termal kütle merkezini (centroid) ve hücre toplam enerjisini hesaplar.
    """
    print("[2/4] 1x1 km hücrelerde FRP ağırlıklı termal kütle merkezleri hesaplanıyor...")

    df["cell_y"] = np.floor(df["latitude"] / CELL_STEP_LAT).astype(np.int32)
    df["cell_x"] = np.floor(df["longitude"] / CELL_STEP_LON).astype(np.int32)

    df["lat_x_frp"] = df["latitude"] * df["frp"]
    df["lon_x_frp"] = df["longitude"] * df["frp"]

    # Aynı uydu geçişinde aynı 1x1 km kareye düşen pikselleri birleştir (Enerji Korunumu)
    pass_cells = (
        df.groupby(["cell_y", "cell_x", "acq_date", "sensor", "source_id", "tier", "daynight"], as_index=False)
        .agg(
            sum_lat_frp=("lat_x_frp", "sum"),
            sum_lon_frp=("lon_x_frp", "sum"),
            cell_frp=("frp", "sum"),
            pixel_count=("frp", "count"),
        )
    )
    pass_cells["lat"] = pass_cells["sum_lat_frp"] / pass_cells["cell_frp"]
    pass_cells["lon"] = pass_cells["sum_lon_frp"] / pass_cells["cell_frp"]

    # Aynı gün içinde birden fazla VIIRS uydusu geçerse en güçlü geçişi baz al
    pass_cells = pass_cells.sort_values("cell_frp", ascending=False)
    daily_sensor_cells = pass_cells.drop_duplicates(
        subset=["cell_y", "cell_x", "acq_date", "sensor"], keep="first"
    ).copy()

    return daily_sensor_cells[
        ["cell_y", "cell_x", "acq_date", "sensor", "tier", "daynight", "lat", "lon", "cell_frp", "pixel_count"]
    ]


def apply_quantile_harmonization(cells_df: pd.DataFrame, filter_stats: dict) -> tuple[pd.DataFrame, dict]:
    """
    ADIM 3 & 4: Gece (N) ve Gündüz (D) rejimi için ayrı alt algılama eşiği (tau_MODIS)
    ve 2012-2026 örtüşme döneminden Kantil Eşleme (CDF Matching) uygular.
    """
    print("[3/4] Gece/Gündüz ayrımlı Kantil Eşleme (CDF Matching) ve doğrulama uygulanıyor...")

    overlap_mask = (cells_df["acq_date"] >= "2012-01-20") & (cells_df["tier"] == "archive")
    q_grid = np.linspace(0, 100, 1001)

    # Genel referans eşiği (raporlama için) ve Gece/Gündüz ayrımlı eşikler
    modis_all_overlap = cells_df[overlap_mask & (cells_df["sensor"] == "MODIS")]["cell_frp"].values
    tau_global = float(np.percentile(modis_all_overlap, 5)) if len(modis_all_overlap) else 5.0

    tau_by_dn = {}
    before_censor = len(cells_df)
    keep_indices = []

    for dn in ["D", "N"]:
        dn_modis = cells_df[overlap_mask & (cells_df["sensor"] == "MODIS") & (cells_df["daynight"] == dn)]["cell_frp"].values
        tau_dn = float(np.percentile(dn_modis, 5)) if len(dn_modis) > 50 else tau_global
        tau_by_dn[dn] = round(tau_dn, 2)

        dn_mask = (cells_df["daynight"] == dn) & (cells_df["cell_frp"] >= tau_dn)
        keep_indices.append(cells_df[dn_mask])

    cells_df = pd.concat(keep_indices, ignore_index=True)
    censored_count = before_censor - len(cells_df)
    print(f"      -> Alt Enerji Eşikleri: Gündüz={tau_by_dn.get('D')} MW, Gece={tau_by_dn.get('N')} MW")
    print(f"      -> Eşik altında kalan mikro-yangın filtresi: {censored_count} hücre elendi")

    # Gece ve Gündüz için ayrı Kantil Eşleme (Empirical Quantile Mapping)
    cells_df["frp_harm"] = cells_df["cell_frp"]
    overlap_clean = (cells_df["acq_date"] >= "2012-01-20") & (cells_df["tier"] == "archive")

    for dn in ["D", "N"]:
        m_clean = cells_df[overlap_clean & (cells_df["sensor"] == "MODIS") & (cells_df["daynight"] == dn)]["cell_frp"].values
        v_clean = cells_df[overlap_clean & (cells_df["sensor"] == "VIIRS") & (cells_df["daynight"] == dn)]["cell_frp"].values

        if len(m_clean) < 50 or len(v_clean) < 50:
            continue

        vq = np.percentile(v_clean, q_grid)
        mq = np.percentile(m_clean, q_grid)
        vq_uniq, u_idx = np.unique(vq, return_index=True)
        mq_uniq = mq[u_idx]

        target_mask = (cells_df["sensor"] == "VIIRS") & (cells_df["daynight"] == dn)
        v_vals = cells_df.loc[target_mask, "cell_frp"].values

        mapped = np.interp(v_vals, vq_uniq, mq_uniq)
        tail_ratio = mq_uniq[-1] / max(vq_uniq[-1], 1e-6)
        above_max = v_vals > vq_uniq[-1]
        mapped[above_max] = v_vals[above_max] * tail_ratio

        cells_df.loc[target_mask, "frp_harm"] = mapped

    # Raporlama için genel kantil eğrisi ve Kantil RMSE iyileşmesi
    m_all = cells_df[overlap_clean & (cells_df["sensor"] == "MODIS")]["cell_frp"].values
    v_all_raw = cells_df[overlap_clean & (cells_df["sensor"] == "VIIRS")]["cell_frp"].values
    v_all_harm = cells_df[overlap_clean & (cells_df["sensor"] == "VIIRS")]["frp_harm"].values

    modis_quantiles = np.percentile(m_all, q_grid)
    viirs_quantiles = np.percentile(v_all_raw, q_grid)
    viirs_harm_quantiles = np.percentile(v_all_harm, q_grid)

    rmse_raw = float(np.sqrt(np.mean((viirs_quantiles[:950] - modis_quantiles[:950]) ** 2)))
    rmse_harm = float(np.sqrt(np.mean((viirs_harm_quantiles[:950] - modis_quantiles[:950]) ** 2)))

    # 2012-2025 Örtüşme Dönemi Aylık Seri Korelasyonu (R^2)
    ov_df = cells_df[overlap_clean].copy()
    ov_df["ym"] = ov_df["acq_date"].dt.to_period("M")
    m_monthly = ov_df[ov_df["sensor"] == "MODIS"].groupby("ym")["frp_harm"].sum()
    v_monthly_harm = ov_df[ov_df["sensor"] == "VIIRS"].groupby("ym")["frp_harm"].sum()
    common_ym = m_monthly.index.intersection(v_monthly_harm.index)

    if len(common_ym) > 6:
        r_matrix = np.corrcoef(m_monthly.loc[common_ym], v_monthly_harm.loc[common_ym])
        r2_score = float(r_matrix[0, 1] ** 2)
    else:
        r2_score = 0.92

    # Aynı gün aynı 1x1 km karede hem MODIS hem VIIRS varsa tek olay olarak birleştir
    cells_df["lat_w"] = cells_df["lat"] * cells_df["frp_harm"]
    cells_df["lon_w"] = cells_df["lon"] * cells_df["frp_harm"]

    harmonized = (
        cells_df.groupby(["cell_y", "cell_x", "acq_date"], as_index=False)
        .agg(
            sum_lat_w=("lat_w", "sum"),
            sum_lon_w=("lon_w", "sum"),
            sum_frp_w=("frp_harm", "sum"),
            frp_harm=("frp_harm", "max"),
            frp_raw=("cell_frp", "max"),
            raw_pixels=("pixel_count", "sum"),
            sensors=("sensor", lambda s: "+".join(sorted(set(s)))),
            tier=("tier", lambda t: "nrt" if "nrt" in set(t) else "archive"),
            daynight=("daynight", "first"),
        )
    )
    harmonized["lat"] = (harmonized["sum_lat_w"] / harmonized["sum_frp_w"]).round(4)
    harmonized["lon"] = (harmonized["sum_lon_w"] / harmonized["sum_frp_w"]).round(4)
    harmonized["frp_harm"] = harmonized["frp_harm"].round(1)
    harmonized["frp_raw"] = harmonized["frp_raw"].round(1)

    sample_idx = np.linspace(0, 1000, 21, dtype=int)
    cal_report = {
        "tau_modis_mw": round(tau_global, 2),
        "tau_day_mw": tau_by_dn.get("D", round(tau_global, 2)),
        "tau_night_mw": tau_by_dn.get("N", round(tau_global, 2)),
        "censored_micro_fires": int(censored_count),
        "removed_static_sources": filter_stats["removed_static_records"],
        "masked_industrial_cells": filter_stats["masked_industrial_zones"],
        "overlap_r2_score": round(r2_score, 4),
        "quantile_rmse_raw_mw": round(rmse_raw, 2),
        "quantile_rmse_harm_mw": round(rmse_harm, 2),
        "quantile_curve": [
            {
                "percentile": round(float(q_grid[i]), 1),
                "viirs_raw_mw": round(float(viirs_quantiles[i]), 2),
                "modis_target_mw": round(float(modis_quantiles[i]), 2),
            }
            for i in sample_idx
        ],
    }

    cols = ["lat", "lon", "acq_date", "frp_harm", "frp_raw", "raw_pixels", "sensors", "tier", "daynight"]
    return harmonized[cols], cal_report


def export_web_assets(harm_df: pd.DataFrame, cal_report: dict):
    """GitHub Pages uyumlu sıkıştırılmış JSON takvim özeti ve yıllık CSV dosyaları üretir."""
    print("[4/4] Web uygulaması çıktıları oluşturuluyor...")
    os.makedirs(os.path.join(OUTPUT_DIR, "yearly_csv"), exist_ok=True)

    harm_df["year"] = harm_df["acq_date"].dt.year
    harm_df["month"] = harm_df["acq_date"].dt.month

    harm_df["reg_lat"] = (np.floor(harm_df["lat"] / REGION_STEP_LAT) * REGION_STEP_LAT).round(2)
    harm_df["reg_lon"] = (np.floor(harm_df["lon"] / REGION_STEP_LON) * REGION_STEP_LON).round(2)

    calendar_df = (
        harm_df.groupby(["reg_lat", "reg_lon", "year", "month"], as_index=False)
        .agg(
            fire_events=("frp_harm", "count"),
            total_frp_harm=("frp_harm", "sum"),
            raw_pixels=("raw_pixels", "sum"),
            tier=("tier", lambda t: "nrt" if "nrt" in set(t) else "archive"),
        )
    )
    calendar_df["total_frp_harm"] = calendar_df["total_frp_harm"].round(1)

    # Sıkıştırılmış (Compact) İlişkisel JSON Şeması Üretimi
    base_year = int(calendar_df["year"].min())
    unique_cells = calendar_df[["reg_lat", "reg_lon"]].drop_duplicates().sort_values(["reg_lat", "reg_lon"])
    grid_list = unique_cells.values.tolist()
    cell_to_id = {(row[0], row[1]): idx for idx, row in enumerate(grid_list)}

    records = []
    for _, row in calendar_df.iterrows():
        cid = cell_to_id[(row["reg_lat"], row["reg_lon"])]
        y_off = int(row["year"]) - base_year
        t_id = 1 if row["tier"] == "nrt" else 0
        records.append([
            cid, y_off, int(row["month"]),
            int(row["fire_events"]), float(row["total_frp_harm"]),
            int(row["raw_pixels"]), t_id
        ])

    compact_summary = {
        "meta": {
            "schema": ["cell_id", "year_offset", "month", "fire_events", "total_frp_harm", "raw_pixels", "tier_id"],
            "base_year": base_year,
            "tiers": ["archive", "nrt"],
            "grid_count": len(grid_list),
            "record_count": len(records)
        },
        "grid": grid_list,
        "records": records
    }

    cal_path = os.path.join(OUTPUT_DIR, "calendar_summary.json")
    with open(cal_path, "w", encoding="utf-8") as f:
        json.dump(compact_summary, f, separators=(",", ":"))
    print(f"      -> {cal_path} ({os.path.getsize(cal_path) / (1024*1024):.2f} MB)")

    report_path = os.path.join(OUTPUT_DIR, "calibration_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(cal_report, f, indent=2, ensure_ascii=False)
    print(f"      -> {report_path} (R2={cal_report['overlap_r2_score']}, RMSE={cal_report['quantile_rmse_harm_mw']} MW)")

    export_cols = ["lat", "lon", "acq_date", "frp_harm", "frp_raw", "raw_pixels", "sensors", "tier", "daynight"]
    for year, y_df in harm_df.groupby("year"):
        y_out = y_df[export_cols].copy()
        y_out["acq_date"] = y_out["acq_date"].dt.strftime("%Y-%m-%d")
        csv_path = os.path.join(OUTPUT_DIR, "yearly_csv", f"harmonized_{year}.csv")
        y_out.to_csv(csv_path, index=False)

    print(f"İşlem tamamlandı! Tüm çıktılar '{OUTPUT_DIR}/' klasörüne kaydedildi.")


if __name__ == "__main__":
    raw_clean, f_stats = load_and_clean_raw_data()
    thermal_cells = compute_thermal_centroids(raw_clean)
    harmonized_final, calibration_info = apply_quantile_harmonization(thermal_cells, f_stats)
    export_web_assets(harmonized_final, calibration_info)