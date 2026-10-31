# Bảng thực phẩm (`foods`) — FitAI

Dữ liệu tra cứu dinh dưỡng của thực phẩm cho công cụ `lookup_food` của agent (FR8).

## 1. Nguồn

* **Bảng thành phần thực phẩm Việt Nam** (Vietnamese Food Composition Table), 2007.
* Tác giả/tổ chức: **Viện Dinh dưỡng** — Bộ Y tế. Nhà xuất bản: **NXB Y học**.
* File gốc: `data/knowledge/raw/vn_food_composition_2007_vi.pdf` (567 trang, không đưa lên Git).
* Bản quyền/giấy phép: (tôi sẽ điền)

## 2. Phạm vi đã nạp

* Mỗi trang thực phẩm của PDF là một dòng của bảng `foods`.
* **Cột đã nạp:** STT, mã số, tên tiếng Việt (chuyển từ mã TCVN3 sang Unicode, viết hoa chữ
  đầu), tên tiếng Anh, nhóm thực phẩm, tỷ lệ thải bỏ (%), nước, năng lượng (kcal), protein,
  lipid, glucid, xơ (celluloza), tro, số trang PDF.
* **Cơ sở tính:** mọi giá trị dinh dưỡng tính **trên 100 g phần ăn được**.
* **`NULL` = "không có số liệu"** (bảng gốc ghi "-"), KHÔNG phải 0.
* **Đã loại:** nhóm 14 (nước giải khát, bia, rượu). Bảng gốc không tính năng lượng từ
  cồn (rượu ghi 0 kcal) nên dễ gây hiểu sai.
* **Chưa nạp:** khoáng chất, vitamin, acid amin, acid béo (xem mục 4).
* Mỗi dòng có `quality_flags` ghi các kiểm tra không qua khi nạp (Atwater 4/9/4 lệch quá
  ±2 kcal, tổng khối lượng ngoài 90–110 g, hoặc thiếu số liệu để kiểm tra). Số liệu không
  bao giờ bị tự sửa.

## 3. Cách chạy

```bash
# Áp dụng migration (tạo bảng foods, bật extension pg_trgm)
docker exec fitai_backend alembic upgrade head

# Chỉ tách và kiểm tra chất lượng, không ghi DB
docker exec fitai_backend python scripts/ingest_foods.py --dry-run

# Nạp / cập nhật (chạy lại nhiều lần không nhân đôi: upsert theo mã số)
docker exec fitai_backend python scripts/ingest_foods.py

# Xoá các dòng của bảng foods rồi nạp lại (CHỈ bảng foods, không động tới bảng khác)
docker exec fitai_backend python scripts/ingest_foods.py --reset
```

`data/` được mount chỉ đọc vào container, nên file mẫu đối chiếu được ghi vào `/tmp` trong
container rồi chép ra ngoài:

```bash
docker exec fitai_backend python scripts/ingest_foods.py --dry-run --sample-out /tmp/foods_ingested_sample.md
docker cp fitai_backend:/tmp/foods_ingested_sample.md data/knowledge/_review/foods_ingested_sample.md
```

### Trạng thái sống/chín (`preparation`)

Cột `foods.preparation` (`raw`, `cooked`, `processed`, `dried`, `unknown`) CHỈ được gán khi tên
tiếng Việt hoặc tiếng Anh ghi rõ (quy tắc trong `backend/services/foods/preparation.py`); còn lại
là `unknown` = nguồn không ghi rõ — không suy đoán từ tỷ lệ nước hay thải bỏ.
`preparation_source`: `auto` = script gán, `manual` = chỉnh tay (script và lần nạp sau không ghi đè).

```bash
# Điền từ tên đã có trong DB (không nạp lại PDF, chỉ UPDATE cột preparation); xem trước rồi mới ghi
docker exec fitai_backend python scripts/backfill_food_preparation.py --dry-run
docker exec fitai_backend python scripts/backfill_food_preparation.py
```

### Từ đồng nghĩa và từ mơ hồ

`backend/services/foods/aliases.py` (tách khỏi dữ liệu nguồn, có test): từ đồng nghĩa/biến thể
chính tả chỉ mở rộng truy vấn (kết quả vẫn hiện tên gốc trong nguồn); từ mơ hồ (vd. "bơ") trả
danh sách nghĩa để người dùng chọn, không trả số liệu. Thêm cặp/từ mới cần được duyệt.

Món đã nấu mà bảng chỉ có nguyên liệu sống (`COOKED_DISHES`: cơm, cháo → gạo tẻ; xôi → gạo nếp)
trả số liệu nguyên liệu SỐNG kèm cảnh báo, không quy đổi sang món đã nấu.

### Quy ước glucid (không gồm xơ)

Kiểm tra trên dữ liệu đã nạp (2026-10-31): với 418/509 dòng đủ số liệu, tổng nước + protein +
lipid + glucid + celluloza + tro nằm trong 99–101 g ở **cả 418 dòng** (trung vị 100,0 g). Với 88
dòng có xơ ≥ 2 g, chỉ 8 dòng cộng đủ ~100 g nếu bỏ celluloza. Kết luận: **cột glucid KHÔNG gồm
celluloza** (glucid có thể được tính theo hiệu số — chưa xác minh trong PDF). Vì vậy nhãn hiển thị
là "glucid (không gồm xơ)", và carb trong tổng ngày (`/meals/summary`) là glucid của nguồn,
không gồm xơ.

**Súp lơ xanh** (mã 4100, tr. PDF 202): tên EN là "Cauliflower, green"; nguồn không nói rõ đây có
phải bông cải xanh (broccoli) hay không. Tra "bông cải xanh" chỉ cho biết "bảng ghi là Súp lơ xanh
(Cauliflower, green)", không khẳng định hai thứ là một.

## 4. Hạn chế đã biết

* **Không có món ăn hoàn chỉnh** (phở bò, cơm đã nấu, cháo, canh, món xào...): chỉ có
  nguyên liệu và một số sản phẩm chế biến sẵn (bánh phở, bún, giò, chả, đồ hộp...).
* **Xơ là celluloza** (theo nhãn của bảng gốc), có thể khác "chất xơ tổng" (dietary fiber)
  của các bảng khác.
* **Dữ liệu tính theo phần ăn được:** thực phẩm có tỷ lệ thải bỏ cao (vd. ngô bắp tươi 45%)
  phải trừ phần bỏ đi trước khi tính theo khối lượng mua về.
* **Chưa tách khoáng chất và vitamin:** với giá trị là số nguyên, PDF dính giá trị với mã
  nguồn tài liệu (vd. "Natri mg 31" có thể là 3 mg nguồn 1 hoặc 31 mg).
* STT 450 không có trang nào trong PDF (sách nhảy số hay PDF thiếu trang: chưa xác định).
* Tên chữ hoa có dấu ở đầu (vd. "Ốc bươu") nằm ở font TCVN3 chữ hoa riêng; code viết hoa
  lại chữ đầu sau khi chuyển mã.
