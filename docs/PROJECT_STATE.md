# Trạng thái dự án FitAI (ghi chú bàn giao giữa các phiên)

Chỉ ghi những gì KHÔNG có trong SPEC.md / AGENTS.md. Cập nhật lần cuối: 2026-11-08.

## 1. Các lát đã xong (git log)
| Lát | Commit | Nội dung chính |
|---|---|---|
| FR1–2 | 58d2b7e | đăng ký, hồ sơ, onboarding |
| FR3 | fb17c37 | BMI, BMR, TDEE, calo mục tiêu, macro |
| FR4, FR6 | eaeb0cb | chatbot thật, lịch sử, cá nhân hoá |
| FR5 (RAG) | cdcbb30, f652b6e | Chroma, nạp tài liệu, agent dùng công cụ, trích dẫn nguồn |
| FR8 (5a) | 2448f98 | bảng foods (VN 2007), lookup_food |
| FR9 (5b) | 458c4aa | nhật ký bữa ăn, tổng hợp ngày, get_daily_summary |
| 5d-1 | 7bdeb15 | từ đồng nghĩa/mơ hồ, preparation sống/chín, quy ước glucid, gạo sống (manual) |
| Đánh giá v1 | eade8b0 | eval_questions.csv v1 + bộ chạy đánh giá |
| 5d-2 | 7516fb2 | food_sources, 20 mục USDA SR Legacy, trích dẫn theo từng dòng |
| 7 (FR15–17) | cdb6293 | body_metrics, /body-metrics, /progress, báo cáo tuần, get_progress_summary, dashboard tiến độ |
| 8a (FR19 thực phẩm + phân quyền) | a719799 | users.role, admin_audit_log, nguồn ADMIN_MANUAL, /admin/foods, make_admin, trang /admin |
| 8b-1 (FR18 tài liệu RAG) | 8e1bbfa | knowledge_documents, /admin/documents, lập chỉ mục hai pha, bộ lọc doc_enabled, pdf_guard, tab Tài liệu |
| 8b-2 (FR20 hội thoại ẩn danh) | b6e8256 | /admin/conversations (tắt mặc định), bí danh HMAC, che nội dung, nhật ký xem, người dùng tự xoá phiên |
| 9a (một phần FR12–13) | b71a0f2 | workout_videos, training_programs, program_days, program_day_items, seed_training.py, /training |
| 9b (một phần FR14) | b9f206e | program_enrollments, program_day_completions, /training/enrollments, /training/summary, thẻ Tập luyện tuần này |
| 9d (FR12) | fa90001 | recommend.py, /training/recommendation, công cụ recommend_program và get_training_summary, quy tắc TẬP LUYỆN |
| Dữ liệu tập luyện + ảnh xem trước | 5af1b21, 7f4def5, 76b89a7 | nội dung nguoi-moi-14 và toan-than-28 trong data/training/, ảnh xem trước YouTube trên trang ngày tập |
| Nạp món ăn thủ công (FR19) | 2fab762, d5da112 | scripts/import_admin_foods.py, services/foods/admin_import.py, data/foods/manual/ |
| 70 món ADMIN_MANUAL (chế biến, đồ uống, thực phẩm cơ bản) | 6d25841 | dishes.csv (đợt 1, 8 món) + dishes_all.csv (62 món mới, cập nhật 6 món đợt 1), nạp vào DB dev |

- FR12–FR14 coi là XONG sau 9a/9b/9d; FR13 và FR14 được đơn giản hoá có chủ đích (mỗi mục là một video YouTube kèm
  label, không có nhóm cơ / lưu ý riêng từng bài / ghi từng hiệp; nhật ký tập là đánh dấu hoàn thành ngày).

- pytest hiện tại: 956 passed, 0 skipped (sau quy tắc kỹ thuật động tác: +1 test nội dung quy tắc; sau 955
  là sau script nạp món ăn thủ công: +28 test import, test dữ liệu tập luyện
  trong repo 1 → 4; sau 9d là 924, sau 9b là 862, sau 9a là 822, sau 8b-2 là 689, sau 8b-1 là
  628, sau 8a là 580, sau lát 7 là 487). Lát 9d không có migration mới.
- md5 trước/sau migration d2a6f9c3e8b1 (trùng nhau): foods, meal_logs, body_metrics, chat_sessions như dòng 9a bên
  dưới; users 80 dòng `45add6f9c99a77675bdb856963d98f93`; workout_videos 2 dòng `a8f9331b5237cf67edb66f7dad117fb5`;
  training_programs 1 dòng `8d94dc027929a48eec087fc37364fd21`. Sau thử đầu-cuối 9b chỉ users đổi (81 dòng
  `a3aa166522bb9ba09ed8f9af75f2cfc7`, thêm tài khoản thử). Bản pg_dump trước migration ở scratchpad, ngoài git.
- md5 trước/sau migration c4b8e2f7a915 và sau thử đầu-cuối 9a (trùng nhau): foods 529 dòng
  `88900310ebf5772e3286d73e84e48edc`, meal_logs 23 dòng `5e937f6981948a0875c85edb6653f239`, body_metrics 7 dòng
  `fdbf4752cc5d4016195a6d5d28a0040f`, users 80 dòng `45add6f9c99a77675bdb856963d98f93`, chat_sessions 38 dòng
  `d512c213ba82af1ae8c65e0dceed1811`. Bản pg_dump trước migration ở scratchpad của phiên, ngoài git.
- md5 trước/sau migration a9d4e6f1c2b3 (trùng nhau): foods 529 dòng, tính trên mọi cột kể cả source_note,
  `88900310ebf5772e3286d73e84e48edc`; meal_logs 23 dòng `5e937f6981948a0875c85edb6653f239`; food_sources 3 dòng
  `e0ec8aea8d9ae7de0f765b2857db16df`; body_metrics 7 dòng `fdbf4752cc5d4016195a6d5d28a0040f`; users 75 dòng
  `bd77f2ba9ba81f7b9d41738e7b5196ab` (sau thử đầu-cuối 76 dòng do thêm tài khoản admin thử). Câu SQL md5 và bản
  pg_dump trước migration nằm ở scratchpad của phiên, ngoài git.
- rag_smoke 10 câu A: giống hệt trước/sau lát 8b-1 (10 câu, 40 đoạn qua ngưỡng). So bằng vector câu hỏi nhúng MỘT
  lần rồi lưu lại (để không tốn hạn mức), chạy đúng scripts/rag_smoke.py; kết quả đã khớp với lần chạy thật.
- Đổi nhãn "xơ thực phẩm tổng số" đã nằm trong 7516fb2 (chưa chắc: suy từ git status sạch).
- Dòng `food_sources.id=2` trong DB dev VẪN còn chữ cũ "xơ ăn kiêng tổng số" ở fiber_type (đã thấy khi kiểm
  tra lát 8a; migration chạy trước khi đổi tên); chỉ là cột mô tả, chưa hiển thị ở đâu.

## 2. Kiến trúc đang chạy
Công cụ của agent (fitness_advisor.py, tối đa 3 vòng, 3 lệnh gọi/vòng, timeout 30 s):
- `search_knowledge(query)`: RAG trên Chroma, ngưỡng cosine 0,65, top-k 5.
- `calc_body_metrics()`: không nhận tham số; đọc hồ sơ của user lấy từ JWT.
- `lookup_food(query, grams?)`: tra bảng foods; code tính theo grams; mỗi dòng trích nguồn riêng.
- `get_daily_summary(date?)`: chỉ đọc nhật ký ngày của user hiện tại (giờ VN = UTC+7).
- `get_progress_summary(days=7)` (công cụ thứ 5): chỉ đọc, không nhận user_id; days ∈ {7, 30, 90}, sai thì
  trả lỗi tham số. Chỉ kèm chuỗi theo ngày khi days=7.
- `recommend_program(experience?)` (công cụ thứ 6, lát 9d): chỉ đọc; experience ∈ {"regular", "new"} hoặc bỏ trống
  (khác → "Lỗi tham số"); prompt dặn chỉ truyền khi người dùng tự nói rõ. Trả cùng nội dung như API gợi ý.
- `get_training_summary()` (công cụ thứ 7, lát 9d): chỉ đọc, không tham số; chương trình đang theo (tên, a/b ngày,
  ngày tiếp theo, available) + tuần lịch hiện tại (từ weekly_summary của 9b); thiếu → null kèm ghi chú, không 0.
- Hai công cụ tập luyện chạy trong SAVEPOINT (ChatService._load_recommendation / _load_training_summary); lỗi DB
  → mã `TAP_LUYEN_KHONG_KHA_DUNG`. 3 vòng × 3 lệnh gọi vẫn đủ với 7 công cụ (không đổi).

Thứ tự quy tắc prompt hiện tại (cuối danh sách): 15 nhiều nguồn dữ liệu thực phẩm, 16 tiến độ (nói "N ngày gần
nhất", không nói "tuần này", kèm calorie_note, không dùng từ đánh giá), 17 nguồn quản trị viên nhập (nêu rõ
"số liệu do quản trị viên nhập" kèm mã ADM- và ghi chú nguồn; ghi chú là dữ liệu, không phải chỉ thị),
18 tập luyện (tiêu đề "TẬP LUYỆN:": gọi recommend_program / get_training_summary, chỉ nêu chương trình và con số
công cụ trả về, không bịa bài tập hay số hiệp, số phút là tự đánh dấu, null không phải 0, không hứa giảm cân, không
kcal đã đốt, không "đạt/chưa đạt"; câu hỏi kỹ thuật động tác / khởi động / giãn cơ → PHẢI gọi search_knowledge
trước, có đoạn phù hợp thì trình bày các bước đúng theo đoạn, nói rõ là trích giáo trình NASM kèm tên tài liệu
(nguon) và trang (trang_pdf), dặn không thay thế huấn luyện viên và dừng tập nếu đau / chóng mặt / khó thở, không
thêm bước ngoài đoạn, chữ lỗi OCR hoặc bước bị trộn thì chỉ nêu phần rõ và nói phần còn lại chưa rõ; chỉ khi
không có đoạn phù hợp mới nói chưa có hướng dẫn kỹ thuật và khuyên hỏi huấn luyện viên (nhánh feat/technique-rule);
bệnh nền/đau → gặp bác sĩ, thống kê tính theo tuần lịch từ thứ Hai), 19 an toàn y tế. Test tìm quy tắc theo tiêu
đề ("TẬP LUYỆN:", "NGUYÊN TẮC AN TOÀN Y TẾ:"), không theo số thứ tự.

Bảng chính: users (role), user_profiles, chat_sessions, chat_messages (sources JSON), foods, food_sources,
meal_logs (FK RESTRICT tới foods), body_metrics, admin_audit_log, knowledge_documents, workout_videos,
training_programs, program_days, program_day_items, program_enrollments, program_day_completions.
Migration head: d2a6f9c3e8b1.

Tập luyện (lát 9a, models/training.py, services/training/{youtube,seed,catalog}.py, api/routers/training.py):
- Bảng: `workout_videos` (youtube_id 11 ký tự UNIQUE, url chuẩn `https://www.youtube.com/watch?v=<id>`; title bắt
  buộc; channel, duration_min 1–180, category, intensity, impact, equipment, level, notes, checked_on đều NULL được;
  video chưa có link thì youtube_id/url NULL, chỉ được draft, duy nhất theo title); `training_programs` (slug
  UNIQUE, goal_tag, level, duration_days ≥ 1, KHÔNG có cột tuổi); `program_days` (CASCADE, day_number duy nhất trong
  chương trình, is_rest, note); `program_day_items` (CASCADE theo ngày, RESTRICT theo video, duy nhất (ngày,
  position), required mặc định true). id là số nguyên.
- Xác thực link (youtube.py, hàm thuần): chỉ https, host đúng một trong youtube.com / www / m / youtu.be (so
  nguyên chuỗi), không userinfo, không port; dạng watch?v=, youtu.be/<id>, shorts/<id>; từ chối mọi dạng khác.
- Trình nạp `scripts/seed_training.py [--dir DIR] [--dry-run]` (mặc định data/training, trong container
  /app/data/training): đọc programs.csv + schedule.csv, tự nhận dấu phân cách `,` `;` tab từ dòng tiêu đề (mơ hồ →
  lỗi), utf-8-sig, cắt khoảng trắng, true/false/1/0. Cột bắt buộc: programs.csv — slug, title, description,
  goal_tag, level, duration_days, publish (intensity_label tuỳ chọn); schedule.csv — program_slug, day_number,
  is_rest, position, label, required, url (mọi cột khác tuỳ chọn; title mặc định bằng label; ô được điền vẫn phải
  hợp lệ). Upsert theo khoá tự nhiên, chạy lại không đổi gì; ngày/mục không còn trong CSV bị xoá, video và chương
  trình không bao giờ bị xoá. Lỗi cấu trúc → không ghi gì (mã thoát 1). Cùng youtube_id ở nhiều dòng chỉ lỗi khi ô
  ĐƯỢC ĐIỀN khác nhau. Chi tiết cột: data/training/README.md.
- Trạng thái: video draft nếu thiếu url hoặc title/label bắt đầu "(VÍ DỤ)"; thiếu thời lượng/kênh/checked_on chỉ
  cảnh báo. Chương trình published khi publish=true, đủ ngày, mọi mục trỏ tới video published, có ít nhất một
  mục, title/description không bắt đầu "(VÍ DỤ)". Thiếu ngày: publish=false → cảnh báo (giữ draft), publish=true →
  lỗi. Đổi publish về false rồi nạp lại → về draft.
- API (JWT, chỉ đọc, không lọc tuổi): GET /training/programs, /training/programs/{slug},
  /training/programs/{slug}/days/{n}. Chương trình draft hoặc không tồn tại → 404; ngày ngoài khoảng → 404. Mục
  theo position; label trống thì dùng title video. total_minutes/required_minutes chỉ cộng mục có thời lượng, null
  (không phải 0) khi không mục nào có; kèm items_without_duration. Phòng thủ: mục trỏ tới video không published bị
  ẩn và không tính phút.
- Frontend: /training (thẻ chữ, không ảnh), /training/[slug], /training/[slug]/days/[n] (tham số đọc bằng
  useParams vì repo chưa có route động mẫu và không có node_modules/next/dist/docs). Nút "Bắt đầu" là
  `<a target="_blank" rel="noopener noreferrer">`, client chỉ mở url đúng dạng chuẩn. Hộp lưu ý an toàn cố định;
  goal weight_loss thêm dòng "không hứa kết quả giảm cân"; tuổi < 18 (đọc GET /profile, lỗi thì bỏ qua) thêm dòng
  nhắc tập cùng người lớn, hiện trên mọi trang tập. Liên kết "Tập luyện" ở dashboard, nhật ký ăn uống, chat.
- Ảnh xem trước (76b89a7, chỉ frontend, ProgramDayView + `youtubeThumbUrl` trong lib/training.ts): mỗi mục của
  trang ngày tập là một thẻ, ảnh bên trái, tiêu đề và nút "Bắt đầu" bên phải. Ảnh lấy từ
  `https://i.ytimg.com/vi/<youtube_id>/hqdefault.jpg`, chỉ dựng khi youtube_id khớp `^[A-Za-z0-9_-]{11}$` (không
  khớp → không hiện ảnh). Thẻ `<img>` thường (không next/image, không sửa next.config): loading="lazy",
  referrerPolicy="no-referrer", alt="" (ảnh trang trí), 16:9 object-cover, rộng w-24 (màn hẹp) / w-40 (từ sm), vẫn
  cạnh tiêu đề. Ảnh lỗi → ẩn, giữ khối xám cùng kích thước. Ảnh bọc trong `<a>` cùng đích với "Bắt đầu"
  (tabIndex -1, aria-hidden vì trùng nút); url không hợp lệ thì ảnh không bấm được. Chú thích cuối trang "Ảnh xem
  trước tải từ YouTube; bản quyền video thuộc kênh đăng tải." (chỉ khi có ít nhất một ảnh). Trang /training và
  trang chương trình vẫn chỉ có chữ.
- Dữ liệu (5af1b21, 7f4def5): data/training/ có nội dung thật của hai chương trình, cả hai publish=true:
  `nguoi-moi-14` (beginner, weight_loss, 14 ngày, 3 ngày nghỉ, 17 video khác nhau) và `toan-than-28`
  (intermediate, weight_loss, 28 ngày, 5 ngày nghỉ, 28 video khác nhau); tổng 43 video YouTube khác nhau vì 2 video
  dùng chung giữa hai chương trình (toan-than-28 ngày 5 mục 3 và ngày 13 mục 4). schedule.csv chỉ dùng đúng 7 cột
  bắt buộc + duration_min (để trống ở mọi dòng); không có kênh, thời lượng, checked_on. Cách nạp:
  `docker compose exec backend python scripts/seed_training.py --dry-run` rồi chạy lại không có `--dry-run`. DB
  dev (kiểm ngày 2026-11-07): nguoi-moi-14 và toan-than-28 published; `thu-nghiem` (từ data/training_dev/,
  gitignore) đã về draft; 45 video published (43 + 2 video của thu-nghiem).
- Test dữ liệu repo (tests/test_training_seed.py, chỉ chạy bước kiểm tra load_dir, không ghi DB): data/training/
  nạp không lỗi; mọi chương trình publish=true đều published, đủ ngày 1..duration_days, mọi mục trỏ tới video
  published có url YouTube hợp lệ (parse_youtube_url); dòng mẫu "(VÍ DỤ)" hoặc video không link không bao giờ
  published (kể cả bản sao dữ liệu repo đổi title một chương trình thành "(VÍ DỤ)" → draft dù publish=true).

Theo chương trình (lát 9b, models/training_progress.py, services/training/progress.py, api/routers/training.py):
- `program_enrollments`: id UUID, user_id (FK CASCADE), program_id (FK RESTRICT), started_on / ended_on (ngày giờ
  VN), status enum enrollment_status (active | completed | abandoned), created_at mặc định `clock_timestamp()` (không
  phải now(), để thứ tự đúng khi nhiều dòng tạo trong một transaction). Unique index một phần: MỘT enrollment active
  mỗi người; CHECK ended_on NULL đúng khi active.
- `program_day_completions`: id UUID, enrollment_id (FK CASCADE), day_number ≥ 1 (theo SỐ NGÀY, không FK tới
  program_days), completed_on (today_vn), minutes_done NULL hoặc 0–600; UNIQUE (enrollment_id, day_number).
- minutes_done được chụp lúc đánh dấu: tổng duration_min các mục BẮT BUỘC, chỉ khi MỌI mục bắt buộc của ngày đều có
  thời lượng; thiếu bất kỳ mục nào → null (không cộng thiếu một phần). Mục không bắt buộc không tính.
- API (JWT, user từ token, của người khác → 404):
  - POST /training/enrollments {program_slug} (extra=forbid): draft/không tồn tại → 404; đang có active → 409 kèm
    tên chương trình; `?replace=true` chuyển cái cũ sang abandoned (đặt ended_on, giữ lịch sử) rồi tạo mới — "Tập
    lại" cũng là lệnh này.
  - GET /training/enrollments/current → `{"enrollment": … | null}` kèm tiến độ (training_days_done /
    training_days_total chỉ đếm ngày hiện là ngày tập trong 1..duration_days, completed_days, next_day). Chương
    trình về draft → available=false + "Chương trình tạm thời không khả dụng"; ngày đã đánh dấu vượt duration_days
    hoặc đã thành ngày nghỉ → bỏ qua, schedule_changed=true.
  - POST /training/enrollments/{id}/days/{n}/complete: idempotent (đã có bản ghi → 200 không đổi, kể cả khi
    completed); ngày nghỉ / ngoài khoảng → 422; enrollment không active hoặc chương trình draft → 409. Không bắt
    theo thứ tự ngày. Xong mọi ngày tập → completed (đặt ended_on).
  - DELETE /training/enrollments/{id}/days/{n}: bỏ đánh dấu; abandoned → 409; ngày chưa đánh dấu → 404; enrollment
    completed quay lại active (đang có active khác → 409).
  - GET /training/summary?week_start= (mặc định tuần hiện tại, thứ Hai giờ VN; không phải thứ Hai hoặc tuần tương
    lai → 422): trên MỌI enrollment; completed_days (số ngày chương trình), active_dates (số ngày lịch),
    total_minutes (chỉ ngày có minutes_done), days_without_minutes, series 7 ngày; không có dữ liệu → null, không 0.
    Logic ở `build_week_summary` (thuần) + `weekly_summary` (DB) để lát 9d dùng lại làm công cụ chatbot.
  - GET /training/programs/{slug} thêm `my_enrollment` (enrollment gần nhất của người dùng với chương trình, ưu
    tiên active).
- Frontend: trang chương trình có "Bắt đầu chương trình" (đang theo chương trình khác → hộp xác nhận trong trang,
  không dùng window.confirm), banner "Đang theo…: đã xong a/b ngày", dấu tích ngày đã xong, "Tập lại chương trình";
  trang ngày có "Hoàn thành các bài tập" / "Đã hoàn thành" + "Bỏ đánh dấu" và ghi chú tự đánh dấu (chưa theo → mời
  bắt đầu); danh sách có nhãn "Đang theo"; dashboard có thẻ "Tập luyện tuần này" (đã tập N ngày, tổng phút bạn đánh
  dấu, "chưa tính N ngày chưa đủ thời lượng", "Chưa có dữ liệu thời lượng" khi mọi ngày thiếu; câu tham khảo WHO
  trung lập, không "đạt/chưa đạt", không kcal).
- Còn để ý: chương trình có trong DB nhưng không có trong CSV thì trình nạp chỉ liệt kê, không tính lại trạng thái.

Gợi ý chương trình (lát 9d, services/training/recommend.py):
- `recommend_program(profile, experience, programs)` thuần; `recommendation_for_user(db, user_id, experience)` đọc
  hồ sơ của chính user (không có hồ sơ → thiếu thông tin) và chương trình published; dùng chung cho API và công cụ.
- Thứ tự: CHỐT CHẶN BMI < 18,5 xét trước mọi luật (kể cả experience): mục tiêu giảm cân → chính null
  (`bmi_thap_muc_tieu_giam_can`); mục tiêu khác → loại chương trình weight_loss, không còn gì → null
  (`chi_co_chuong_trinh_giam_can`). Rồi: thiếu mức vận động và experience None → beginner (`thieu_thong_tin`);
  regular → intermediate; new → beginner; vận động ít/nhẹ hoặc BMI ≥ 30 hoặc tuổi ≥ 60 → beginner, thay thế
  intermediate (`nen_bat_dau_nhe`); vận động vừa trở lên → intermediate, thay thế beginner. Không lọc tuổi < 18.
- BMI từ metrics_service.calculate_bmi (làm tròn 1 chữ số); thiếu chiều cao/cân nặng → không áp chốt chặn, có ghi
  chú. Câu lý do "Nên bắt đầu ở mức … vì <dữ kiện đã khớp>"; không nêu con số BMI, không cam kết kết quả, không
  lời khuyên y tế. Chọn trong cùng level: ưu tiên goal_tag trùng mục tiêu (maintenance ↔ general), rồi ngắn hơn,
  rồi slug; không có level đó → level còn lại kèm ghi chú. Ghi chú "chưa có chương trình riêng cho mục tiêu này"
  chỉ khi không có chương trình published cùng mục tiêu.
- API GET /training/recommendation?experience=regular|new (khác → 422): primary / alternative (slug, title,
  duration_days, level, goal_tag), reason_code, reason, notes, experience. Không sửa hồ sơ.
- Frontend /training: hộp "Gợi ý cho bạn" (câu lý do, ghi chú, "Thay thế: …"), nhãn trên thẻ chương trình chính,
  câu hỏi "Bạn đã tập đều trong vài tháng qua chưa?" (2 nút; chỉ giữ trong trang); primary null → chỉ hiện câu lý do.

Tài liệu RAG (lát 8b-1, services/knowledge/documents.py, indexing.py, pdf_guard.py; api/routers/admin_documents.py):
- `knowledge_documents`: origin builtin | upload; status uploaded | indexing | indexed | failed; error_code là mã
  ngắn (CHECK `^[a-z0-9_]{1,40}$`); content_hash sha256 duy nhất (trùng → 409); unique index một phần
  `((true)) WHERE status='indexing'` nên chỉ một việc lập chỉ mục tại một thời điểm (vi phạm → 409).
  Hai tài liệu builtin (ISSN, WHO) đăng ký từ sources.csv bằng `sync_builtin_documents` (idempotent, giữ
  `enabled`), chạy lúc khởi động app và trong script backfill.
- Đoạn trong Chroma có `doc_id`, `doc_enabled`, `doc_origin`. rag_service lọc `{"doc_enabled": {"$ne": False}}`:
  đã thử thật với Chroma 1.5.9, `$ne False` giữ đoạn THIẾU trường, còn `$eq True` loại chúng. Chroma
  `collection.update` gộp metadata; giá trị None xoá khoá.
- Lập chỉ mục hai pha (chạy nền bằng BackgroundTasks): đoạn mới ghi với `doc_enabled=False, index_pending=True`
  (vô hình với tìm kiếm); nhúng xong toàn bộ mới kích hoạt, rồi xoá đoạn cũ không còn trong tập mới. id đoạn upload
  = sha1(doc:<doc_id>|trang|loại|chỉ số|content_hash) nên thử lại không nhúng lại đoạn đã có. Lỗi giữa chừng → đoạn
  cũ giữ nguyên, `enabled` không đổi. Vượt KNOWLEDGE_MAX_CHUNKS (400) → failed/tai_lieu_qua_dai, không nhúng.
  Lỗi hạn mức → failed/loi_han_muc (EmbeddingQuotaError; lập chỉ mục thử lại tối đa 3 lần). Khởi động: bản ghi
  kẹt ở indexing → failed/gian_doan.
- `pdf_guard` + `pdf_worker`: mọi lần mở PDF tải lên đều chạy trong tiến trình con với môi trường tối thiểu
  (PATH, PYTHONPATH, LANG, HOME — không có GOOGLE_API_KEY hay SECRET_KEY), RLIMIT_AS (KNOWLEDGE_PDF_MEMORY_MB) và
  thời gian chờ (KNOWLEDGE_PDF_TIMEOUT_S). Tải lên: chỉ .pdf có byte đầu `%PDF-`, tối đa KNOWLEDGE_MAX_UPLOAD_MB
  (20, qua proxy cổng 3000 file 12 MB không bị cắt nên giữ 20), không mã hoá, tối đa 300 trang; file trên đĩa
  tên `<uuid>.pdf`, tên gốc chỉ là metadata; không endpoint nào phục vụ file.
- /admin/documents (require_admin): GET danh sách / {id}; POST multipart; POST /{id}/index (?force=true để lập
  lại); GET /{id}/preview (đã lập chỉ mục: 5 đoạn cách đều từ Chroma; chưa: đọc PDF qua pdf_guard, không nhúng);
  PATCH (metadata → cập nhật metadata đoạn; enabled → doc_enabled; không nhúng lại); DELETE (chỉ upload: đoạn →
  file → bản ghi; file thiếu vẫn xoá, trả file_missing=true). Builtin: xem và bật/tắt được; xoá, sửa thông tin,
  lập chỉ mục lại → 403. Audit chỉ ghi `{"fields": [...]}`.
- Metadata do người nhập được làm sạch (bỏ ký tự điều khiển, « » → ", title/authors_org ≤ 200, topic ≤ 100,
  license_note ≤ 500); `format_search_results` thêm làm sạch thuộc tính thẻ (" → ', < > → ‹ ›).
- Script: `scripts/backfill_knowledge_metadata.py [--dry-run]` gắn metadata doc_* cho đoạn builtin, không nhúng lại
  (đã chạy: 134 đoạn trước và sau, chạy lại 0 thay đổi). `ingest_knowledge` không xoá đoạn `doc_origin='upload'`;
  đoạn không đổi nội dung mà metadata khác thì chỉ cập nhật metadata.
- Lưu file: mount ghi được `./data/knowledge/uploads:/app/uploads` (đã áp dụng). Thư mục gitignore, giữ .gitkeep;
  `backend/uploads/` là điểm mount do Docker tạo. Lưu ý triển khai: sau khi sửa mount (volumes) trong
  docker-compose.yml phải chạy `docker compose up -d --force-recreate backend` (restart không áp dụng mount mới).
- Frontend: tab Tài liệu trong /admin (tự tải lại mỗi 3 s khi có tài liệu đang lập chỉ mục; tắt tài liệu builtin
  phải xác nhận; builtin ẩn nút xoá và lập chỉ mục lại; xem trước hiển thị văn bản thuần). Tab Hội thoại có từ 8b-2.

Quản trị (lát 8a, services/foods/admin.py, api/routers/admin_foods.py):
- `users.role`: enum user_role ('user' | 'admin'), NOT NULL, mặc định 'user'. Chỉ đổi được bằng
  `docker compose exec backend python scripts/make_admin.py <email> [--revoke]` (email không tồn tại → mã thoát 1).
  Cột is_superuser cũ KHÔNG dùng để cấp quyền. UserCreate và ProfileUpdate có extra="forbid" (gửi role → 422).
  /users/me và response đăng ký trả role chỉ để đọc.
- `require_admin`: đọc lại role + is_active từ DB ở mỗi request; chưa đăng nhập 401, không phải admin hoặc
  tài khoản bị khoá 403.
- `admin_audit_log` (admin_user_id ON DELETE SET NULL): mỗi thao tác ghi một dòng; details chỉ có mã ADM-,
  tên trường và số liệu dinh dưỡng trước/sau — không tên món, ghi chú hay email.
- Nguồn ADMIN_MANUAL (food_sources id 3, fiber_type "không xác định", carb_basis "glucid không gồm xơ (theo quy
  ước khi nhập)"); `foods.source_note` bắt buộc với nguồn 3 (CHECK); mã `ADM-xxxxx` từ sequence
  admin_food_ref_seq (không quay lui khi rollback, nên test làm nhảy số); unique index một phần trên
  name_search của nguồn 3, lỗi unique violation bắt thành 409.
- /admin/foods: GET (q, source, phân trang ≤ 50); POST chỉ tạo dưới ADMIN_MANUAL (mỗi cột g 0–100, năng lượng
  ≤ 900, tổng các chất CÓ NHẬP trong nước/protein/lipid/glucid/xơ ≤ 100,5 g; lệch Atwater 4/9/4 > 15% chỉ gắn cờ
  atwater_lech_15pct); PATCH/DELETE chỉ dòng ADMIN_MANUAL (VN/USDA → 403; DELETE đang có nhật ký → 409 kèm số
  mục); PATCH /{id}/preparation cho mọi nguồn (preparation_source=manual).
- Ghi chú nguồn trong kết quả lookup_food và trích dẫn chat (trường `note`) được cắt còn 300 ký tự, bao trong
  «…»; giao diện hiển thị dạng văn bản thuần. Script nạp VN/USDA và backfill_food_preparation không đụng dòng
  ADMIN_MANUAL (có test).
- Nạp nhiều món từ CSV (services/foods/admin_import.py, scripts/import_admin_foods.py; 2fab762):
  `docker compose exec backend python scripts/import_admin_foods.py --admin-email <email admin> [--file F]
  [--dry-run] [--update-existing]`, mặc định /app/data/foods/manual/dishes.csv. Kiểm tra từng dòng bằng chính
  AdminFoodCreate + check_mass_sum + normalize_search, ghi qua create_food / update_food nên cùng mã ADM-xxxxx, cờ
  atwater_lech_15pct, chặn trùng tên và audit (food.create; food.update before/after như PATCH). Cột bắt buộc:
  name_vi, energy_kcal, protein_g, fat_g, carb_g (glucid không gồm xơ, trên 100 g), source_note; tuỳ chọn (vắng
  cột hoặc ô trống = không có số liệu): fiber_g, water_g, refuse_pct, group_name, preparation (raw / cooked /
  processed / dried / unknown), name_original. Đọc CSV bằng read_csv của trình nạp tập luyện (`,` `;` tab,
  utf-8-sig, cắt khoảng trắng); số nhận "1,5" và "1.5", từ chối dấu hàng nghìn. Kiểm tra TOÀN BỘ trước (kể cả
  tổng chất sau khi gộp với món đã có): một lỗi → không ghi gì, mã thoát 1, liệt kê mọi lỗi kèm số dòng CSV.
  Trùng tên (không phân biệt dấu) với món ADMIN_MANUAL đã có → bỏ qua và báo; --update-existing → cập nhật (cột
  có trong file ghi đè, ô trống xoá giá trị; cột vắng giữ nguyên; không đổi gì → không ghi audit). Trùng tên
  trong cùng file là lỗi. Dòng "(VÍ DỤ)" luôn bỏ qua; cột lạ chỉ cảnh báo. --admin-email bắt buộc cả khi
  --dry-run (không có / không phải admin / bị khoá → mã thoát 1); dry-run không tiêu số ADM-. Báo cáo: số thêm
  mới, cập nhật, không đổi, bỏ qua, và danh sách món lệch Atwater > 15%. data/foods/manual/ (được commit):
  README.md (cột, quy đổi nhãn sang 100 g, vd. sữa 180 ml 120 kcal → 66,7 kcal/100 g) và dishes_template.csv
  (tiêu đề + 1 dòng "(VÍ DỤ)").
- Món đã nạp vào ADMIN_MANUAL (DB dev, kiểm ngày 2026-11-08: 70 dòng, ADM-00658…ADM-00765, không liên tục do
  sequence bị test dùng), nạp bằng scripts/import_admin_foods.py từ data/foods/manual/:
  - dishes.csv (đợt 1, 8 món): phở bò, bún bò Huế, cơm tấm sườn, bánh mì thịt, bún chả, cơm gà, trà sữa trân
    châu, cà phê sữa đá.
  - dishes_all.csv (68 dòng): 62 món mới (món chế biến, đồ uống và 24 thực phẩm cơ bản, vd. Hủ tiếu Nam Vang,
    Mì Quảng, Cơm tấm bì chả) + cập nhật 6 món đợt 1 bằng --update-existing.
  - Mọi số liệu trên 100 g. Khẩu phần trong tên món ("1 tô ≈ 500 g", "1 đĩa", "1 ly") là GIẢ ĐỊNH, không có cột
    khẩu phần. Món có nhiều nguồn lấy trung bình.
  - Nguồn: bảng dinh dưỡng chuỗi Roll'd (Úc), FatSecret, CalorieKing, Arise, công thức tự pha, và bảng calo blog
    Tu Farm (tu-farm.com, tra 08/11/2026) — Tu Farm là NGUỒN THỨ CẤP CHƯA KIỂM CHỨNG. Chi tiết:
    data/foods/manual/dishes_sources.md, dishes_batch2_sources.md, dishes_batch3_sources.md (kiểm 2026-11-08:
    hai file batch2/batch3 CHƯA có trong repo, dishes_sources.md chưa nhắc Tu Farm); tóm tắt trong source_note.
  - 24 thực phẩm cơ bản đặt tên kèm hậu tố "(Tu Farm)" (vd. "Dưa chuột (Tu Farm)") để không trùng tên với dòng
    VN 2007 / USDA (unique index chỉ chặn trùng trong ADMIN_MANUAL; hậu tố giúp người dùng và LLM phân biệt).
  - Cảnh báo số liệu: Bánh tét 408 kcal/100 g cao bất thường (cần kiểm lại). Lệch Atwater > 15% (có cờ
    atwater_lech_15pct, đúng 5 dòng): Bánh xèo (1 suất ≈ 200 g), Nem chua rán, Rau muống luộc (Tu Farm), Rau bina
    (Tu Farm), Dưa chuột (Tu Farm).
- Frontend: trang /admin (hỏi lại /users/me; không phải admin → /dashboard, chưa đăng nhập → /login), tab
  Thực phẩm (bảng tìm/lọc, thêm/sửa/xoá chỉ dòng ADMIN_MANUAL, form kiểm tra như backend). Liên kết "Quản trị"
  trên dashboard chỉ hiện khi role là admin.

Tiến độ (lát 7, services/progress.py):
- `body_metrics`: duy nhất (user_id, measured_on), FK CASCADE, CHECK cân nặng 20–300, vòng eo NULL hoặc
  30–250. Ngày theo giờ VN, tối đa +1 ngày. Ghi cân KHÔNG đổi cân nặng trong hồ sơ.
- API (JWT, bản ghi người khác → 404): POST /body-metrics (upsert; trường không gửi giữ nguyên, null rõ
  ràng thì xoá; 201 tạo mới / 200 cập nhật), GET /body-metrics?from=&to= (mặc định 90 ngày, tối đa 366),
  DELETE /body-metrics/{id}; GET /progress?days=7|30|90 (ngày trống là null, không bao giờ 0; cờ
  incomplete_totals; mục tiêu từ metrics_service, hồ sơ chưa đủ thì null + is_complete=false);
  GET /progress/weekly-report?week_start= (thứ Hai, mặc định tuần trước; tuần chưa hết dùng days_elapsed
  làm mẫu số; nhận xét do code tạo, trung tính, kèm ghi chú calo).
- Dashboard (frontend/src/components/dashboard/): thẻ hôm nay, biểu đồ calo và cân nặng tự vẽ bằng SVG
  (không thêm thư viện, có aria-label và dòng chữ giá trị gần nhất), form ghi/sửa/xoá số đo, thẻ báo cáo tuần,
  nút Đăng xuất.

Nguồn dữ liệu thực phẩm (`food_sources`, id cố định):
- 1 = VN2007, Bảng thành phần thực phẩm Việt Nam 2007: 509 dòng (nhóm 14 đồ uống bị loại, thiếu STT 450).
  source_ref = mã số; trích theo trang PDF; xơ = celluloza.
- 2 = USDA_SR_LEGACY_2018 (CC0): 20 mục đã duyệt (`USDA_SELECTION` trong services/foods/usda.py), nạp từ
  data/foods/usda_selected.csv; source_ref = fdc_id; xơ = xơ thực phẩm tổng số (TDF).
- 3 = ADMIN_MANUAL: quản trị viên nhập qua /admin/foods; source_ref = ADM-xxxxx; nhãn "Quản trị viên nhập";
  mỗi dòng có source_note. DB dev hiện không có dòng nào (dòng thử đầu-cuối đã xoá).

RAG gồm (kiểm 2026-11-08, bảng knowledge_documents khớp Chroma, cả 4 đang bật) — tổng 198 đoạn:
- builtin: ISSN 2017 "diets and body composition" (34 đoạn) và WHO 2020 "physical activity and sedentary
  behaviour" (100 đoạn) (data/knowledge/raw; danh mục ở sources.csv).
- upload qua /admin (lưu ở data/knowledge/uploads, ngoài git): hai chương trích từ giáo trình thương mại NASM
  Essentials of Personal Fitness Training, 6th edition (NASM; Brian G. Sutton biên tập, 2018) — chương 7
  "Flexibility Training Concepts" (khởi động, giãn cơ; 32 đoạn, giữ 38/40 trang) và chương 13 "Resistance Training
  Concepts" (tập sức mạnh, hướng dẫn từng bài dạng Preparation / Movement / Safety; 32 đoạn, giữ 47/50 trang).
  Trang bị bỏ đều là danh mục tham khảo cuối chương (ch.7 tr. 39–40, ch.13 tr. 48–50; nhãn lý do của tr. 40 / 49
  ghi "phụ lục danh sách thành viên" là gọi chưa đúng, thực chất vẫn là danh mục tham khảo).
  Số trang trích dẫn (trang_pdf) là số trang của FILE CẮT, không phải số trang sách: trang sách = trang_pdf + 160
  (chương 7) và trang_pdf + 302 (chương 13).
  Văn bản là bản quét qua OCR: có lỗi chữ vặt (vd. "forma 2.", "ShutterSteck", "| s") và vài đoạn trộn hai cột,
  nên các bước có thể lẫn thứ tự.
PDF bảng 2007 dùng cho foods, không nạp vào RAG.

Cấu hình tra cứu (services/foods/aliases.py, có test): SYNONYMS, AMBIGUOUS (bơ, bo, tôm, chuối, bắp, mè,
thơm, mãng cầu, táo, hồng, dưa, com), COOKED_DISHES (xôi, cháo: chỉ có gạo sống), FOOD_ALIASES (ức gà, cơm,
cá hồi, yến mạch...). Giá trị preparation gán tay: PREPARATION_OVERRIDES trong preparation.py.

## 3. Quy ước làm việc đã chốt
- Không tự commit; báo danh sách file đổi để người dùng commit. Kế hoạch file trước, chờ xác nhận.
- Test mock hoàn toàn Gemini và embedding; test DB dùng Postgres thật trong transaction rollback
  (fixture `db_session`, `foods_session`), skip kèm lý do nếu không kết nối được.
- Thư mục migration thật: backend/alembic/versions/ (bỏ qua các thư mục trùng versions/versions,
  alembic/alembic, scripts/scripts: người dùng tự dọn).
- /app/data trong container mount chỉ đọc: ghi file ra /tmp trong container rồi `docker cp` ra máy.
  Ngoại lệ: data/eval/results mount ghi được tại /app/eval_results; data/knowledge/uploads ghi được tại /app/uploads.
- Ngoài git: data/knowledge/_review/, data/foods/external/ (USDA thô 45 MB), data/eval/results/* (giữ .gitkeep),
  backend/eval_results/ (điểm mount do Docker tạo).
- Trước/sau migration hoặc nạp dữ liệu: so md5 các cột dữ liệu của dòng VN2007 và của meal_logs; sao lưu
  DB bằng pg_dump ra scratchpad trước migration lớn; chạy upgrade → downgrade → upgrade.
- Script nạp đều có --dry-run; --reset chỉ đụng nguồn của chính script và bị từ chối nếu meal_logs tham chiếu.
- Vết công cụ khi thử đầu-cuối: thêm tạm 1 dòng log chỉ tên công cụ + tên tham số rồi gỡ ngay; không ghi
  nội dung tin nhắn hay hồ sơ vào log. SQL echo tắt (SQL_ECHO), hide_parameters=True, access log bỏ query string.
- DB dev có các user thử: e2e-…@example.com (thử tay), eval-mau / eval-chua-ho-so / eval-nhat-ky-trong
  @example.com (bộ đánh giá, chạy lại cho cùng trạng thái). Không tự xoá. Miền .local bị validation từ chối.
  `admin-e2e-050b60@example.com` đang là admin (thử lát 8a); `user-e2e-050b60@example.com` là user thường;
  `admin-docs-e2e-37892b@example.com` đang là admin (thử lát 8b-1). `train9b-e2e-010ec9@example.com` là user
  thường (thử lát 9b; enrollment thử đã xoá cùng chương trình giả). `train9d-e2e-5c20e2@example.com` là user thường
  (thử lát 9d; hồ sơ cuối: nữ, 30 tuổi, 160 cm, 60 kg, nhẹ, giảm cân; enrollment thử đã xoá).
- Test cần Chroma dùng collection TẠM (`test_docs_<uuid>`, xoá sau mỗi test), embedding giả; PDF test tạo bằng
  code (tests/pdf_factory.py, văn bản ASCII). So rag_smoke trước/sau bằng vector câu hỏi nhúng một lần rồi lưu.

## 4. Ràng buộc môi trường
- Gemini miễn phí: khoảng 20 lượt/ngày/mô hình cho dự án này (người dùng cung cấp; từng gặp ResourceExhausted
  dù đã giãn 40–75 s). Mỗi câu có dùng công cụ tốn 2 lượt trở lên. Không gọi Gemini khi không cần.
- Hạn mức embedding cũng thấp: mỗi lần search_knowledge (và mỗi câu rag_smoke) tốn một lượt embedding; ngày
  2026-11-04 từng gặp ResourceExhausted khi chạy 10 câu liền nhau, giãn 15 s mỗi câu thì qua.
- Mô hình: gemini-2.5-flash (temperature 0,3); embedding models/gemini-embedding-001.
- Frontend chạy bản build production: đổi giao diện cần `docker compose build frontend && docker compose up -d frontend`.

## 5. Bộ đánh giá
- File: data/eval/eval_questions.csv (38 câu, nhóm A–F); code: backend/evaluation/; CLI:
  backend/scripts/run_eval.py (--group, --id, --resume, --retrieval-only, --delay mặc định 45 s).
- Quy ước v1: bản ở commit eade8b0 là mốc "trước" — KHÔNG sửa. Cột điểm lan1_*/lan2_* do người dùng chấm
  (hiện trống cả 38 dòng).
- Câu lỗi thời sau 5d-2 (dữ liệu đã có món): C04 (ức gà), C08 (bông cải xanh giờ trỏ USDA), C09 (cơm),
  C10 (yến mạch). auto_check của các câu này có thể gây hiểu nhầm.
- Câu lỗi thời sau khi nạp 70 món ADMIN_MANUAL: các câu về món ăn của bản v1 giờ cho đáp án khác — C04, C08,
  C09, C10 (như trên, nay còn có thể khớp thêm dòng "(Tu Farm)") và C05 ("Một tô phở bò bao nhiêu calo?" — v1
  mong đợi "chưa có số liệu cho món hoàn chỉnh, không nêu số cho cả tô", nay DB có "Phở bò (1 tô ≈ 500 g)"); D01
  (nấu phở bò) phần "gợi ý tra dinh dưỡng" giờ có dữ liệu. Chưa chạy lại các câu này. Cần tạo bản v2, giữ v1
  (eade8b0) làm mốc, KHÔNG sửa v1.
- Sau khi tải hai chương NASM (rag_smoke 10 câu A bằng vector câu hỏi đã lưu, 0 lượt embedding): 9/10 câu giống
  hệt; số đoạn qua ngưỡng 40 → 43. A06 ("Tập tạ mấy buổi mỗi tuần thì đủ?") bị NASM ch.13 chen vào top 3 (tr. 9
  0,6614; tr. 11 0,6567; tr. 14 0,6524), đoạn WHO tr. 12 (0,6510, nguồn kỳ vọng) tụt xuống hạng 4. A09 vẫn không
  đoạn nào qua ngưỡng (0,6382); A10 không đổi (0,6710). D03 ("Hướng dẫn tôi tập squat đúng kỹ thuật.") nay truy
  xuất được đoạn squat NASM ch.13 tr. 45–47 (0,7006) nên trả lời được: bản v2 cần đổi kỳ vọng D03 (v1 mong đợi
  "nói chưa có tài liệu về kỹ thuật tập") và xem lại nguồn kỳ vọng A06.
- Kết quả đã chạy (data/eval/results/, ngoài git):
  - results_20261102-012741_retrieval.csv: retrieval nhóm A. A09 không đoạn nào vượt ngưỡng (cao nhất 0,638);
    A06 chỉ 1 đoạn (0,651).
  - results_20261102-012809.csv: B01, C02, D02, F01 auto dat; E01 khong_dat (chấm theo cột công cụ cũ).
  - results_20261102-124431.csv: A01–A08 đều ok, mỗi câu gọi search_knowledge, có nguồn ISSN/WHO; auto_check
    "dat" chỉ là kiểm tra công cụ — nội dung CHƯA chấm.
- Chưa chạy: A09–A10, phần lớn B–F, và lần đo 2. auto_check nhóm B/C chỉ chứng minh nhất quán với DB/API,
  không chứng minh DB đúng như PDF.

## 6. Hạn chế đã biết
- Bảng VN 2007 không có thực phẩm đã nấu chín; preparation chỉ gán khi tên ghi rõ (392/509 unknown).
- glucid (carb_g) không gồm xơ cho mọi nguồn; USDA carb_g = carbohydrate by difference − TDF (thiếu xơ → NULL).
  Xơ hai nguồn khác loại nên tổng xơ khi lẫn nguồn chỉ mang tính tham khảo.
- USDA: "cup" là chén đong Mỹ (~240 ml), không phải bát cơm; food_portion CHƯA dùng; không có tỷ lệ thải bỏ;
  năng lượng tính bằng hệ số Atwater riêng (không kiểm 4/9/4); cá ngừ 171986 tổng khối lượng 102,32 g.
- Foundation Foods chưa dùng (bản tải thiếu food.csv, food_nutrient.csv, food_portion.csv).
- Tra "cơm" kèm 2 dòng VN chỉ khớp một phần (Rau giền cơm, Cốm). Xếp hạng ứng viên SQL chưa xét vị trí từ khoá.
- Ngưỡng RAG 0,65 là tạm (một số câu giáp ranh 0,64–0,65). Kỹ thuật tập nay chỉ có hai chương NASM (bản OCR có
  lỗi chữ, vài đoạn trộn hai cột; trang trích dẫn là trang file cắt); chưa có tài liệu về lượng nước. NASM là giáo
  trình thương mại (có bản quyền; file tải lên nằm ngoài git). Quy tắc kỹ thuật động tác mới CHƯA thử với Gemini thật.
- LLM đôi khi không làm đúng quy tắc (không nêu trạng thái, gọi lại bằng tên người dùng gõ) — chỉ kiểm được
  bằng thử thật.
- ESLint frontend lỗi sẵn ("nextVitals is not iterable"); kiểm tra frontend bằng tsc và next build.
- Bản quyền bảng 2007 trong data/foods/README.md: người dùng tự điền.
- Tiến độ: chưa có gợi ý cập nhật cân nặng trong hồ sơ từ lần đo mới nhất (mục tiêu calo vẫn tính theo cân
  nặng trong hồ sơ). Trung bình calo chỉ tính trên ngày có nhật ký nên thấp hơn thực tế nếu ghi thiếu bữa.
  Dashboard mới chỉ kiểm bằng tsc/next build, chưa thử trên trình duyệt; get_progress_summary chưa thử với
  Gemini thật.
- Quản trị (8a): trùng tên mới test bằng hai yêu cầu liên tiếp, CHƯA test bằng hai kết nối song song thật (cần
  commit dữ liệu ra ngoài transaction của test). Chưa có giao diện quản lý bài tập (nạp bằng CSV). Ô trạng thái
  sống/chín của dòng VN/USDA chỉ đọc trên giao diện (đổi được qua API). Quy tắc 17 chưa thử với Gemini thật.
- Món ăn ADMIN_MANUAL (70 món): món Việt chủ yếu dựa dữ liệu chuỗi nhà hàng ở Úc (Roll'd) và ứng dụng đếm calo,
  cộng blog Tu Farm (thứ cấp, chưa kiểm chứng) — độ chính xác thấp, không phải phân tích phòng thí nghiệm hay bảng
  thành phần chính thức; mỗi quán khác nhau (lượng bánh/cơm, thịt, nước dùng, đường, sữa đặc). Cơm tấm sườn chỉ
  có hai nguồn. Bánh tét 408 kcal/100 g và 5 dòng lệch Atwater chưa được kiểm lại. Khẩu phần chỉ nằm trong tên
  món (giả định) nên số "1 tô / 1 ly" phải tự nhân từ số trên 100 g. Tài liệu nguồn batch2/batch3 chưa có trong
  repo. lookup_food chỉ hiện nhãn
  "Quản trị viên nhập" kèm ghi chú nguồn, không phân biệt món ước tính với số liệu nhãn. Chưa test hai lần nạp
  song song thật (dựa vào unique index như 8a). Module thực phẩm dùng read_csv của services/training/seed.py.
- Tài liệu RAG (8b-1): chưa test hai kết nối lập chỉ mục song song thật (đã test unique index ở mức DB và đường
  409 qua API). python-multipart nhận và lưu tạm cả body trước khi endpoint kiểm giới hạn 20 MB (không chặn sớm
  theo header). Văn bản PDF test viết không dấu (font Helvetica trong PDF tạo bằng code). Lập chỉ mục chạy trong
  tiến trình uvicorn (BackgroundTasks), khởi động lại giữa chừng thì bản ghi thành failed/gian_doan và phải thử lại.
- Giao diện: frontend đã build lại sau lát 8b-1, nhưng CHƯA có ghi nhận thử trên trình duyệt cho dashboard, trang
  /admin (tab Thực phẩm, tab Tài liệu, xác nhận khi tắt tài liệu builtin, tải file lớn); mới kiểm bằng tsc/next
  build và gọi API trực tiếp.
- Hội thoại (8b-2): hội thoại được giữ vô thời hạn (chưa có chính sách lưu trữ).
- Tập luyện (9a): FR13 và FR14 được đơn giản hoá có chủ đích — chưa có nhóm cơ, lưu ý an toàn riêng từng bài,
  ghi từng hiệp/lần/mức tạ; mỗi mục chỉ là một video YouTube kèm label. Chưa có theo dõi hoàn thành ngày, ghi số
  phút, gợi ý chương trình, công cụ chatbot (đã làm ở 9b/9d). Không kiểm link còn xem được (checked_on do người
  nhập điền). Hai lần nạp chạy cùng lúc không có khoá (ràng buộc UNIQUE sẽ báo lỗi). Trang /training chưa thử trên
  trình duyệt, container frontend chưa build lại sau 9a.
- Tập luyện (9b): chưa test hai kết nối đồng thời thật (mới dựa vào unique index, khoá FOR UPDATE và đường 409).
  minutes_done chụp lúc đánh dấu nên nạp lại lịch sau đó không cập nhật số phút đã lưu. Số ngày giảm chỉ phát hiện
  được khi có ngày đã đánh dấu vượt khoảng (không lưu số ngày lúc bắt đầu). Số phút là do người dùng tự đánh dấu,
  hệ thống không kiểm tra có xem video. Access log có id enrollment và số ngày trong đường dẫn (không có tên
  chương trình hay số phút). Trang tập luyện và thẻ dashboard chưa thử trên trình duyệt.
- Tập luyện (9d): recommend_program / get_training_summary và quy tắc TẬP LUYỆN CHƯA thử với Gemini thật; bộ đánh
  giá chưa có câu hỏi tập luyện. Câu trả lời "đã tập đều / mới bắt đầu" không được lưu (tải lại trang là mất). Luật
  chỉ phân biệt 2 level; vì các chương trình dự kiến đều weight_loss, người có mục tiêu khác giảm cân luôn thấy ghi
  chú "hiện chưa có chương trình riêng cho mục tiêu này". Hộp gợi ý chưa thử trên trình duyệt.
- Tập luyện (dữ liệu, ảnh xem trước): link YouTube có thể bị kênh gỡ hoặc đặt riêng tư bất cứ lúc nào; hệ thống
  không tự kiểm (ảnh lỗi chỉ hiện khối xám, nút vẫn mở link). Chưa có thời lượng từng video nên total_minutes,
  minutes_done của hai chương trình là null và thẻ dashboard hiện "chưa có dữ liệu thời lượng". Hai bài dùng lại
  link của nguoi-moi-14 trong toan-than-28 chưa được kiểm chứng bằng mắt, nhất là ngày 13 mục 4 (label "10 phút
  cánh tay và cơ bụng", trùng video với "10 phút tập bụng và cánh tay" ngày 1 của nguoi-moi-14). Ảnh xem trước tải
  thẳng từ i.ytimg.com (trình duyệt người dùng gửi IP tới Google, không gửi referrer); mới kiểm bằng tsc/next
  build, chưa thử trên trình duyệt.

## 7. Việc còn lại (thứ tự dự kiến)
1. Thử trên trình duyệt: dashboard, /admin tab Thực phẩm và tab Tài liệu (tải lên, lập chỉ mục, xem trước, bật/tắt,
   xoá); thử get_progress_summary, một dòng ADMIN_MANUAL qua lookup_food và search_knowledge có tài liệu tải lên
   với Gemini thật (vài lượt).
   Thêm: tab Hội thoại (8b-2), nút xoá phiên trong chat, trang /training (gợi ý, bắt đầu, đánh dấu, tập lại) và
   thẻ Tập luyện tuần này sau khi build lại frontend, ảnh xem trước trên trang ngày tập (cả màn hẹp và ảnh lỗi);
   vài câu hỏi tập luyện với Gemini thật (recommend_program, get_training_summary).
2. Dữ liệu tập luyện: kiểm chứng bằng mắt hai video dùng chung (toan-than-28 ngày 5 và ngày 13), điền
   duration_min (và kênh nếu muốn) cho 43 video rồi nạp lại; định kỳ kiểm link còn xem được.
3. Món ăn thủ công: đưa dishes_batch2_sources.md, dishes_batch3_sources.md vào repo (hiện chưa có); kiểm lại
   bánh tét và 5 dòng lệch Atwater (sửa bằng --update-existing nếu cần); tìm nguồn tốt hơn cho món Việt (ưu
   tiên nguồn Việt Nam đã công bố) và thêm nguồn cho cơm tấm sườn; thử lookup_food với vài món (vd. "1 tô phở
   bò", tên trùng giữa dòng "(Tu Farm)" và VN 2007) với Gemini thật.
   Quản trị bài tập của FR19 (hiện nạp bằng CSV) chưa xếp lát.
4. Gợi ý cập nhật cân nặng trong hồ sơ từ lần đo mới nhất (chỉ dạng gợi ý, người dùng xác nhận; chưa chốt cách làm).
5. Chính sách lưu trữ hội thoại (hiện giữ vô thời hạn).
6. Chốt mô hình cho demo (hiện gemini-2.5-flash, giới hạn ~20 lượt/ngày/mô hình ở gói miễn phí).
7. Đóng gói và README: hướng dẫn chạy từ đầu (docker compose, migration, các script nạp dữ liệu, tạo admin),
   repo hiện chưa có README ở thư mục gốc.
8. Tạo bản v2 của bộ đánh giá: cập nhật hành vi mong đợi C04/C08/C09/C10, câu phở bò C05 (và D01) theo 70 món
   ADMIN_MANUAL, giữ nguyên v1 ở eade8b0 làm mốc, rồi đo lần 2 và so với mốc eade8b0. Có thể thêm
   câu đánh giá cho tiến độ, dòng quản trị viên nhập và tập luyện (gợi ý chương trình, tiến độ tập).
9. Báo cáo đồ án (bảng "Trạng thái thực hiện" ở SPEC.md mục 4 là căn cứ phạm vi).
Đã bỏ có chủ đích: gợi ý thực đơn / thay món (FR10–11 ngoài phạm vi) và bộ lọc câu hỏi y khoa riêng bằng code
(FR7 đáp ứng bằng quy tắc prompt, dòng cảnh báo dưới ô nhập và nhóm câu hỏi E).
Thứ tự trên là dự kiến của người dùng; chi tiết từng lát chưa chốt (chưa chắc).
