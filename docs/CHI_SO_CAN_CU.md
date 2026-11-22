# Chỉ số và căn cứ trong code (đối chiếu ngày 2026-11-23, nhánh nang-cap-ai)

Tài liệu này chỉ mô tả những gì code hiện đang làm. Cột "nguồn" chép đúng chú thích trong code; chỗ nào code
không ghi tài liệu cụ thể thì ghi "chưa có nguồn". Đường dẫn tính từ thư mục gốc repo.

## a) Các trường nhập trong hồ sơ người dùng và form onboarding

Lưu ở bảng `user_profiles` (`backend/models/profile.py:66-79`), nhận qua `PUT /profile` với schema
`ProfileUpdate` (`backend/api/schemas/profile.py:19-91`, trường lạ bị từ chối 422). Form onboarding
(`frontend/src/components/onboarding/OnboardingForm.tsx`) gửi các trường dưới đây, trường nào để trống thì không
gửi (`:179-194`); riêng phần bệnh lý chỉ được gửi khi người dùng đã thao tác ở bước "Sức khỏe" (`:188-192`).

| Trường | Kiểu và giá trị cho phép | Được dùng ở công thức nào | Vị trí trong code |
|---|---|---|---|
| `age` | Số nguyên, 13–100, có thể để trống. Form: ô số `min=13 max=100`, không bắt buộc ở bước 1 (chỉ kiểm khoảng khi đã nhập); dưới 18 tuổi hiện cảnh báo mềm, không chặn | BMR (`- 5 × tuổi`); gợi ý chương trình tập (tuổi ≥ 60 → mức người mới) | DB `backend/models/profile.py:66`; schema `backend/api/schemas/profile.py:23`, kiểm khoảng `:66-70`; form `OnboardingForm.tsx:66`, `:274`, cảnh báo dưới 18 `:132` |
| `gender` | Chuỗi `male` / `female` / `other` (schema đổi về chữ thường), có thể để trống. Form: ô chọn Nam / Nữ / Khác, **bắt buộc** ở bước 1 | BMR (hằng số giới tính); calo sàn tối thiểu | DB `backend/models/profile.py:67` (String 20); schema `backend/api/schemas/profile.py:24`, kiểm `:87-92`; form `OnboardingForm.tsx:26-30`, `:69`, `:295` |
| `height_cm` | Số thực, 100–250 cm, có thể để trống. Form: `min=100 max=250 step=0.1`, không bắt buộc ở bước 1 | BMI; BMR (`+ 6,25 × cm`); gợi ý chương trình tập (qua BMI) | DB `backend/models/profile.py:68`; schema `backend/api/schemas/profile.py:25`, kiểm `:73-77`; form `OnboardingForm.tsx:71`, `:315` |
| `weight_kg` | Số thực, 20–300 kg, có thể để trống. Form: `min=20 max=300 step=0.1`, không bắt buộc ở bước 1 | BMI; BMR (`+ 10 × kg`); protein (g/kg); gợi ý chương trình tập (qua BMI) | DB `backend/models/profile.py:69`; schema `backend/api/schemas/profile.py:26`, kiểm `:80-84`; form `OnboardingForm.tsx:75`, `:332` |
| `activity_level` | Enum `sedentary` / `light` / `moderate` / `active` / `very_active`, có thể để trống. Form: nút chọn, **bắt buộc** ở bước 2 | TDEE (hệ số vận động); gợi ý chương trình tập (mức người mới hay trung bình) | Enum `backend/models/profile.py:12-17`, DB `:70`; schema `backend/api/schemas/profile.py:27`; form `OnboardingForm.tsx:11-17`, `:80`, `:359` |
| `fitness_goal` | Enum `weight_loss` / `muscle_gain` / `maintenance` / `endurance`, có thể để trống. Form: nút chọn, **bắt buộc** ở bước 2 | Calo mục tiêu (hệ số mục tiêu); protein (g/kg); gợi ý chương trình tập (chọn chương trình cùng mục tiêu; chặn chương trình giảm cân khi BMI < 18,5) | Enum `backend/models/profile.py:20-24`, DB `:71`; schema `backend/api/schemas/profile.py:28`; form `OnboardingForm.tsx:19-24`, `:81`, `:371` |
| `dietary_restrictions` | Chuỗi tự do, có thể để trống. DB giới hạn 500 ký tự (String 500); schema và form (textarea) **không** kiểm độ dài. Form: nằm ở bước 3 "Sức khỏe" | Không có công thức nào (chỉ đưa vào system prompt của chatbot) | DB `backend/models/profile.py:72`; schema `backend/api/schemas/profile.py:29`; form `OnboardingForm.tsx:474`; prompt `backend/services/ai_agents/fitness_advisor.py:538`, `:552` |
| `medical_conditions` | Mảng mã bệnh `varchar(40)[]`, NOT NULL, mặc định rỗng (người dùng cũ: `[]`). Mã hợp lệ (7 mã, từ migration `e4c1a8f2d905`): `musculoskeletal` (Viêm khớp, loãng xương, đau lưng), `cardiovascular` (Tim mạch), `hypertension` (Tăng huyết áp), `metabolic` (Bệnh chuyển hóa, gồm tiểu đường), `respiratory` (Bệnh hô hấp), `stroke` (Đột quỵ), `other` (Khác). Mã cũ (`diabetes`, `kidney`, `pregnancy_lactation`…) bị từ chối 422; mã lạ còn sót trong DB bị bỏ qua ở mọi nơi. Schema: mã lạ → 422, loại trùng giữ thứ tự, `null` → 422 (muốn "không có" thì gửi `[]`), tối đa 50 phần tử trước khi loại trùng. Form: 6 ô bệnh + "Khác" + "Không có" (loại trừ nhau), toàn bộ tùy chọn | **Không** đổi con số nào ở bảng b); chỉ sinh cảnh báo theo bảng c); gợi ý chương trình tập (chỉ mức người mới) | Mã và nhãn `backend/models/profile.py:27-52` (frontend: `frontend/src/lib/medical.ts`); DB `:74-76`; schema `backend/api/schemas/profile.py:31`, kiểm `:38-47`; form `OnboardingForm.tsx:388-440` |
| `medical_notes` | Chuỗi tự do tối đa 500 ký tự, có thể null. Schema cắt khoảng trắng hai đầu, chuỗi rỗng → null, dài hơn 500 → 422. Form: chỉ hiện và chỉ gửi khi tick "Khác", có đếm ký tự, `maxLength=500` | Không có công thức nào (chỉ đưa vào system prompt, trong thẻ `<ghi_chu_benh_ly>` như dữ liệu) | DB `backend/models/profile.py:77`; schema `backend/api/schemas/profile.py:32`, kiểm `:50-56`; form `OnboardingForm.tsx:412-414`; prompt `backend/services/ai_agents/fitness_advisor.py:543`, quy tắc 20 `:584-590` |
| `medical_consent` (chỉ ở request) | Bool thật (`StrictBool`; `"true"`, `1` → 422), tùy chọn. Bắt buộc `true` khi `medical_conditions` không rỗng, nếu không → 422. **Không lưu** giá trị bool. Form: ô "Tôi hiểu và đồng ý" chỉ hiện và chỉ bắt buộc khi đã chọn ít nhất một bệnh | Không có công thức nào | Schema `backend/api/schemas/profile.py:34`, kiểm `:59-62`; router bỏ khỏi dữ liệu lưu `backend/api/routers/profile.py:48`; form `OnboardingForm.tsx:452`, `:167` |
| `medical_consent_at` (server đặt) | `timestamptz`, null. Không nhận từ client (gửi lên → 422 vì trường lạ). Server đặt = thời điểm lưu khi gửi danh sách bệnh không rỗng (đã có đồng ý); đặt null khi danh sách được xoá về rỗng; không gửi `medical_conditions` thì giữ nguyên | Không có công thức nào | DB `backend/models/profile.py:79`; router `backend/api/routers/profile.py:52-53` |

Ghi chú:
- Hồ sơ được coi là đủ (`is_complete`) khi có cả 6 trường `age`, `gender`, `height_cm`, `weight_kg`,
  `activity_level`, `fitness_goal` (`backend/api/schemas/profile.py:124-125`). Danh sách trường bắt buộc để tính
  chỉ số: `backend/services/metrics_service.py:241-248`. Thiếu trường nào thì mọi chỉ số ở bảng b) là null kèm
  `missing_fields` (`:257-262`); `health_warnings` vẫn được trả.
- Form onboarding cho phép bỏ trống tuổi, chiều cao, cân nặng (chỉ kiểm khoảng khi đã nhập,
  `OnboardingForm.tsx:62-84`), nên người dùng có thể lưu hồ sơ chưa đủ để tính chỉ số.
- Mô tả mức vận động `light` nay thống nhất "1–3 ngày/tuần" ở form (`OnboardingForm.tsx:13`), chú thích hệ số
  (`backend/services/metrics_service.py:16`) và system prompt (`backend/services/ai_agents/fitness_advisor.py:523`).
- Form onboarding không nạp hồ sơ cũ. Vì vậy phần bệnh lý chỉ được gửi khi người dùng đã tick hoặc bỏ tick ở bước
  "Sức khỏe"; nếu không, gửi `[]` sẽ xoá bệnh đã khai trước đó.
- Các trường hồ sơ (kể cả tên bệnh tiếng Việt và ghi chú bệnh lý) được đưa vào system prompt để cá nhân hoá câu
  trả lời (`backend/services/chat_service.py:79-91`, `backend/services/ai_agents/fitness_advisor.py:497-554`);
  prompt không chứa con số chỉ số cơ thể, chatbot phải gọi công cụ `calc_body_metrics`.
- Dữ liệu bệnh lý không được ghi log (không có handler hay middleware nào đọc body request; SQLAlchemy đặt
  `hide_parameters=True`) và không xuất hiện ở các API quản trị xem hội thoại; có test kiểm cả hai.

## b) Các chỉ số tính ra

Mọi hàm ở `backend/services/metrics_service.py` là hàm thuần (không DB, không LLM). Ba ngữ cảnh dùng chung:
API `GET /profile/metrics`, công cụ `calc_body_metrics` của chatbot, và mục tiêu trong nhật ký ăn uống / tiến độ
(qua `profile_metrics_summary`, `:251-285`). Bệnh lý tự khai báo **không** đổi con số nào trong bảng này.

| Chỉ số | Công thức | Hằng số | Vị trí trong code | Nguồn đang ghi trong code |
|---|---|---|---|---|
| BMI | cân nặng (kg) / (chiều cao (m))², làm tròn 0,1 | Phân loại: < 18,5 "Thiếu cân"; 18,5–< 25 "Bình thường"; 25–< 30 "Thừa cân"; ≥ 30 "Béo phì" (xét trên số đã làm tròn) | `backend/services/metrics_service.py:83-103` | "phân loại theo chuẩn WHO" (`:84`); không ghi tài liệu, năm hay trang cụ thể |
| BMR | 10 × kg + 6,25 × cm − 5 × tuổi + hằng số giới tính, làm tròn 0,01 | Nam +5; nữ −161; khác −78 | Hàm `:106-122`; hằng số `:43-49` | "công thức Mifflin-St Jeor" (`:42`, `:107`); không ghi tài liệu gốc. Giá trị −78 cho "other" ghi rõ là "quy ước xấp xỉ hệ thống, không phải công thức y khoa chuẩn" (`:46-47`) |
| TDEE | BMR × hệ số vận động, làm tròn 0,01 | sedentary 1,2; light 1,375; moderate 1,55; active 1,725; very_active 1,9 | Hàm `:125-134`; hệ số `:14-20` | "Dựa trên công thức chuẩn tính TDEE từ BMR" (`:13`); chưa có nguồn |
| Calo mục tiêu | round(TDEE × hệ số mục tiêu); nếu nhỏ hơn calo sàn thì lấy calo sàn và bật cờ `calorie_floor_applied` | Hệ số: weight_loss 0,85; muscle_gain 1,10; maintenance 1,00; endurance 1,00 | Hàm `:137-164`; hệ số `:23-30` | Chưa có nguồn. endurance = 1,00 ghi là "QUY ƯỚC ĐƠN GIẢN HÓA" (`:27-29`) |
| Calo sàn tối thiểu (chặn dưới của calo mục tiêu) | Lấy theo giới tính | Nam 1500; nữ 1200; khác 1350 kcal | `:34-40`, áp dụng ở `:161-163` | "Chặn dưới an toàn y tế" (`:33`); chưa có nguồn. 1350 cho "other" ghi là "quy ước xấp xỉ hệ thống" (`:37-38`) |
| Protein (g/ngày) | round(cân nặng × hệ số g/kg) | weight_loss 2,0; muscle_gain 2,0; maintenance 1,6; endurance 1,6 g/kg | Hàm `:167-203`, công thức `:187`; hệ số `:52-58` | Chưa có nguồn. endurance = 1,6 ghi là "QUY ƯỚC ĐƠN GIẢN HÓA" (`:56`) |
| Chất béo (g/ngày) | round(calo mục tiêu × 25% / 9) | 25% năng lượng; 9 kcal/g | `:190-191`; hằng số `:61`, `:63` | Chưa có nguồn |
| Carb (g/ngày) | round((calo mục tiêu − protein × 4 − chất béo × 9) / 4), âm thì lấy 0 | 4 kcal/g protein, 9 kcal/g chất béo, 4 kcal/g carb | `:194-201`; hằng số `:62-64` | Chưa có nguồn |
| Nước uống mỗi ngày | **Không có trong code** (không có hàm hay hằng số nào tính lượng nước) | — | — | — |
| Còn lại trong ngày (nhật ký ăn uống) | mục tiêu − đã ăn cho calo, protein, chất béo, carb, làm tròn 0,1 (âm = đã vượt); mục tiêu lấy từ bảng này (hồ sơ chưa đủ thì mục tiêu và "còn lại" null cả khối) | — | `backend/services/meals.py:29`, `:182-186` | Không có nguồn (phép trừ) |
| Trung bình và so với mục tiêu (tiến độ, báo cáo tuần) | Trung bình mỗi chất trên các ngày có nhật ký có số liệu; diff = trung bình − mục tiêu; diff_pct = diff / mục tiêu × 100 (làm tròn 0,1; không có mục tiêu hoặc mục tiêu 0 → null). Báo cáo tuần kèm thông điệp các cảnh báo dinh dưỡng và chung ở bảng c) | — | `backend/services/progress.py:194-221`; câu nhận xét `:363-403` | Không có nguồn (thống kê mô tả) |
| Thay đổi cân nặng | lần đo cuối − lần đo đầu trong khoảng, làm tròn 0,1; dưới 2 lần đo → null | — | `backend/services/progress.py:224-235` | Không có nguồn (phép trừ) |
| Mức chương trình tập được gợi ý | BMI < 18,5: không gợi ý chương trình giảm cân (xét trước nhất). **Có bất kỳ bệnh lý nào** → chỉ mức người mới (thay thế cũng chỉ người mới; không có chương trình người mới thì không gợi ý), `needs_medical_clearance=true`, bỏ qua câu trả lời "đã tập đều". Không bệnh lý: vận động sedentary/light, hoặc BMI ≥ 30, hoặc tuổi ≥ 60 → mức người mới (thay thế: trung bình); vận động moderate trở lên → trung bình (thay thế: người mới); người dùng tự nói đã tập đều / mới bắt đầu thì theo câu trả lời đó | LOW_BMI 18,5; HIGH_BMI 30,0; SENIOR_AGE 60 | `backend/services/training/recommend.py:36`, `:113-188` (bệnh lý `:122-128`, `:143-150`) | Chưa có nguồn (docstring `:1-21` ghi "Luật do code quyết định, không gọi LLM"). Quy tắc bệnh lý ghi "Quy tắc thiết kế, chưa có nguồn lâm sàng" (`:10-14`) |
| Nhắc tập cùng người lớn (trang tập luyện) | Hiện câu nhắc khi tuổi < 18 (chỉ hiển thị, không đổi gợi ý) | 18 | `frontend/src/components/training/TrainingShell.tsx:44` | Chưa có nguồn |
| Cảnh báo dưới 18 tuổi (form onboarding) | Hiện cảnh báo mềm khi 13 ≤ tuổi < 18, không chặn lưu | 18 | `frontend/src/components/onboarding/OnboardingForm.tsx:132` | Chưa có nguồn |

## c) Cảnh báo theo bệnh lý

Bệnh lý tự khai báo **không đổi mục tiêu** (BMI, BMR, TDEE, calo, protein, chất béo, carb luôn tính như người không
bệnh; ví dụ hồ sơ nam 22 tuổi, 180 cm, 78 kg, vận động nhẹ, giảm cân luôn ra 2104 kcal, protein 156 g, chất béo
58 g, carb 240 g dù có bệnh nào). Bệnh chỉ thêm cảnh báo dạng lưu ý chung kèm lời khuyên hỏi bác sĩ, **không** phải
chỉ dẫn điều trị. Không lọc bài tập theo bệnh: video có cột `intensity`, `impact`, `category`, `level`
(`backend/models/training.py`) nhưng 0/45 video published đã điền, nên chỉ cảnh báo bằng chữ.

Nguồn duy nhất của mọi cảnh báo: `backend/services/health_rules.py` (`HEALTH_RULES` `:67`, `DESIGN_RULE` `:17`,
nguồn WHO `:42`). Mỗi quy tắc có `source` (nguồn thật đã kiểm) hoặc ghi đúng chuỗi `DESIGN_RULE` =
"Quy tắc thiết kế, chưa có nguồn lâm sàng". Chỉ ý muối có nguồn: câu "In adults, salt intake should be limited
to less than 5 grams per day (2 grams per day sodium)" ở trang 3 của `data/knowledge/extra/who_healthy_diet.pdf`
(câu này dành cho người lớn). Bảng dưới xuất bằng `docker compose exec backend python scripts/export_health_rules.py`
(thêm `--csv` để ra CSV); test `backend/tests/test_health_rules.py` kiểm mọi `id` có mặt trong tài liệu này.

| id | Bệnh | Lĩnh vực | Nội dung cảnh báo | Nguồn |
|---|---|---|---|---|
| salt | cardiovascular (Tim mạch), hypertension (Tăng huyết áp), stroke (Đột quỵ) | Dinh dưỡng | Nên hạn chế muối: WHO khuyến nghị người lớn dùng dưới 5 g muối mỗi ngày; hãy hỏi bác sĩ về mức phù hợp với bạn | WHO, Healthy diet (fact sheet), tr. 3; năm 2026, cập nhật 26/01/2026; https://www.who.int/news-room/fact-sheets/detail/healthy-diet; file data/knowledge/extra/who_healthy_diet.pdf |
| sat_fat | cardiovascular (Tim mạch) | Dinh dưỡng | Lưu ý lượng chất béo bão hòa trong bữa ăn; hãy hỏi bác sĩ về chế độ ăn phù hợp | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| metabolic_diet | metabolic (Bệnh chuyển hóa (gồm tiểu đường)) | Dinh dưỡng | Cẩn thận khi cắt giảm calo mạnh và chú ý lượng, loại carb trong bữa ăn; hãy hỏi bác sĩ trước khi thay đổi chế độ ăn | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| msk_training | musculoskeletal (Viêm khớp, loãng xương, đau lưng) | Tập luyện | Tránh bài có xung lực mạnh (như bật nhảy) và bài dồn tải nặng lên cột sống; hãy hỏi bác sĩ về bài tập phù hợp | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| cardio_training | cardiovascular (Tim mạch) | Tập luyện | Giảm cường độ, không tập đến mức tối đa và chỉ tập khi bác sĩ đã cho phép; dừng tập ngay nếu đau ngực hoặc khó thở | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| htn_training | hypertension (Tăng huyết áp) | Tập luyện | Tập ở cường độ vừa và tránh nín thở khi nâng vật nặng; hãy hỏi bác sĩ trước khi tập | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| metabolic_training | metabolic (Bệnh chuyển hóa (gồm tiểu đường)) | Tập luyện | Theo dõi dấu hiệu hạ đường huyết khi tập; hãy hỏi bác sĩ cách phòng tránh và xử lý | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| resp_training | respiratory (Bệnh hô hấp) | Tập luyện | Tập ở cường độ vừa, khởi động kỹ và mang theo thuốc nếu bác sĩ đã kê; hãy hỏi bác sĩ trước khi tập | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| stroke_training | stroke (Đột quỵ) | Tập luyện | Nên tập khi có người giám sát, chú ý thăng bằng và nguy cơ ngã; hãy hỏi bác sĩ trước khi tập | Quy tắc thiết kế, chưa có nguồn lâm sàng |
| other_general | other (Khác) | Chung | Mục tiêu và gợi ý chỉ mang tính tham khảo với tình trạng sức khỏe bạn khai báo; hãy hỏi bác sĩ | Quy tắc thiết kế, chưa có nguồn lâm sàng |

- Mỗi cảnh báo trả qua API có dạng `{id, domain, codes, message, source, source_short, source_url}`; quy tắc áp
  cho nhiều bệnh (muối) chỉ xuất một lần, `codes` là các bệnh đã khai báo kích hoạt nó.
- `health_warnings` (đủ mọi lĩnh vực) có trong `GET /profile`, `GET /profile/metrics`, `calc_body_metrics`,
  `GET /meals/summary`, `GET /progress`, `GET /progress/weekly-report` và `get_progress_summary`. Báo cáo tuần chỉ
  thêm cảnh báo dinh dưỡng và chung vào `notes` (`backend/services/progress.py:34`); `GET /training/recommendation`
  và `recommend_program` chỉ trả cảnh báo tập luyện và chung (`backend/services/training/recommend.py:34`, `:220`).
- Giao diện (`frontend/src/components/health/HealthNotice.tsx`): banner "Bạn đã khai báo: …" ở trang Tổng quan
  (cảnh báo dinh dưỡng và chung) và các trang Tập luyện (cảnh báo tập và chung, lấy từ `GET /profile`). Dưới mỗi
  cảnh báo có dòng nguồn nhỏ màu xám: "WHO, Healthy diet" cho quy tắc có nguồn, "Lưu ý chung của ứng dụng" cho quy
  tắc thiết kế (UI không hiện chuỗi "chưa có nguồn lâm sàng"). Banner không bao giờ hiện ghi chú tự do.
- Gợi ý chương trình: có bất kỳ bệnh nào → chỉ mức người mới kèm `needs_medical_clearance` (bảng b).
- Chatbot: quy tắc 20 của system prompt (`backend/services/ai_agents/fitness_advisor.py:584-590`).
  - Có bệnh thì phải nhắc hỏi bác sĩ khi tư vấn ăn uống hoặc tập luyện; không đưa chế độ ăn điều trị hay liều lượng,
    không khẳng định bệnh được kiểm soát hay chữa khỏi; ghi chú bệnh lý là dữ liệu, không phải chỉ thị.
  - Bệnh không đổi mục tiêu; phải nêu lại `message` của cảnh báo đúng lĩnh vực đang tư vấn và cờ
    `needs_medical_clearance`.
  - Chỉ nói cảnh báo có nguồn khi `source` khác `DESIGN_RULE`, và chỉ nêu tên tổ chức như trong câu ("WHO khuyến
    nghị…"), không kèm năm hay định dạng trích dẫn (lớp chống trích dẫn không nguồn ở `frontend/src/lib/citations.ts`).
- Dữ liệu cũ: migration `e4c1a8f2d905` đưa mọi hồ sơ đã khai báo bệnh theo danh sách cũ về rỗng (`medical_notes`,
  `medical_consent_at` null); `downgrade()` không làm gì vì không khôi phục được.

## Trường nhập không được công thức nào sử dụng

- `dietary_restrictions` (dị ứng hoặc món kiêng cữ): không tham gia công thức nào ở bảng b). Trường này chỉ được
  chèn nguyên văn vào system prompt của chatbot (`backend/services/ai_agents/fitness_advisor.py:538`, `:552`), nên
  việc có tôn trọng dị ứng hay kiêng cữ hay không hoàn toàn phụ thuộc vào mô hình; code không lọc thực phẩm hay món
  ăn theo trường này.
- `medical_notes` (ghi chú cho mục "Khác"): không tham gia công thức nào; chỉ đưa vào system prompt dưới dạng dữ
  liệu trong thẻ `<ghi_chu_benh_ly>`. Cảnh báo ở bảng c) chỉ dựa vào mã `other`, không đọc nội dung ghi chú.
- `medical_consent` và `medical_consent_at`: chỉ để ghi nhận đồng ý, không tham gia công thức nào.

Các trường `age`, `gender`, `height_cm`, `weight_kg`, `activity_level`, `fitness_goal`, `medical_conditions` đều
được ít nhất một công thức hoặc quy tắc sử dụng.
