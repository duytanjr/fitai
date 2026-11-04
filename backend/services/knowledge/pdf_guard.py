"""Bộ bảo vệ PDF: mọi lần mở PDF do người dùng tải lên đều chạy trong TIẾN TRÌNH CON.

- Môi trường tối thiểu (không thừa hưởng GOOGLE_API_KEY, SECRET_KEY hay biến nào khác của backend).
- Giới hạn bộ nhớ ảo (RLIMIT_AS, Linux) và thời gian chờ; quá hạn thì tiến trình con bị giết.
- Không thực thi gì từ file: chỉ pypdf đọc văn bản. Lỗi trả về là MÃ NGẮN, không đường dẫn hay stack trace.

Hai chế độ của tiến trình con (`python -m services.knowledge.pdf_worker <mode> <path> <max_pages>`):
- inspect: kiểm tra mã hoá và số trang (khi tải lên).
- chunks: trích xuất + làm sạch + chia đoạn (xem trước, lập chỉ mục) — cùng pipeline với script ingest.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PDF_MAGIC = b"%PDF-"

# Mã lỗi ngắn (lưu vào knowledge_documents.error_code / trả trong API)
ERR_NOT_PDF = "khong_phai_pdf"
ERR_ENCRYPTED = "pdf_ma_hoa"
ERR_TOO_MANY_PAGES = "qua_nhieu_trang"
ERR_UNREADABLE = "pdf_khong_doc_duoc"
ERR_TIMEOUT = "het_thoi_gian_doc"
ERR_NO_CHUNKS = "khong_co_doan"
ERR_FILE_MISSING = "thieu_file"


class PdfGuardError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class PdfInfo:
    pages_total: int


@dataclass
class ChunkData:
    text: str
    page: int
    page_end: int
    is_table: bool


@dataclass
class ParsedDocument:
    pages_total: int
    pages_kept: int
    pages_skipped: int
    chunks: list[ChunkData] = field(default_factory=list)


def has_pdf_magic(head: bytes) -> bool:
    return head.startswith(PDF_MAGIC)


def _minimal_env() -> dict[str, str]:
    """Chỉ những biến cần để chạy Python và import code; KHÔNG có khoá API hay bí mật."""
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(BACKEND_ROOT), "LANG": "C.UTF-8",
            "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}


def _limit_memory() -> None:  # pragma: no cover — chạy trong tiến trình con
    try:
        import resource

        limit = settings.KNOWLEDGE_PDF_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        pass


def _run_worker(mode: str, path: Path, max_pages: int, timeout: float | None = None) -> dict:
    if not path.is_file():
        raise PdfGuardError(ERR_FILE_MISSING)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "services.knowledge.pdf_worker", mode, str(path), str(max_pages)],
            env=_minimal_env(), cwd=str(BACKEND_ROOT), capture_output=True, stdin=subprocess.DEVNULL,
            timeout=timeout or settings.KNOWLEDGE_PDF_TIMEOUT_S,
            preexec_fn=_limit_memory if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        raise PdfGuardError(ERR_TIMEOUT) from None
    try:
        result = json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise PdfGuardError(ERR_UNREADABLE) from None        # tiến trình con chết (vd. hết bộ nhớ)
    if "error" in result:
        raise PdfGuardError(result["error"])
    return result


def inspect_pdf(path: Path, max_pages: int | None = None, timeout: float | None = None) -> PdfInfo:
    """Mã hoá → pdf_ma_hoa; quá số trang → qua_nhieu_trang; hỏng → pdf_khong_doc_duoc."""
    res = _run_worker("inspect", path, max_pages or settings.KNOWLEDGE_MAX_PDF_PAGES, timeout)
    return PdfInfo(pages_total=res["pages_total"])


def parse_pdf(path: Path, max_pages: int | None = None, timeout: float | None = None) -> ParsedDocument:
    """Trích xuất, làm sạch và chia đoạn (KHÔNG nhúng). Cùng giới hạn trang và thời gian chờ."""
    res = _run_worker("chunks", path, max_pages or settings.KNOWLEDGE_MAX_PDF_PAGES, timeout)
    doc = ParsedDocument(pages_total=res["pages_total"], pages_kept=res["pages_kept"],
                         pages_skipped=res["pages_skipped"],
                         chunks=[ChunkData(**c) for c in res["chunks"]])
    if not doc.chunks:
        raise PdfGuardError(ERR_NO_CHUNKS)
    return doc
