# Món ăn do quản trị viên nhập (nguồn `ADMIN_MANUAL`)

Thư mục này chứa file CSV để nạp nhiều món cùng lúc vào nguồn **Quản trị viên nhập** (id 3) bằng
`scripts/import_admin_foods.py`. Script dùng đúng quy tắc của trang `/admin/foods`: kiểm biên từng cột, tổng chất
≤ 100,5 g, cờ lệch Atwater, ghi chú nguồn bắt buộc, mã `ADM-xxxxx`, chống trùng tên, và ghi audit log.

Thư mục được commit nên chỉ đưa vào số liệu có nguồn công khai (nhãn sản phẩm, tài liệu đã xuất bản…).

## File

* `dishes_template.csv`: mẫu gồm dòng tiêu đề và 1 dòng `(VÍ DỤ)`. Sao chép thành `dishes.csv` rồi điền.
* `dishes.csv`: file mặc định script đọc (`/app/data/foods/manual/dishes.csv` trong container).

## Cột

Mọi số liệu tính **trên 100 g phần ăn được**.

| Cột | Bắt buộc | Ý nghĩa |
|---|---|---|
| `name_vi` | có | Tên món (≤ 255 ký tự). Trùng tên không phân biệt dấu/hoa thường với món đã có thì bị bỏ qua. |
| `energy_kcal` | có | Năng lượng, 0–900 kcal |
| `protein_g` | có | Protein (đạm), 0–100 g |
| `fat_g` | có | Lipid (béo), 0–100 g |
| `carb_g` | có | Glucid **không gồm xơ**, 0–100 g. Nhãn ghi carbohydrate tổng (gồm xơ) thì trừ xơ trước. |
| `source_note` | có | Ghi chú nguồn bằng chữ (≤ 1000 ký tự), vd. "Nhãn hộp 180 ml, chụp ngày 01/11/2026". |
| `fiber_g` | không | Xơ, 0–100 g |
| `water_g` | không | Nước, 0–100 g |
| `refuse_pct` | không | Tỷ lệ thải bỏ, 0–100 % |
| `group_name` | không | Nhóm thực phẩm; trống thì là "Chưa phân nhóm" |
| `preparation` | không | `raw`, `cooked`, `processed`, `dried` hoặc `unknown` (trống thì là `unknown`) |
| `name_original` | không | Tên gốc / tên tiếng Anh (≤ 500 ký tự) |

* Cột tùy chọn có thể vắng hẳn hoặc để trống. Ô trống nghĩa là "không có số liệu", **không phải 0**.
* Dấu phân cách tự nhận: `,`, `;` hoặc tab. Lưu file dạng UTF-8; có BOM (Excel "CSV UTF-8") cũng được.
* Số thập phân ghi `1,5` hay `1.5` đều được. Khi dấu phân cách là `,` thì ô `1,5` phải đặt trong ngoặc kép
  (Excel tự làm). Không dùng dấu phân cách hàng nghìn.
* Tổng nước + protein + lipid + glucid + xơ (các chất có nhập) không được vượt 100,5 g.
* Năng lượng lệch 4·protein + 9·lipid + 4·glucid quá 15% thì **vẫn nạp** nhưng gắn cờ và được liệt kê trong
  báo cáo để kiểm lại.
* Dòng có `name_vi` bắt đầu bằng `(VÍ DỤ)` luôn bị bỏ qua.

## Quy đổi số liệu trên nhãn sang 100 g

Nhân mỗi giá trị trên nhãn với **100 / khối lượng khẩu phần (g)**.

Ví dụ: hộp sữa 180 ml ghi 120 kcal, đạm 5,5 g, béo 6 g, carb 11 g. Coi 180 ml ≈ 180 g (sữa nặng hơn nước một
chút, sai số nhỏ). Hệ số là 100 / 180 ≈ 0,556:

| | Trên nhãn (180 ml) | Trên 100 g |
|---|---|---|
| Năng lượng | 120 kcal | 120 × 100 / 180 = **66,7 kcal** |
| Đạm | 5,5 g | 5,5 × 100 / 180 = **3,06 g** |
| Béo | 6 g | 6 × 100 / 180 = **3,33 g** |
| Carb | 11 g | 11 × 100 / 180 = **6,11 g** |

Nhãn đã ghi sẵn cột "trên 100 g" / "trên 100 ml" thì dùng thẳng cột đó. Ghi rõ cách quy đổi trong `source_note`.

## Cách chạy

```bash
# Kiểm tra, không ghi DB (vẫn cần tài khoản admin)
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin> --dry-run

# Nạp thật
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin>

# Cập nhật cả món đã có cùng tên (audit ghi before/after như sửa trên trang quản trị)
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin> --update-existing

# File khác
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin> --file /app/data/foods/manual/khac.csv
```

* Chỉ cần một dòng lỗi là không ghi dòng nào (mã thoát 1). Báo cáo liệt kê mọi lỗi kèm số dòng CSV.
* Với `--update-existing`: cột có trong file thì ghi đè, kể cả ô trống (xóa giá trị đó). Cột vắng mặt thì giữ
  nguyên. Món không đổi gì thì không ghi audit.
* Tài khoản admin cấp bằng `scripts/make_admin.py <email>`.
