# Trạng thái dự án FitAI (ghi chú bàn giao giữa các phiên)

Chỉ ghi những gì KHÔNG có trong SPEC.md / AGENTS.md. Cập nhật lần cuối: 2026-11-04.

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
| 7 (FR15–17) | chưa commit | body_metrics, /body-metrics, /progress, báo cáo tuần, get_progress_summary, dashboard tiến độ |

- pytest hiện tại: 487 passed, 0 skipped (sau lát 7; trước đó 393).
- Lát 7 trên nhánh feat/progress, chưa commit. md5 trước/sau migration e5a7c3b91f20 (trùng nhau):
  foods 529 dòng (VN + USDA) `8a773b9b054b5568fad90618824d9ced`, meal_logs 16 dòng
  `dead684f3f89244a24a7d81e4bd7f269`, food_sources 2 dòng `52bc5ff84530157b4e78a424a8f5fd2f`.
- Đổi nhãn "xơ thực phẩm tổng số" đã nằm trong 7516fb2 (chưa chắc: suy từ git status sạch).
- Dòng `food_sources.id=2` trong DB dev có thể còn chữ cũ "xơ ăn kiêng tổng số" (migration chạy trước khi đổi
  tên); chỉ là cột mô tả, chưa hiển thị ở đâu.

## 2. Kiến trúc đang chạy
Công cụ của agent (fitness_advisor.py, tối đa 3 vòng, 3 lệnh gọi/vòng, timeout 30 s):
- `search_knowledge(query)`: RAG trên Chroma, ngưỡng cosine 0,65, top-k 5.
- `calc_body_metrics()`: không nhận tham số; đọc hồ sơ của user lấy từ JWT.
- `lookup_food(query, grams?)`: tra bảng foods; code tính theo grams; mỗi dòng trích nguồn riêng.
- `get_daily_summary(date?)`: chỉ đọc nhật ký ngày của user hiện tại (giờ VN = UTC+7).
- `get_progress_summary(days=7)` (công cụ thứ 5): chỉ đọc, không nhận user_id; days ∈ {7, 30, 90}, sai thì
  trả lỗi tham số. Chỉ kèm chuỗi theo ngày khi days=7. Prompt quy tắc 16 (tiến độ): nói "N ngày gần nhất",
  không nói "tuần này", kèm calorie_note, không dùng từ đánh giá; quy tắc an toàn y tế giờ là số 17.

Bảng chính: users, user_profiles, chat_sessions, chat_messages (sources JSON), foods, food_sources,
meal_logs (FK RESTRICT tới foods), body_metrics. Migration head: e5a7c3b91f20.

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

RAG gồm: ISSN 2017 "diets and body composition" và WHO 2020 "physical activity and sedentary behaviour"
(data/knowledge/raw; danh mục ở sources.csv). PDF bảng 2007 dùng cho foods, không nạp vào RAG.

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
  Ngoại lệ: data/eval/results mount ghi được tại /app/eval_results.
- Ngoài git: data/knowledge/_review/, data/foods/external/ (USDA thô 45 MB), data/eval/results/* (giữ .gitkeep),
  backend/eval_results/ (điểm mount do Docker tạo).
- Trước/sau migration hoặc nạp dữ liệu: so md5 các cột dữ liệu của dòng VN2007 và của meal_logs; sao lưu
  DB bằng pg_dump ra scratchpad trước migration lớn; chạy upgrade → downgrade → upgrade.
- Script nạp đều có --dry-run; --reset chỉ đụng nguồn của chính script và bị từ chối nếu meal_logs tham chiếu.
- Vết công cụ khi thử đầu-cuối: thêm tạm 1 dòng log chỉ tên công cụ + tên tham số rồi gỡ ngay; không ghi
  nội dung tin nhắn hay hồ sơ vào log. SQL echo tắt (SQL_ECHO), hide_parameters=True, access log bỏ query string.
- DB dev có các user thử: e2e-…@example.com (thử tay), eval-mau / eval-chua-ho-so / eval-nhat-ky-trong
  @example.com (bộ đánh giá, chạy lại cho cùng trạng thái). Không tự xoá. Miền .local bị validation từ chối.

## 4. Ràng buộc môi trường
- Gemini miễn phí: khoảng 20 lượt/ngày/mô hình cho dự án này (người dùng cung cấp; từng gặp ResourceExhausted
  dù đã giãn 40–75 s). Mỗi câu có dùng công cụ tốn 2 lượt trở lên. Không gọi Gemini khi không cần.
- Mô hình: gemini-2.5-flash (temperature 0,3); embedding models/gemini-embedding-001.
- Frontend chạy bản build production: đổi giao diện cần `docker compose build frontend && docker compose up -d frontend`.

## 5. Bộ đánh giá
- File: data/eval/eval_questions.csv (38 câu, nhóm A–F); code: backend/evaluation/; CLI:
  backend/scripts/run_eval.py (--group, --id, --resume, --retrieval-only, --delay mặc định 45 s).
- Quy ước v1: bản ở commit eade8b0 là mốc "trước" — KHÔNG sửa. Cột điểm lan1_*/lan2_* do người dùng chấm
  (hiện trống cả 38 dòng).
- Câu lỗi thời sau 5d-2 (dữ liệu đã có món): C04 (ức gà), C08 (bông cải xanh giờ trỏ USDA), C09 (cơm),
  C10 (yến mạch). auto_check của các câu này có thể gây hiểu nhầm.
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
- Ngưỡng RAG 0,65 là tạm (một số câu giáp ranh 0,64–0,65). Chưa có tài liệu về kỹ thuật tập, lượng nước.
- LLM đôi khi không làm đúng quy tắc (không nêu trạng thái, gọi lại bằng tên người dùng gõ) — chỉ kiểm được
  bằng thử thật.
- ESLint frontend lỗi sẵn ("nextVitals is not iterable"); kiểm tra frontend bằng tsc và next build.
- Bản quyền bảng 2007 trong data/foods/README.md: người dùng tự điền.
- Tiến độ: chưa có gợi ý cập nhật cân nặng trong hồ sơ từ lần đo mới nhất (mục tiêu calo vẫn tính theo cân
  nặng trong hồ sơ). Trung bình calo chỉ tính trên ngày có nhật ký nên thấp hơn thực tế nếu ghi thiếu bữa.
  Dashboard mới chỉ kiểm bằng tsc/next build, chưa thử trên trình duyệt; get_progress_summary chưa thử với
  Gemini thật.

## 7. Việc còn lại (thứ tự dự kiến)
1. Hoàn tất lát 7: người dùng commit; `docker compose build frontend && docker compose up -d frontend`; thử
   dashboard trên trình duyệt; thử get_progress_summary với Gemini thật (vài lượt).
2. Gợi ý cập nhật cân nặng trong hồ sơ từ lần đo mới nhất (chỉ dạng gợi ý, người dùng xác nhận; chưa chốt cách làm).
3. Gợi ý thực đơn (FR10–11), có thể dùng food_portion sau khi xử lý đơn vị Mỹ.
4. Thể dục (FR12–14: bài tập, lịch tập, nhật ký tập).
5. Quản trị (FR18–20: tài liệu, CSDL món ăn và bài tập, nhật ký hội thoại ẩn danh).
6. Lọc câu hỏi y khoa (guardrail riêng, ngoài quy tắc prompt hiện có).
7. Cập nhật hành vi mong đợi C04/C08/C09/C10 (bản v2), rồi đo lần 2 và so với mốc eade8b0. Có thể thêm
   câu đánh giá cho tiến độ.
Thứ tự trên là dự kiến của người dùng; chi tiết từng lát chưa chốt (chưa chắc).
