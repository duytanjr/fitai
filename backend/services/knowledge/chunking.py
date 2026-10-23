"""Chia văn bản đã làm sạch thành đoạn (chunk) ~500–800 token, chồng lấp ~12%.

Ưu tiên cắt tại đề mục, sau đó tại ranh giới đoạn văn; chỉ cắt giữa đoạn văn
(theo câu) khi một đoạn văn dài hơn giới hạn. Token được ƯỚC LƯỢNG theo ký tự
(~4 ký tự/token với tiếng Anh) vì không có tokenizer Gemini chạy offline.
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass

from services.knowledge.pdf_cleaning import CleanedDocument, TableBlock, join_hyphenated

CHARS_PER_TOKEN = 4
MIN_TOKENS = 500
MAX_TOKENS = 800
OVERLAP_RATIO = 0.12

MIN_CHARS = MIN_TOKENS * CHARS_PER_TOKEN
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN
# Phần nội dung chính chừa chỗ cho phần chồng lấp để cả đoạn không vượt MAX_TOKENS
MAX_CORE_CHARS = int(MAX_CHARS / (1 + OVERLAP_RATIO))

SENTENCE_END = re.compile(r"[.!?:”\"')\]]$")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(•\d\[])")
LIST_START = re.compile(r"^(•|\d{1,2}[.)]\s)")


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass
class Paragraph:
    text: str
    page: int
    is_heading: bool = False


@dataclass
class Chunk:
    text: str
    page: int            # trang PDF bắt đầu phần nội dung chính (không tính phần chồng lấp)
    page_end: int
    is_table: bool = False


# ── Đoạn văn ─────────────────────────────────────────────────────────────────
def _is_heading(line: str) -> bool:
    words = line.split()
    if not words or len(line) > 80 or len(words) > 12:
        return False
    if re.search(r"[.,;:–-]$", line) or not (line[0].isupper() or line[0].isdigit()):
        return False
    letters = [ch for ch in line if ch.isalpha()]
    upper_ratio = sum(ch.isupper() for ch in letters) / max(1, len(letters))
    # Đề mục: chữ in hoa toàn bộ, hoặc dạng tiêu đề ngắn (đa số từ viết hoa đầu)
    title_like = sum(w[0].isupper() for w in words if w[0].isalpha()) >= max(1, len(words) // 2)
    return upper_ratio > 0.7 or (title_like and len(words) <= 8)


def split_paragraphs(text: str, page: int, vocabulary: set[str]) -> list[Paragraph]:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return []
    typical = statistics.median(len(ln) for ln in lines)
    paragraphs: list[Paragraph] = []
    buf = ""
    buf_heading = False

    def flush() -> None:
        nonlocal buf, buf_heading
        if buf.strip():
            paragraphs.append(Paragraph(buf.strip(), page, buf_heading))
        buf, buf_heading = "", False

    prev = ""
    for line in lines:
        heading = _is_heading(line)
        prev_ended = bool(SENTENCE_END.search(prev)) and len(prev) < 0.85 * typical
        if heading != buf_heading or (not heading and (prev_ended or LIST_START.match(line))):
            flush()
            buf_heading = heading
        if not buf:
            buf = line
        elif buf.endswith("-"):
            buf = join_hyphenated(buf, line, vocabulary)
        else:
            buf = f"{buf} {line}"
        prev = line
    flush()
    return paragraphs


def _split_long(par: Paragraph) -> list[Paragraph]:
    """Tách đoạn văn dài hơn MAX_CHARS theo câu."""
    if len(par.text) <= MAX_CORE_CHARS:
        return [par]
    pieces: list[Paragraph] = []
    cur = ""
    for sentence in SENTENCE_SPLIT.split(par.text):
        if cur and len(cur) + len(sentence) + 1 > MIN_CHARS:
            pieces.append(Paragraph(cur, par.page))
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip()
    if cur:
        pieces.append(Paragraph(cur, par.page))
    return pieces


def _overlap_tail(text: str) -> str:
    """Các câu cuối của đoạn, tổng độ dài ~OVERLAP_RATIO đoạn."""
    budget = len(text) * OVERLAP_RATIO
    tail: list[str] = []
    for sentence in reversed(SENTENCE_SPLIT.split(text)):
        if tail and sum(len(s) for s in tail) + len(sentence) > budget:
            break
        tail.insert(0, sentence)
        if len(sentence) > budget:
            break
    out = " ".join(tail)
    # Một câu quá dài: cắt theo từ để không vượt ngân sách quá nhiều
    if len(out) > budget * 1.5:
        out = out[-int(budget):].split(" ", 1)[-1]
    return out


# ── Chia đoạn ────────────────────────────────────────────────────────────────
def chunk_paragraphs(paragraphs: list[Paragraph]) -> list[Chunk]:
    chunks: list[Chunk] = []
    overlap = ""
    core: list[Paragraph] = []

    def core_len() -> int:
        return sum(len(p.text) + 1 for p in core)

    def flush(with_overlap: bool) -> None:
        nonlocal overlap, core
        if not core or all(p.is_heading for p in core):
            return
        body = "\n".join(p.text for p in core)
        text = f"{overlap}\n{body}" if overlap else body
        chunks.append(Chunk(text=text, page=core[0].page, page_end=core[-1].page))
        overlap = _overlap_tail(body) if with_overlap else ""
        core = []

    queue = [piece for p in paragraphs for piece in _split_long(p)]
    while queue:
        par = queue.pop(0)
        if par.is_heading and core_len() >= MIN_CHARS:
            # Cắt tại đề mục: ranh giới tự nhiên, không chồng lấp sang mục mới
            flush(with_overlap=False)
        elif core and core_len() < MIN_CHARS and core_len() + len(par.text) > MAX_CORE_CHARS:
            # Đoạn hiện tại còn ngắn mà đoạn văn kế tiếp dài: lấy các câu đầu để lấp đầy
            room = MAX_CORE_CHARS - core_len()
            head, rest = "", []
            sentences = SENTENCE_SPLIT.split(par.text)
            for i, sentence in enumerate(sentences):
                if len(head) + len(sentence) + 1 > room:
                    rest = sentences[i:]
                    break
                head = f"{head} {sentence}".strip()
            if head and rest:
                core.append(Paragraph(head, par.page))
                queue.insert(0, Paragraph(" ".join(rest), par.page))
                flush(with_overlap=True)
                continue
            flush(with_overlap=True)
        elif core and core_len() + len(par.text) > MAX_CORE_CHARS:
            # Đề mục ở cuối đoạn được chuyển sang đoạn sau cùng nội dung của nó
            carried: list[Paragraph] = []
            while core and core[-1].is_heading:
                carried.insert(0, core.pop())
            flush(with_overlap=not carried)
            core.extend(carried)
        core.append(par)

    # Đoạn cuối quá ngắn: gộp vào đoạn trước (nếu không làm đoạn trước quá dài)
    if core and chunks and core_len() < MIN_CHARS * 0.3:
        last = chunks[-1]
        if len(last.text) + core_len() <= MAX_CHARS * 1.15:
            last.text += "\n" + "\n".join(p.text for p in core)
            last.page_end = core[-1].page
            core = []
    flush(with_overlap=False)
    return chunks


def chunk_table(table: TableBlock) -> list[Chunk]:
    """Mỗi đoạn bảng lặp lại tiêu đề bảng; không cắt giữa một hàng."""
    rendered = table.render().split("\n")
    title, rows = rendered[0], rendered[1:]
    chunks: list[Chunk] = []
    cur: list[str] = []
    for row in rows:
        if cur and len(title) + sum(len(r) + 1 for r in cur) + len(row) > MAX_CHARS:
            chunks.append(Chunk("\n".join([title, *cur]), table.page, table.page, is_table=True))
            cur = []
        cur.append(row)
    if cur:
        chunks.append(Chunk("\n".join([title, *cur]), table.page, table.page, is_table=True))
    return chunks


def chunk_document(doc: CleanedDocument) -> list[Chunk]:
    paragraphs = [
        par for page in doc.pages for par in split_paragraphs(page.text, page.number, doc.vocabulary)
    ]
    chunks = chunk_paragraphs(paragraphs)
    for table in doc.tables:
        chunks.extend(chunk_table(table))
    return chunks
