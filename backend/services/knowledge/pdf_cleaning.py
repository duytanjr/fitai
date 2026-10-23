"""Trích xuất và làm sạch văn bản PDF theo từng trang (giữ số trang PDF, đếm từ 1).

Hai chế độ trích xuất của pypdf được dùng song song:
- "plain": giữ đúng thứ tự đọc của bố cục nhiều cột (đọc hết cột trái rồi cột phải),
  dùng cho văn bản thường.
- "layout": giữ vị trí ngang của chữ (cột cách nhau bằng nhiều khoảng trắng),
  chỉ dùng để dựng lại bảng (Table N) thành từng hàng/cột.
"""
from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_PAGE_CHARS = 200            # ít hơn số ký tự chữ/số này → "gần như không có chữ"
DUPLICATE_CONTAINMENT = 0.95    # tỷ lệ shingle của trang nằm trong một trang trước đó
EDGE_LINES = 3                  # số dòng đầu/cuối trang xét làm đầu trang/chân trang

COVER_MARKERS = ("to cite this article", "journal homepage", "full terms & conditions")
COPYRIGHT_MARKERS = ("some rights reserved", "cataloguing-in-publication", "suggested citation")
CONTENTS_HEADINGS = {"contents", "table of contents"}
ACK_HEADINGS = {"acknowledgements", "acknowledgments"}
# Đề mục phần phụ cuối bài báo: cắt từ đề mục đến hết trang (chỉ xét ở nửa sau tài liệu)
BACK_MATTER_HEADINGS = ACK_HEADINGS | {
    "funding",
    "competing interests",
    "author details",
    "authors’ contributions",
    "authors' contributions",
    "consent for publication",
    "availability of data and materials",
    "ethics approval and consent to participate",
    "references",
}
MAX_TABLE_COLUMNS = 6
REFERENCE_LINE = re.compile(r"^\d{1,3}\.\s+\S")
# Dấu hiệu dòng trích dẫn: năm xuất bản kèm ';' / ':số' / doi / http / et al.
CITATION_FEATURE = re.compile(r"\b(19|20)\d{2}\b.*(;|:\s*\d|doi|http|et al)|et al\.|doi\.org", re.I)
TABLE_CAPTION = re.compile(r"^Table\s+(\d+)[.:]?\s+([A-Z].*)$")
URL_FOOTNOTE = re.compile(r"^\s*((available online at\s+)?https?://\S+|DOI\s+10\.\S+)\s*$", re.I)
# Dòng chỉ có số trang, vd. "34 35" hoặc số La Mã "vi vii"
PAGE_NUMBER_LINE = re.compile(r"\s*(\d{1,3}|[ivxl]{1,5})(\s+(\d{1,3}|[ivxl]{1,5}))?\s*")
BULLET_GLYPHS ="\uf0b7\uf0a7\u25aa\u25cf"


@dataclass
class RawPage:
    number: int          # số trang PDF, đếm từ 1
    text: str            # chế độ plain
    layout: str = ""     # chế độ layout (chỉ cần cho trang có bảng)


@dataclass
class TableBlock:
    page: int
    number: int
    caption: str
    header: list[str]
    rows: list[list[str]]
    parsed: bool                     # False → không dựng được hàng/cột, giữ chữ thô
    raw_lines: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Hiển thị mỗi hàng thành 'tên cột: giá trị' để số liệu không bị trộn ô.

        Chỉ giữ ngôn ngữ gốc của tài liệu: một câu dẫn tiếng Việt chung cho mọi bảng
        làm embedding của bảng giống mọi câu hỏi tiếng Việt (đã đo bằng rag_smoke).
        Cảnh báo "dữ liệu bảng" do agent thêm khi hiển thị, dựa vào cờ is_table.
        """
        title = f"[Table {self.number} — {self.caption}]"
        if not self.parsed:
            return title + "\n" + "\n".join(self.raw_lines)
        lines = [title]
        for row in self.rows:
            cells = [f"{h}: {v}" for h, v in zip(self.header, row) if v]
            lines.append("- " + "; ".join(cells))
        return "\n".join(lines)


@dataclass
class CleanPage:
    number: int
    text: str


@dataclass
class SkippedPage:
    number: int
    reason: str


@dataclass
class CleanedDocument:
    total_pages: int
    pages: list[CleanPage]
    tables: list[TableBlock]
    skipped: list[SkippedPage]
    notes: list[str]                 # các cắt bỏ một phần trang, đầu/chân trang đã bỏ
    vocabulary: set[str]


# ── Trích xuất ────────────────────────────────────────────────────────────────
def extract_pages(pdf_path: Path) -> list[RawPage]:
    """Đọc PDF, trả văn bản từng trang ở cả hai chế độ plain và layout."""
    from pypdf import PdfReader

    # pypdf cảnh báo rất nhiều về font CFF; không ảnh hưởng nội dung đã kiểm tra
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(str(pdf_path))
    pages: list[RawPage] = []
    for i, page in enumerate(reader.pages, start=1):
        plain = page.extract_text() or ""
        layout = ""
        if re.search(r"^Table\s+\d+", plain, re.MULTILINE):
            layout = page.extract_text(extraction_mode="layout") or ""
        pages.append(RawPage(number=i, text=plain, layout=layout))
    return pages


# ── Chuẩn hoá ─────────────────────────────────────────────────────────────────
def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    for glyph in BULLET_GLYPHS:
        text = text.replace(glyph, "•")
    text = re.sub(r"(\d) +([–-])(\d)", r"\1\2\3", text)   # "8 –15" → "8–15"
    text = re.sub(r"(\w) ’(\w)", r"\1’\2", text)          # "body ’s" → "body’s"
    return text


def _lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.split("\n")]


def _edge_key(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.strip().lower()))


def _letters(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def _shingles(text: str, n: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _is_reference_list(lines: list[str]) -> bool:
    """Trang là danh mục tham khảo: ≥5 mục đánh số và ≥5 dòng mang dấu hiệu trích dẫn
    (tránh nhầm với danh sách bước đánh số trong nội dung)."""
    numbered = sum(bool(REFERENCE_LINE.match(ln.strip())) for ln in lines)
    citations = sum(bool(CITATION_FEATURE.search(ln)) for ln in lines)
    return numbered >= 5 and citations >= 5


def _first_line(lines: list[str]) -> str:
    return next((ln.strip() for ln in lines if ln.strip()), "")


def build_vocabulary(texts: list[str]) -> set[str]:
    """Từ vựng của tài liệu: các từ đơn và các từ ghép có gạch nối nằm GIỮA dòng
    (vd. "vigorous-intensity"), dùng để phân biệt gạch nối thật với gạch ngắt dòng."""
    vocab: set[str] = set()
    for t in texts:
        vocab.update(w.lower() for w in re.findall(r"[A-Za-z]+", t))
        vocab.update(w.lower() for w in re.findall(r"[A-Za-z]+-[A-Za-z]+", t))
    return vocab


def join_hyphenated(left: str, right: str, vocabulary: set[str]) -> str:
    """Nối hai dòng khi dòng trái kết thúc bằng '-'.

    Giữ gạch nối nếu từ ghép có gạch xuất hiện giữa dòng ở chỗ khác trong tài liệu
    (vd. "vigorous-" + "intensity"); ngược lại coi là gạch ngắt dòng và bỏ đi
    (vd. "There-" + "fore", "com-" + "prehensiveness").
    """
    m_left = re.search(r"([A-Za-z]+)-$", left)
    m_right = re.match(r"([a-z]+)", right)
    if m_left and m_right:
        a, b = m_left.group(1).lower(), m_right.group(1).lower()
        if f"{a}-{b}" not in vocabulary or f"{a}{b}" in vocabulary:
            return left[:-1] + right
    return left + right


# ── Bảng ──────────────────────────────────────────────────────────────────────
def _segments(line: str) -> list[tuple[int, str]]:
    """Tách một dòng chế độ layout thành các ô (cách nhau ≥3 khoảng trắng) kèm vị trí."""
    return [(m.start(), m.group(0)) for m in re.finditer(r"\S+(?: {1,2}\S+)*", line)]


def parse_layout_table(layout_text: str, number: int, page: int, vocabulary: set[str]) -> TableBlock | None:
    """Dựng lại bảng `Table {number}` từ văn bản chế độ layout của một trang."""
    lines = _lines(_normalize(layout_text))
    start = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^\s*Table\s+{number}\b", ln)), None
    )
    if start is None:
        return None
    caption_match = TABLE_CAPTION.match(lines[start].strip())
    caption = re.sub(
        r"\s+", " ", caption_match.group(2) if caption_match else lines[start]
    ).strip()

    body: list[str] = []
    for ln in lines[start + 1 :]:
        if not ln.strip():
            if body:
                break
            continue
        body.append(ln)
    raw_lines = [re.sub(r"\s{3,}", " | ", ln.strip()) for ln in body]
    if len(body) < 2:
        return TableBlock(page, number, caption, [], [], parsed=False, raw_lines=raw_lines)

    # Vùng ngang của từng cột: lấy từ những dòng (bỏ dòng tiêu đề đầu) có đủ số ô nhất
    seg_lines = [_segments(ln) for ln in body]
    ncols = max(len(s) for s in seg_lines[1:]) if len(seg_lines) > 1 else 0
    full = [s for s in seg_lines[1:] if len(s) == ncols]
    if ncols < 2 or ncols > MAX_TABLE_COLUMNS or not full:
        return TableBlock(page, number, caption, [], [], parsed=False, raw_lines=raw_lines)
    spans = [
        (min(s[c][0] for s in full), max(s[c][0] + len(s[c][1]) for s in full))
        for c in range(ncols)
    ]

    def column_of(start: int, end: int) -> int:
        overlaps = [max(0, min(end, hi) - max(start, lo)) for lo, hi in spans]
        if max(overlaps) > 0:
            return overlaps.index(max(overlaps))
        distances = [lo - end if end <= lo else start - hi for lo, hi in spans]
        return distances.index(min(distances))

    def to_cells(line: str, segs: list[tuple[int, str]]) -> list[str]:
        if len(segs) == ncols:
            return [txt for _, txt in segs]
        # Dòng thiếu ô (ô nhiều dòng): gán từng từ vào cột theo vị trí ngang
        cells: list[list[str]] = [[] for _ in range(ncols)]
        for m in re.finditer(r"\S+", line):
            cells[column_of(m.start(), m.end())].append(m.group(0))
        return [" ".join(c) for c in cells]

    line_cells = [to_cells(ln, s) for ln, s in zip(body, seg_lines)]

    # Hàng tiêu đề: dòng đầu + các dòng tiếp theo có cột đầu trống. Tiêu đề cột số
    # thường không thẳng hàng với số (số căn phải) nên không gán theo vị trí:
    # dòng đầu gán từ trái sang, dòng tiêu đề phụ gán từ phải sang.
    n_header = 1
    while n_header < len(line_cells) and not line_cells[n_header][0]:
        n_header += 1
    for h in range(n_header):
        texts = [txt for _, txt in seg_lines[h]]
        if len(texts) < ncols:
            pad = [""] * (ncols - len(texts))
            line_cells[h] = texts + pad if h == 0 else pad + texts
    header = [
        re.sub(r"(\w+:)\1", r"\1", " ".join(cells[c] for cells in line_cells[:n_header] if cells[c])).strip()
        for c in range(ncols)
    ]

    data = line_cells[n_header:]
    # Không tin được kết quả nếu có cột không tên (thường là bảng ma trận/ô gộp)
    if not data or not all(header):
        return TableBlock(page, number, caption, [], [], parsed=False, raw_lines=raw_lines)

    multiline = any(not cells[0] for cells in data)
    rows: list[list[list[str]]] = []
    prev_first_empty = True
    for cells in data:
        first_filled = bool(cells[0])
        if not rows or not multiline or (first_filled and prev_first_empty):
            rows.append([[] for _ in range(ncols)])
        for c in range(ncols):
            rows[-1][c].append(cells[c])
        prev_first_empty = not first_filled

    def join_cell(parts: list[str]) -> str:
        out = ""
        for part in filter(None, parts):
            if not out:
                out = part
            elif out.endswith("-"):
                out = join_hyphenated(out, part, vocabulary)
            else:
                out = f"{out} {part}"
        return out.strip()

    joined = [[join_cell(c) for c in row] for row in rows]
    return TableBlock(page, number, caption, header, joined, parsed=True, raw_lines=raw_lines)


def _strip_table_from_plain(lines: list[str], caption_idx: int, table: TableBlock) -> list[str]:
    """Bỏ các dòng của bảng khỏi văn bản plain: từ dòng chú thích bảng, liên tiếp
    các dòng có mặt trong nội dung bảng (so sánh sau khi bỏ hết khoảng trắng)."""
    blob = re.sub(r"[\s|]+", "", " ".join(table.raw_lines))
    end = caption_idx + 1
    while end < len(lines):
        key = re.sub(r"\s+", "", lines[end])
        if key and key not in blob:
            break
        end += 1
    return lines[:caption_idx] + lines[end:]


# ── Làm sạch ──────────────────────────────────────────────────────────────────
def clean_document(raw_pages: list[RawPage]) -> CleanedDocument:
    total = len(raw_pages)
    page_lines = {p.number: _lines(_normalize(p.text)) for p in raw_pages}
    vocabulary = build_vocabulary([p.text for p in raw_pages])
    skipped: list[SkippedPage] = []
    notes: list[str] = []
    second_half = lambda n: n > total / 2  # noqa: E731

    # 1. Đầu trang / chân trang lặp lại: dòng ở mép trang xuất hiện trên nhiều trang
    edge_counts: Counter[str] = Counter()
    for lines in page_lines.values():
        non_empty = [ln for ln in lines if ln.strip()]
        edges = {_edge_key(ln) for ln in non_empty[:EDGE_LINES] + non_empty[-EDGE_LINES:]}
        edge_counts.update(edges)
    threshold = max(3, math.ceil(0.2 * total))
    repeated = {k for k, c in edge_counts.items() if c >= threshold and len(k) <= 100}
    if repeated:
        notes.append(
            "Bỏ đầu/chân trang lặp lại: " + "; ".join(sorted(f"'{k}'" for k in repeated))
        )

    def strip_edges(lines: list[str]) -> list[str]:
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        edge_idx = set(idx[:EDGE_LINES] + idx[-EDGE_LINES:])
        return [
            ln
            for i, ln in enumerate(lines)
            if not (i in edge_idx and _edge_key(ln) in repeated)
            and not PAGE_NUMBER_LINE.fullmatch(ln)
            and not URL_FOOTNOTE.match(ln)
        ]

    kept: list[CleanPage] = []
    tables: list[TableBlock] = []
    kept_shingles: list[tuple[int, set]] = []
    after_references = False

    for raw in raw_pages:
        n = raw.number
        lines = strip_edges(page_lines[n])
        text_lower = "\n".join(lines).lower()
        first = _first_line(lines).lower()

        if after_references:
            reason = (
                "danh mục tài liệu tham khảo"
                if any(REFERENCE_LINE.match(ln.strip()) for ln in lines)
                else "phần phụ sau danh mục tham khảo (phụ lục danh sách thành viên/khai báo lợi ích)"
            )
            skipped.append(SkippedPage(n, reason))
            continue
        if any(m in text_lower for m in COVER_MARKERS):
            skipped.append(SkippedPage(n, "trang bìa tạp chí/nhà xuất bản"))
            continue
        if any(m in text_lower for m in COPYRIGHT_MARKERS):
            skipped.append(SkippedPage(n, "trang bản quyền/thông tin xuất bản"))
            continue
        if first in CONTENTS_HEADINGS:
            skipped.append(SkippedPage(n, "mục lục"))
            continue
        if first in ACK_HEADINGS and not second_half(n):
            skipped.append(SkippedPage(n, "lời cảm ơn (danh sách người đóng góp)"))
            continue
        if second_half(n) and _is_reference_list(lines):
            after_references = True
            skipped.append(SkippedPage(n, "danh mục tài liệu tham khảo"))
            continue

        # Phần phụ cuối bài (lời cảm ơn, tài trợ, ..., tài liệu tham khảo) giữa trang
        if second_half(n):
            cut = next(
                (i for i, ln in enumerate(lines) if ln.strip().lower() in BACK_MATTER_HEADINGS),
                None,
            )
            if cut is not None:
                heading = lines[cut].strip()
                if any(ln.strip().lower() == "references" for ln in lines[cut:]):
                    after_references = True
                lines = lines[:cut]
                if _letters("\n".join(lines)) < MIN_PAGE_CHARS:
                    skipped.append(
                        SkippedPage(n, f"phần phụ cuối bài/tài liệu tham khảo (từ đề mục '{heading}')")
                    )
                    continue
                notes.append(f"tr. PDF {n}: cắt từ đề mục '{heading}' đến hết trang (phần phụ cuối bài)")

        # Bảng: tách thành khối riêng, bỏ khỏi văn bản thường
        for i in range(len(lines) - 1, -1, -1):
            m = TABLE_CAPTION.match(lines[i].strip())
            if not m or not raw.layout:
                continue
            table = parse_layout_table(raw.layout, int(m.group(1)), n, vocabulary)
            if table is None:
                continue
            lines = _strip_table_from_plain(lines, i, table)
            if table.parsed:
                tables.append(table)
            else:
                # Không nạp bảng không dựng lại được hàng/cột để tránh số liệu bị trộn ô
                notes.append(
                    f"tr. PDF {n}: Bảng {table.number} ('{table.caption}') không dựng lại được "
                    "hàng/cột → KHÔNG nạp (đã bỏ khỏi văn bản trang)"
                )

        text = "\n".join(lines).strip()
        if _letters(text) < MIN_PAGE_CHARS and not any(t.page == n for t in tables):
            skipped.append(SkippedPage(n, "gần như không có chữ"))
            continue

        sh = _shingles(text)
        dup_of = next(
            (
                num
                for num, other in kept_shingles
                if sh and len(sh & other) / len(sh) >= DUPLICATE_CONTAINMENT
            ),
            None,
        )
        if dup_of is not None:
            skipped.append(SkippedPage(n, f"trùng lặp nội dung với tr. PDF {dup_of}"))
            continue

        kept_shingles.append((n, sh))
        kept.append(CleanPage(number=n, text=text))

    tables.sort(key=lambda t: (t.page, t.number))
    return CleanedDocument(
        total_pages=total,
        pages=kept,
        tables=tables,
        skipped=skipped,
        notes=notes,
        vocabulary=vocabulary,
    )
