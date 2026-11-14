import json
import os
from pathlib import Path


def compress_calendar_summary(
    input_path: str = "calendar_summary.json",
    output_path: str = "calendar_summary.compact.json",
) -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        raw_records = json.load(f)

    # 1. Tekil (reg_lat, reg_lon) koordinatlarını deterministik sözlük tablosuna al
    unique_coords = sorted({(r["reg_lat"], r["reg_lon"]) for r in raw_records})
    coord_to_id = {coord: idx for idx, coord in enumerate(unique_coords)}

    # 2. Tier sınıflarını indeksle (ileride yeni tier eklenirse otomatik kapsar)
    default_tiers = ["archive", "nrt"]
    extra_tiers = sorted({r["tier"] for r in raw_records if r["tier"] not in default_tiers})
    tier_list = default_tiers + extra_tiers
    tier_to_id = {t: idx for idx, t in enumerate(tier_list)}

    # 3. Kayıtları kronolojik ve mekânsal olarak sırala (ön yüzde ikili arama / dilimleme için)
    sorted_records = sorted(
        raw_records,
        key=lambda r: (r["year"], r["month"], r["reg_lat"], r["reg_lon"], r["tier"]),
    )

    base_year = 2000

    # 4. Sütun bazlı sıkıştırılmış kayıt dizisi:
    # [cell_id, year_offset, month, fire_events, total_frp_harm, raw_pixels, tier_id]
    compact_records = [
        [
            coord_to_id[(r["reg_lat"], r["reg_lon"])],
            r["year"] - base_year,
            r["month"],
            r["fire_events"],
            round(float(r["total_frp_harm"]), 2),
            r["raw_pixels"],
            tier_to_id[r["tier"]],
        ]
        for r in sorted_records
    ]

    payload = {
        "meta": {
            "schema": [
                "cell_id",
                "year_offset",
                "month",
                "fire_events",
                "total_frp_harm",
                "raw_pixels",
                "tier_id",
            ],
            "base_year": base_year,
            "tiers": tier_list,
            "grid_count": len(unique_coords),
            "record_count": len(compact_records),
        },
        "grid": [[lat, lon] for lat, lon in unique_coords],
        "records": compact_records,
    }

    compact_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    Path(output_path).write_text(compact_json, encoding="utf-8")

    # 5. Kayıpsız doğrulama (Round-trip kontrolü)
    decoded = json.loads(compact_json)
    reconstructed = [
        {
            "reg_lat": decoded["grid"][rec[0]][0],
            "reg_lon": decoded["grid"][rec[0]][1],
            "year": decoded["meta"]["base_year"] + rec[1],
            "month": rec[2],
            "fire_events": rec[3],
            "total_frp_harm": rec[4],
            "raw_pixels": rec[5],
            "tier": decoded["meta"]["tiers"][rec[6]],
        }
        for rec in decoded["records"]
    ]
    assert reconstructed == sorted_records, "Hata: Sıkıştırılan veri orijinaliyle birebir eşleşmiyor!"

    orig_bytes = os.path.getsize(input_path)
    new_bytes = os.path.getsize(output_path)
    ratio = (1 - new_bytes / orig_bytes) * 100

    print(f"Orijinal boyut : {orig_bytes:,} bayt ({orig_bytes / 1024:.1f} KB)")
    print(f"Sıkışmış boyut : {new_bytes:,} bayt ({new_bytes / 1024:.1f} KB)")
    print(f"Tasarruf oranı : %{ratio:.2f} | Doğrulama: BAŞARILI")


if __name__ == "__main__":
    compress_calendar_summary()