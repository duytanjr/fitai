# Thư mục Tri thức (Knowledge Base) cho RAG — FitAI

Thư mục này lưu trữ tài liệu tham khảo khoa học và hướng dẫn chuyên môn về dinh dưỡng, thể dục phục vụ quy trình tìm kiếm thông tin tăng cường (RAG) của FitAI.

---

## 1. Cấu trúc thư mục

```text
data/knowledge/
├── README.md        # Hướng dẫn cấu trúc và quy trình thêm tài liệu
├── sources.csv      # Bảng siêu dữ liệu (metadata) quản lý các nguồn tài liệu
└── raw/             # Thư mục chứa các file tài liệu gốc (PDF, ...)
```

* **`raw/`**: Chứa các file tài liệu gốc (ví dụ `.pdf`). Thư mục này được cấu hình trong `.gitignore` (`data/knowledge/raw/*.pdf`) nhằm tránh đưa các file nhị phân nặng lên Git.
* **`sources.csv`**: File danh mục quản trị UTF-8 lưu trữ nguồn gốc, tác giả, năm xuất bản, ngôn ngữ, giấy phép và các ghi chú đối tượng của từng tài liệu.

---

## 2. Cách thêm tài liệu mới

Khi muốn bổ sung một tài liệu tri thức vào hệ thống, thực hiện 2 bước:

1. **Thêm file gốc:** Đặt file tài liệu (ví dụ: `my_document.pdf`) vào thư mục `data/knowledge/raw/`.
2. **Khai báo metadata:** Mở file `data/knowledge/sources.csv` và thêm 1 dòng mới với đúng định dạng các cột:
   * `file`: Tên file chính xác trong thư mục `raw/` (ví dụ: `my_document.pdf`).
   * `title`: Tiêu đề đầy đủ của tài liệu/nghiên cứu.
   * `authors_org`: Tác giả hoặc tổ chức phát hành (ví dụ: `WHO`, `ISSN`, ...).
   * `year`: Năm xuất bản.
   * `language`: Ngôn ngữ (`en`, `vi`, ...).
   * `topic`: Chủ đề tài liệu (dùng dấu ngoặc kép nếu có dấu phẩy).
   * `source_url`: Đường dẫn nguồn hoặc DOI (nếu có, nếu không để trống).
   * `license_note`: Giấy phép sử dụng hoặc ghi chú bản quyền (nếu chưa rõ để trống).
   * `notes`: Ghi chú đối tượng áp dụng hoặc phạm vi khuyến nghị.
3. **Nạp vào ChromaDB:** chạy script nạp (xem mục 3).

---

## 3. Nạp tài liệu vào ChromaDB

Thư mục `data/` được mount chỉ đọc vào container backend tại `/app/data`.

```bash
# Nạp / cập nhật (chạy lại nhiều lần không nhân đôi; đoạn không đổi sẽ không embedding lại)
docker exec fitai_backend python scripts/ingest_knowledge.py

# Xem trước kết quả làm sạch và chia đoạn, không gọi API, không ghi DB
docker exec fitai_backend python scripts/ingest_knowledge.py --dry-run

# Xoá collection và nạp lại từ đầu
docker exec fitai_backend python scripts/ingest_knowledge.py --reset

# Thử truy xuất (không gọi LLM): in top-k kèm điểm tương đồng cosine
docker exec fitai_backend python scripts/rag_smoke.py "Nên ăn bao nhiêu protein khi giảm cân?"
```

**Thử truy xuất với câu hỏi tuỳ ý** (`rag_smoke.py`, không gọi LLM): truyền một hoặc nhiều
câu hỏi trong dấu ngoặc kép; `-k` chọn số đoạn trả về, `--snippet` độ dài trích đoạn.
Dấu `✓` đánh dấu đoạn qua ngưỡng `RAG_SIMILARITY_THRESHOLD` hiện tại.

```bash
docker exec fitai_backend python scripts/rag_smoke.py "câu hỏi của bạn"
docker exec fitai_backend python scripts/rag_smoke.py -k 3 --snippet 200 "câu hỏi 1" "câu hỏi 2"
```

> ⚠️ **Đổi model embedding (`EMBEDDING_MODEL`) thì BẮT BUỘC chạy ingest với `--reset`.**
> Vector của các model khác nhau không so sánh được với nhau; script sẽ từ chối nạp
> vào collection được tạo bằng model khác.

Ghi chú:
* Số trang lưu trong metadata là **số trang PDF (đếm từ 1)**, không phải số in trên giấy.
* Bảng (Table N) được dựng lại thành từng hàng dạng `tên cột: giá trị` và gắn cờ `is_table`;
  bảng không dựng lại được hàng/cột sẽ không được nạp (script in rõ bảng nào).
* Điểm truy xuất = độ tương đồng cosine (1 − khoảng cách); ngưỡng lọc cấu hình bằng
  `RAG_SIMILARITY_THRESHOLD`.
