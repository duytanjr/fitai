"""Tests cho làm sạch PDF và chia đoạn (dữ liệu tổng hợp, không đọc PDF thật, không gọi API)."""
import re

from services.knowledge.chunking import MAX_TOKENS, chunk_document, estimate_tokens
from services.knowledge.ingest import build_records, chunk_id
from services.knowledge.pdf_cleaning import (
    RawPage,
    build_vocabulary,
    clean_document,
    join_hyphenated,
    parse_layout_table,
)

FOOTER = "Journal of Sports Nutrition (2017) 14:16 Page {n} of 10"
SOURCE = {
    "file": "sample.pdf",
    "title": "Sample position stand",
    "authors_org": "ISSN",
    "year": "2017",
    "language": "en",
    "topic": "protein, giảm cân",
    "notes": "đối tượng: người tập luyện",
}


def body(page: int, sentences: int = 30) -> str:
    """Văn bản nội dung có đánh dấu trang (P{page}) trong từng câu."""
    lines = []
    for k in range(sentences):
        lines.append(f"Marker P{page} sentence {k} discusses protein intake and energy balance.")
    return "\n".join(lines)


def references_page(start: int) -> str:
    return "\n".join(
        f"{start + i}. Smith J, Doe A, et al. Protein and lean mass. J Nutr. 2015;12:{i}0–9."
        for i in range(12)
    )


def sample_pages() -> list[RawPage]:
    pages = {
        1: "To cite this article: Sample et al.\nJournal homepage: example.org\n" + "x " * 50,
        2: body(2),
        3: body(3),
        4: body(3),  # trùng lặp với trang 3
        5: body(5),
        6: "12",      # gần như không có chữ
        7: body(7, 10) + "\nAcknowledgements\nWe thank everyone.\nReferences\n1. A B. Title. J X. 2001;1:1.",
        8: references_page(2),
        9: references_page(14),
        10: "Appendix: list of members\nDr A\nDr B",
    }
    return [
        RawPage(number=n, text=f"{text}\n{FOOTER.format(n=n)}") for n, text in pages.items()
    ]


# ── Làm sạch ─────────────────────────────────────────────────────────────────
def test_cleaning_skips_cover_references_duplicates_and_empty_pages():
    doc = clean_document(sample_pages())
    reasons = {s.number: s.reason for s in doc.skipped}

    assert "bìa" in reasons[1]
    assert "trùng lặp" in reasons[4] and "tr. PDF 3" in reasons[4]
    assert "gần như không có chữ" in reasons[6]
    assert "tham khảo" in reasons[8]
    assert "tham khảo" in reasons[9]
    assert 10 in reasons  # phần phụ sau danh mục tham khảo

    kept = [p.number for p in doc.pages]
    assert kept == [2, 3, 5, 7]


def test_cleaning_removes_repeated_footer_and_back_matter():
    doc = clean_document(sample_pages())
    all_text = "\n".join(p.text for p in doc.pages)
    assert "Journal of Sports Nutrition" not in all_text
    # Trang 7: giữ nội dung trước "Acknowledgements", bỏ phần phụ và tham khảo
    page7 = next(p for p in doc.pages if p.number == 7)
    assert "Marker P7" in page7.text
    assert "We thank everyone" not in page7.text
    assert "J X. 2001" not in page7.text


def test_numbered_steps_are_not_mistaken_for_references():
    steps = "\n".join(f"{i}. Engage stakeholders to adapt the guideline step {i}" for i in range(1, 11))
    pages = [RawPage(n, body(n)) for n in range(1, 7)] + [RawPage(7, steps + "\n" + body(7, 5))]
    doc = clean_document(pages)
    assert 7 in [p.number for p in doc.pages]


def test_dehyphenation_keeps_real_compounds():
    vocab = build_vocabulary(["vigorous-intensity activity is good", "therefore"])
    assert join_hyphenated("There-", "fore we eat", vocab) == "Therefore we eat"
    assert join_hyphenated("vigorous-", "intensity aerobic", vocab) == "vigorous-intensity aerobic"
    assert join_hyphenated("com-", "prehensiveness", vocab) == "comprehensiveness"


# ── Chia đoạn ────────────────────────────────────────────────────────────────
def test_chunks_keep_correct_page_numbers_and_size():
    doc = clean_document(sample_pages())
    chunks = chunk_document(doc)
    assert chunks
    for chunk in chunks:
        pages_in_text = {int(m) for m in re.findall(r"Marker P(\d+)", chunk.text)}
        assert chunk.page in pages_in_text
        assert max(pages_in_text) == chunk.page_end
        # Phần chồng lấp có thể lấy từ trang trước liền kề trong số trang được giữ
        assert min(pages_in_text) >= min(p for p in [2, 3, 5, 7] if p >= chunk.page - 2)
        assert estimate_tokens(chunk.text) <= MAX_TOKENS + 10
        assert "et al." not in chunk.text  # không có nội dung danh mục tham khảo


def test_chunks_overlap_between_consecutive_size_based_chunks():
    pages = [RawPage(n, body(n, 60)) for n in range(1, 4)]
    chunks = chunk_document(clean_document(pages))
    assert len(chunks) >= 2
    first_tail = chunks[0].text.split("\n")[-1][-60:]
    assert first_tail in chunks[1].text


def test_records_carry_source_metadata_and_stable_ids():
    doc = clean_document(sample_pages())
    records = build_records(SOURCE, chunk_document(doc))
    again = build_records(SOURCE, chunk_document(clean_document(sample_pages())))

    assert [r.id for r in records] == [r.id for r in again]
    assert len({r.id for r in records}) == len(records)
    meta = records[0].metadata
    assert meta["file"] == "sample.pdf"
    assert meta["title"] == "Sample position stand"
    assert meta["authors_org"] == "ISSN"
    assert meta["year"] == 2017
    assert meta["language"] == "en"
    assert meta["topic"] == "protein, giảm cân"
    assert meta["page"] == 2 and isinstance(meta["page"], int)   # trang đầu tiên được giữ
    assert meta["is_table"] is False
    assert records[0].id == chunk_id("sample.pdf", meta["page"], "text", meta["chunk_index"])


# ── Bảng ─────────────────────────────────────────────────────────────────────
TABLE_LAYOUT = """Some body text above the table
Table 9 Example nutrients
Food                     Protein (g)          Energy (kcal)
Egg                             6                    70
Chicken breast                 31                   165

Body text continues below"""

TABLE_PLAIN = """Some body text above the table
Table 9 Example nutrients
Food Protein (g) Energy (kcal)
Egg 6 70
Chicken breast 31 165"""


def test_table_is_rebuilt_row_by_column_and_flagged():
    table = parse_layout_table(TABLE_LAYOUT, 9, 4, set())
    assert table is not None and table.parsed
    assert table.header == ["Food", "Protein (g)", "Energy (kcal)"]
    assert table.rows == [["Egg", "6", "70"], ["Chicken breast", "31", "165"]]
    assert "Food: Chicken breast; Protein (g): 31; Energy (kcal): 165" in table.render()


def test_table_page_produces_table_chunk_and_strips_table_from_text():
    pages = [RawPage(n, body(n)) for n in range(1, 4)]
    pages.append(RawPage(4, body(4, 10) + "\n" + TABLE_PLAIN, layout=TABLE_LAYOUT))
    doc = clean_document(pages)
    page4 = next(p for p in doc.pages if p.number == 4)
    assert "Chicken breast 31 165" not in page4.text

    records = build_records(SOURCE, chunk_document(doc))
    table_records = [r for r in records if r.metadata["is_table"]]
    assert len(table_records) == 1
    assert table_records[0].metadata["page"] == 4
    assert "Energy (kcal): 165" in table_records[0].text
