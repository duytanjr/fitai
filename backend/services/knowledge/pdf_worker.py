"""Tiến trình con đọc PDF (gọi bởi pdf_guard; KHÔNG import core.config hay bất kỳ cấu hình/bí mật nào).

In đúng MỘT dòng JSON cuối cùng ra stdout: kết quả, hoặc {"error": "<mã ngắn>"}.
"""
from __future__ import annotations

import json
import logging
import sys


def _inspect(path: str, max_pages: int) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(path)
    if reader.is_encrypted:
        return {"error": "pdf_ma_hoa"}
    pages = len(reader.pages)
    if pages > max_pages:
        return {"error": "qua_nhieu_trang"}
    if pages == 0:
        return {"error": "pdf_khong_doc_duoc"}
    return {"pages_total": pages}


def _chunks(path: str, max_pages: int) -> dict:
    from pathlib import Path

    from services.knowledge.chunking import chunk_document
    from services.knowledge.pdf_cleaning import clean_document, extract_pages

    info = _inspect(path, max_pages)
    if "error" in info:
        return info
    doc = clean_document(extract_pages(Path(path)))
    chunks = chunk_document(doc)
    return {
        "pages_total": doc.total_pages, "pages_kept": len(doc.pages), "pages_skipped": len(doc.skipped),
        "chunks": [{"text": c.text, "page": c.page, "page_end": c.page_end, "is_table": c.is_table} for c in chunks],
    }


def main(argv: list[str]) -> int:
    logging.disable(logging.CRITICAL)        # pypdf cảnh báo font: không in ra
    mode, path, max_pages = argv[0], argv[1], int(argv[2])
    try:
        result = (_inspect if mode == "inspect" else _chunks)(path, max_pages)
    except MemoryError:
        result = {"error": "pdf_khong_doc_duoc"}
    except Exception:  # noqa: BLE001 — chỉ trả mã ngắn, không stack trace
        result = {"error": "pdf_khong_doc_duoc"}
    sys.stdout.write("\n" + json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
