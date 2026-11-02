"""
Tạo data/foods/usda_selected.csv từ USDA FoodData Central SR Legacy (CC0) — CHỈ các fdc_id đã duyệt
(services/foods/usda.py: USDA_SELECTION). Mã chất dinh dưỡng tra từ nutrient.csv theo tên + đơn vị.

/app/data được mount chỉ đọc trong container, nên ghi ra /tmp rồi chép về:
  docker compose exec backend python scripts/build_usda_subset.py --out /tmp/usda_selected.csv
  docker cp fitai_backend:/tmp/usda_selected.csv data/foods/usda_selected.csv
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.foods.usda import build_subset, nutrient_ids, write_subset_csv

DEFAULT_SR = Path("data/foods/external/FoodData_Central_sr_legacy_food_csv_2018-04")


def main() -> int:
    p = argparse.ArgumentParser(description="Tạo file con USDA đã duyệt")
    p.add_argument("--sr-dir", type=Path, default=DEFAULT_SR)
    p.add_argument("--out", type=Path, default=Path("data/foods/usda_selected.csv"))
    args = p.parse_args()
    if not (args.sr_dir / "food.csv").is_file():
        print(f"❌ Không thấy SR Legacy tại {args.sr_dir}")
        return 1
    print("Mã chất (nutrient.csv):", nutrient_ids(args.sr_dir))
    rows = build_subset(args.sr_dir)
    write_subset_csv(rows, args.out)
    print(f"✅ {len(rows)} dòng → {args.out}")
    for r in rows:
        flags = json.loads(r["quality_flags"])
        extra = [k for k in flags if k != "nang_luong_he_so_rieng"]
        energy = flags.get("nang_luong_he_so_rieng", "")
        print(f"  {r['fdc_id']} | {r['name_vi']} | {r['energy_kcal']:g} kcal | carb_g {r['carb_g']} | "
              f"prep_auto {r['preparation_auto']} | năng lượng: {'khớp' if '— khớp' in energy else energy[-40:]}"
              + (f" | cờ khác: {extra}" if extra else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
