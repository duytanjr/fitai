# Dữ liệu chương trình tập luyện (lát 9a)

Hai file CSV được nạp bằng `backend/scripts/seed_training.py`. Hiện chỉ có dữ liệu **mẫu** ("(VÍ DỤ) ..."),
không có link YouTube nào, nên mọi chương trình đều ở trạng thái draft và người dùng chưa thấy chương trình nào.
Nhóm đồ án tự điền dữ liệu thật; không dùng link đoán hay link tạo tự động.

```bash
docker compose exec backend python scripts/seed_training.py --dry-run   # đọc + kiểm tra, không ghi DB
docker compose exec backend python scripts/seed_training.py             # ghi DB (chạy lại không nhân đôi)
```

## Định dạng chung
- Mã hoá UTF-8 (có hoặc không có BOM, nên "CSV UTF-8" của Excel dùng được).
- Dấu phân cách tự nhận từ dòng tiêu đề: `,`, `;` hoặc tab (script báo đã dùng cái nào; dòng tiêu đề có
  nhiều loại cùng lúc thì báo lỗi). Ô có dấu phân cách bên trong thì đặt trong ngoặc kép.
- Khoảng trắng đầu/cuối mỗi ô bị cắt. Cột true/false nhận `true`, `false`, `1`, `0` (không phân biệt hoa thường).
- Thông báo lỗi nêu số dòng trong file (dòng tiêu đề là dòng 1).

## programs.csv
Cột bắt buộc (phải có trong dòng tiêu đề): `slug, title, description, goal_tag, level, duration_days, publish`.
Cột tuỳ chọn: `intensity_label`.

| Cột | Ghi chú |
|---|---|
| slug | chữ thường không dấu, số, `-` (vd. `nguoi-moi-14`); dùng trong đường dẫn |
| title | ≤ 200 ký tự |
| description | ô có thể trống; ≤ 2000 ký tự; không hứa kết quả giảm cân |
| goal_tag | `weight_loss`, `general`, `muscle_gain`, `endurance` |
| level | `beginner`, `intermediate` |
| duration_days | số nguyên 1–365 |
| publish | `true`/`false`; ô trống = `false` |
| intensity_label | tuỳ chọn, chữ ngắn ≤ 60 ký tự (vd. "Nhẹ") |

## schedule.csv (một file phẳng, mỗi dòng một mục)
Cột bắt buộc: `program_slug, day_number, is_rest, position, label, required, url`.
Cột tuỳ chọn (có thể vắng cả cột hoặc để trống): `title, channel, duration_min, category, intensity, impact,
equipment, level, notes, checked_on`.

Ví dụ tối giản:

```csv
program_slug,day_number,is_rest,position,label,required,url
nguoi-moi-14,1,false,1,Khởi động,true,https://www.youtube.com/watch?v=<id>
nguoi-moi-14,2,true,,,,
```

- **Ngày nghỉ:** chỉ điền `program_slug`, `day_number`, `is_rest=true` (có thể thêm `notes`, dùng làm ghi chú
  của ngày). Điền cột khác → lỗi.
- **Ngày tập:** mỗi mục một dòng; `position` ≥ 1, không lặp trong ngày; `required` trống = `true`; mỗi ngày
  tập phải có ít nhất một mục `required=true`. Cần `label` hoặc `title` (ít nhất một ô).
- `url`: chỉ `https://` trên `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`, dạng `watch?v=`,
  `youtu.be/<id>` hoặc `shorts/<id>`. Được lưu ở dạng `https://www.youtube.com/watch?v=<id>`. Để trống thì
  video luôn là draft.
- Khi để trống:
  - `title` → bằng `label`.
  - `channel` → giao diện không hiện dòng "Video: … · kênh".
  - `duration_min` → mục không có thời lượng; tổng phút chỉ cộng các mục có thời lượng và là null (không
    phải 0) nếu không mục nào có; ngày khi đó chỉ hiện số bài.
  - `category`, `intensity`, `impact`, `equipment`, `level`, `notes`, `checked_on` → để trống (NULL).
- Ô **được điền** vẫn phải hợp lệ: `duration_min` số nguyên 1–180; `category`: `warmup`, `cardio`, `strength`,
  `core`, `cooldown`; `intensity`: `low`, `moderate`, `high`; `impact`: `none`, `low`, `high`; `level`:
  `beginner`, `intermediate`; `checked_on`: `YYYY-MM-DD` hoặc `DD/MM/YYYY`.
- Cùng một video (cùng youtube_id, hoặc cùng title khi chưa có url) ở nhiều dòng: chỉ lỗi khi một cột được
  điền ở cả hai dòng mà giá trị khác nhau (ô trống không tính là khác; title mặc định từ label cũng không tính).
  Các ô được điền ở những dòng khác nhau được gộp lại.

## Quy tắc trạng thái
- Video **published** khi có url hợp lệ và title cũng như label của mọi mục trỏ tới nó không bắt đầu bằng
  "(VÍ DỤ)". Thiếu `duration_min`, `channel`, `checked_on` chỉ cảnh báo, không chặn.
- Chương trình **published** khi `publish=true`, đủ ngày 1…`duration_days`, mọi mục trỏ tới video published
  (tức là có url hợp lệ), có ít nhất một mục, và title/description không bắt đầu bằng "(VÍ DỤ)". Ngược lại là
  draft; script in lý do.
- Thiếu ngày: chương trình `publish=false` → chỉ cảnh báo (vẫn ghi, giữ draft); `publish=true` → lỗi.
- Có bất kỳ lỗi nào → không ghi gì vào DB. Đổi `publish` về `false` rồi nạp lại → chương trình về draft.
- Script không xoá video hay chương trình; ngày/mục không còn trong CSV thì bị xoá khỏi chương trình đó.

## Bộ dữ liệu thử ngoài git
Để thử giao diện với link thật mà không commit, đặt hai file cùng tên vào `data/training_dev/` (đã có trong
`.gitignore`), rồi:

```bash
mkdir -p data/training_dev            # trên máy, ở thư mục gốc repo
# tạo data/training_dev/programs.csv và schedule.csv theo định dạng trên
docker compose exec backend python scripts/seed_training.py --dir /app/data/training_dev --dry-run
docker compose exec backend python scripts/seed_training.py --dir /app/data/training_dev
```

Lưu ý: dữ liệu nạp từ `training_dev` vẫn nằm trong DB dev; nạp lại `data/training` không xoá các chương trình
có slug khác (script chỉ liệt kê chúng).
