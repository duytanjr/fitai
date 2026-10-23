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
