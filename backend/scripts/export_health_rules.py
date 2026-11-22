"""
Xuất bảng cảnh báo theo bệnh lý (services/health_rules.py) dạng Markdown cho tài liệu đồ án.

  docker compose exec backend python scripts/export_health_rules.py            # in ra màn hình
  docker compose exec backend python scripts/export_health_rules.py --csv      # dạng CSV

Chỉ đọc hằng số trong code, không đọc DB, không gọi mạng. Dán kết quả vào docs/CHI_SO_CAN_CU.md (mục c).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.profile import MEDICAL_CONDITION_LABELS  # noqa: E402
from services.health_rules import DOMAIN_LABELS, rules_table  # noqa: E402

HEADERS = ["id", "Bệnh", "Lĩnh vực", "Nội dung cảnh báo", "Nguồn"]


def rows() -> list[list[str]]:
    out = []
    for r in rules_table():
        conditions = ", ".join(f"{c} ({MEDICAL_CONDITION_LABELS[c]})" for c in r["conditions"])
        source = r["source"]
        if r["source_url"]:
            updated = f", cập nhật {r['source_updated']}" if r["source_updated"] else ""
            source = (f"{source}; năm {r['source_year']}{updated}; {r['source_url']}; "
                      f"file {r['source_file']}")
        out.append([r["id"], conditions, DOMAIN_LABELS[r["domain"]], r["message"], source])
    return out


def markdown() -> str:
    def cell(v: str) -> str:
        return v.replace("|", "\\|")
    lines = ["| " + " | ".join(HEADERS) + " |", "|" + "---|" * len(HEADERS)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows()]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--csv", action="store_true", help="xuất CSV thay vì Markdown")
    args = parser.parse_args()
    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(HEADERS)
        writer.writerows(rows())
    else:
        print(markdown())


if __name__ == "__main__":
    main()
