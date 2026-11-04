"""Tạo PDF nhỏ bằng code cho test (không cần thư viện ngoài): văn bản ASCII, font Helvetica.

make_pdf(pages) → bytes; encrypt_pdf(data) dùng pypdf để mã hoá; blank_pdf(n) tạo n trang trắng.
"""
from __future__ import annotations

import io
import textwrap

NUTRITION_PARAGRAPHS = [
    "Protein intake for adults who train regularly is often discussed in grams per kilogram of body mass per "
    "day. This hypothetical guide describes general ranges only and is not medical advice.",
    "Vegetables, fruits, whole grains and legumes provide fibre, vitamins and minerals. A varied plate with "
    "several colours is a simple way to describe a balanced meal in this sample document.",
    "Hydration needs depend on climate, body size and activity. Drinking water regularly through the day is a "
    "common recommendation in many public health materials, according to this invented text.",
    "Energy balance describes the relation between energy eaten and energy used. Body weight changes slowly and "
    "daily measurements fluctuate because of water and food in the gut.",
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    """Mỗi phần tử là văn bản một trang (ASCII); tự xuống dòng ~95 ký tự."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")           # điền sau
    pages_id = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = []
    for text in pages:
        lines = [l for para in text.split("\n") for l in (textwrap.wrap(para, 95) or [""])]
        ops = ["BT", "/F1 10 Tf", "13 TL", "40 800 Td"] + [f"({_escape(l)}) Tj T*" for l in lines] + ["ET"]
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                        b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (pages_id, content, font)))
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objects[pages_id - 1] = (b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids)
                             + b"] /Count %d >>" % len(kids))
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref))
    return out.getvalue()


def sample_pages(n: int = 3, tag: str = "", extra: str = "") -> list[str]:
    """n trang văn bản dinh dưỡng giả định (mỗi trang khác nhau để không bị coi là trùng lặp/đầu trang)."""
    pages = []
    for i in range(n):
        paras = [f"Section {i + 1}{tag}: sample nutrition notes, page {i + 1}."]
        paras += [f"{p} (part {i + 1}.{j + 1}{tag})" for j, p in enumerate(NUTRITION_PARAGRAPHS * 3)]
        if extra and i == 0:
            paras.insert(len(paras) // 2, extra)     # giữa trang 1: không bị coi là đầu/chân trang lặp lại
        pages.append("\n".join(paras))
    return pages


def encrypt_pdf(data: bytes, password: str = "secret") -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password=password, owner_password=password, algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def blank_pdf(n: int) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(n):
        writer.add_blank_page(width=595, height=842)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
