# Chỉ số và căn cứ trong code (đối chiếu ngày 2026-11-22, nhánh nang-cap-ai)

Tài liệu này chỉ mô tả những gì code hiện đang làm. Cột "nguồn" chép đúng chú thích trong code; chỗ nào code
không ghi tài liệu cụ thể thì ghi "chưa có nguồn". Đường dẫn tính từ thư mục gốc repo.

## a) Các trường nhập trong hồ sơ người dùng và form onboarding

Lưu ở bảng `user_profiles` (`backend/models/profile.py:73-86`), nhận qua `PUT /profile` với schema
`ProfileUpdate` (`backend/api/schemas/profile.py:18-90`, trường lạ bị từ chối 422). Form onboarding
(`frontend/src/components/onboarding/OnboardingForm.tsx`) gửi các trường dưới đây, trường nào để trống thì không
gửi (`:179-194`); riêng phần bệnh lý chỉ được gửi khi người dùng đã thao tác ở bước "Sức khỏe" (`:188-192`).

| Trường | Kiểu và giá trị cho phép | Được dùng ở công thức nào | Vị trí trong code |
|---|---|---|---|
| `age` | Số nguyên, 13–100, có thể để trống. Form: ô số `min=13 max=100`, không bắt buộc ở bước 1 (chỉ kiểm khoảng khi đã nhập); dưới 18 tuổi hiện cảnh báo mềm, không chặn | BMR (`- 5 × tuổi`); gợi ý chương trình tập (tuổi ≥ 60 → mức người mới) | DB `backend/models/profile.py:73`; schema `backend/api/schemas/profile.py:22`, kiểm khoảng `:65-69`; form `OnboardingForm.tsx:66`, `:274`, cảnh báo dưới 18 `:132` |
| `gender` | Chuỗi `male` / `female` / `other` (schema đổi về chữ thường), có thể để trống. Form: ô chọn Nam / Nữ / Khác, **bắt buộc** ở bước 1 | BMR (hằng số giới tính); calo sàn tối thiểu | DB `backend/models/profile.py:74` (String 20); schema `backend/api/schemas/profile.py:23`, kiểm `:86-91`; form `OnboardingForm.tsx:26-30`, `:69`, `:295` |
| `height_cm` | Số thực, 100–250 cm, có thể để trống. Form: `min=100 max=250 step=0.1`, không bắt buộc ở bước 1 | BMI; BMR (`+ 6,25 × cm`); gợi ý chương trình tập (qua BMI) | DB `backend/models/profile.py:75`; schema `backend/api/schemas/profile.py:24`, kiểm `:72-76`; form `OnboardingForm.tsx:71`, `:315` |
| `weight_kg` | Số thực, 20–300 kg, có thể để trống. Form: `min=20 max=300 step=0.1`, không bắt buộc ở bước 1 | BMI; BMR (`+ 10 × kg`); protein (g/kg); gợi ý chương trình tập (qua BMI) | DB `backend/models/profile.py:76`; schema `backend/api/schemas/profile.py:25`, kiểm `:79-83`; form `OnboardingForm.tsx:75`, `:332` |
| `activity_level` | Enum `sedentary` / `light` / `moderate` / `active` / `very_active`, có thể để trống. Form: nút chọn, **bắt buộc** ở bước 2 | TDEE (hệ số vận động); gợi ý chương trình tập (mức người mới hay trung bình) | Enum `backend/models/profile.py:12-17`, DB `:77`; schema `backend/api/schemas/profile.py:26`; form `OnboardingForm.tsx:11-17`, `:80`, `:359` |
| `fitness_goal` | Enum `weight_loss` / `muscle_gain` / `maintenance` / `endurance`, có thể để trống. Form: nút chọn, **bắt buộc** ở bước 2 | Calo mục tiêu (hệ số mục tiêu); protein (g/kg); gợi ý chương trình tập (chọn chương trình cùng mục tiêu; chặn chương trình giảm cân khi BMI < 18,5) | Enum `backend/models/profile.py:20-24`, DB `:78`; schema `backend/api/schemas/profile.py:27`; form `OnboardingForm.tsx:19-24`, `:81`, `:371` |
| `dietary_restrictions` | Chuỗi tự do, có thể để trống. DB giới hạn 500 ký tự (String 500); schema và form (textarea) **không** kiểm độ dài. Form: nằm ở bước 3 "Sức khỏe" | Không có công thức nào (chỉ đưa vào system prompt của chatbot) | DB `backend/models/profile.py:79`; schema `backend/api/schemas/profile.py:28`; form `OnboardingForm.tsx:474`; prompt `backend/services/ai_agents/fitness_advisor.py:537`, `:551` |
| `medical_conditions` | Mảng mã bệnh `varchar(40)[]`, NOT NULL, mặc định rỗng (người dùng cũ: `[]`). Mã hợp lệ: `diabetes`, `hypertension`, `dyslipidemia`, `cardiovascular`, `kidney`, `gout`, `liver`, `stomach`, `musculoskeletal`, `pregnancy_lactation`, `other`. Schema: mã lạ → 422, loại trùng giữ thứ tự, `null` → 422 (muốn "không có" thì gửi `[]`), tối đa 50 phần tử trước khi loại trùng. Form: 10 ô tick + "Khác" + "Không có" (loại trừ nhau), toàn bộ tùy chọn | Calo mục tiêu và macro (để null theo bảng c); gợi ý chương trình tập (chỉ mức người mới) | Mã và nhãn `backend/models/profile.py:27-59` (frontend: `frontend/src/lib/medical.ts`); DB `:81-83`; schema `backend/api/schemas/profile.py:30`, kiểm `:37-46`; form `OnboardingForm.tsx:388-440` |
| `medical_notes` | Chuỗi tự do tối đa 500 ký tự, có thể null. Schema cắt khoảng trắng hai đầu, chuỗi rỗng → null, dài hơn 500 → 422. Form: chỉ hiện và chỉ gửi khi tick "Khác", có đếm ký tự, `maxLength=500` | Không có công thức nào (chỉ đưa vào system prompt, trong thẻ `<ghi_chu_benh_ly>` như dữ liệu) | DB `backend/models/profile.py:84`; schema `backend/api/schemas/profile.py:31`, kiểm `:49-55`; form `OnboardingForm.tsx:412-414`; prompt `backend/services/ai_agents/fitness_advisor.py:542`, quy tắc 20 `:583-588` |
| `medical_consent` (chỉ ở request) | Bool thật (`StrictBool`; `"true"`, `1` → 422), tùy chọn. Bắt buộc `true` khi `medical_conditions` không rỗng, nếu không → 422. **Không lưu** giá trị bool. Form: ô "Tôi hiểu và đồng ý" chỉ hiện và chỉ bắt buộc khi đã chọn ít nhất một bệnh | Không có công thức nào | Schema `backend/api/schemas/profile.py:33`, kiểm `:58-61`; router bỏ khỏi dữ liệu lưu `backend/api/routers/profile.py:48`; form `OnboardingForm.tsx:452`, `:167` |
| `medical_consent_at` (server đặt) | `timestamptz`, null. Không nhận từ client (gửi lên → 422 vì trường lạ). Server đặt = thời điểm lưu khi gửi danh sách bệnh không rỗng (đã có đồng ý); đặt null khi danh sách được xoá về rỗng; không gửi `medical_conditions` thì giữ nguyên | Không có công thức nào | DB `backend/models/profile.py:86`; router `backend/api/routers/profile.py:52-53` |

Ghi chú:
- Hồ sơ được coi là đủ (`is_complete`) khi có cả 6 trường `age`, `gender`, `height_cm`, `weight_kg`,
  `activity_level`, `fitness_goal` (`backend/api/schemas/profile.py:112-113`). Danh sách trường bắt buộc để tính
  chỉ số: `backend/services/metrics_service.py:255-262`. Thiếu trường nào thì mọi chỉ số ở bảng b) là null kèm
  `missing_fields` (`:290-295`); `health_warnings` vẫn được trả.
- Form onboarding cho phép bỏ trống tuổi, chiều cao, cân nặng (chỉ kiểm khoảng khi đã nhập,
  `OnboardingForm.tsx:62-84`), nên người dùng có thể lưu hồ sơ chưa đủ để tính chỉ số.
- Mô tả mức vận động `light` nay thống nhất "1–3 ngày/tuần" ở form (`OnboardingForm.tsx:13`), chú thích hệ số
  (`backend/services/metrics_service.py:16`) và system prompt (`backend/services/ai_agents/fitness_advisor.py:522`).
- Form onboarding không nạp hồ sơ cũ. Vì vậy phần bệnh lý chỉ được gửi khi người dùng đã tick hoặc bỏ tick ở bước
  "Sức khỏe"; nếu không, gửi `[]` sẽ xoá bệnh đã khai trước đó.
- Các trường hồ sơ (kể cả tên bệnh tiếng Việt và ghi chú bệnh lý) được đưa vào system prompt để cá nhân hoá câu
  trả lời (`backend/services/chat_service.py:79-91`, `backend/services/ai_agents/fitness_advisor.py:496-553`);
  prompt không chứa con số chỉ số cơ thể, chatbot phải gọi công cụ `calc_body_metrics`.
- Dữ liệu bệnh lý không được ghi log (không có handler hay middleware nào đọc body request; SQLAlchemy đặt
  `hide_parameters=True`) và không xuất hiện ở các API quản trị xem hội thoại; có test kiểm cả hai.

## b) Các chỉ số tính ra

Mọi hàm ở `backend/services/metrics_service.py` là hàm thuần (không DB, không LLM). Ba ngữ cảnh dùng chung:
API `GET /profile/metrics`, công cụ `calc_body_metrics` của chatbot, và mục tiêu trong nhật ký ăn uống / tiến độ
(qua `profile_metrics_summary`, `:284-321`).

| Chỉ số | Công thức | Hằng số | Vị trí trong code | Nguồn đang ghi trong code |
|---|---|---|---|---|
| BMI | cân nặng (kg) / (chiều cao (m))², làm tròn 0,1 | Phân loại: < 18,5 "Thiếu cân"; 18,5–< 25 "Bình thường"; 25–< 30 "Thừa cân"; ≥ 30 "Béo phì" (xét trên số đã làm tròn) | `backend/services/metrics_service.py:97-117` | "phân loại theo chuẩn WHO" (`:98`); không ghi tài liệu, năm hay trang cụ thể |
| BMR | 10 × kg + 6,25 × cm − 5 × tuổi + hằng số giới tính, làm tròn 0,01 | Nam +5; nữ −161; khác −78 | Hàm `:120-136`; hằng số `:43-49` | "công thức Mifflin-St Jeor" (`:42`, `:121`); không ghi tài liệu gốc. Giá trị −78 cho "other" ghi rõ là "quy ước xấp xỉ hệ thống, không phải công thức y khoa chuẩn" (`:46-47`) |
| TDEE | BMR × hệ số vận động, làm tròn 0,01 | sedentary 1,2; light 1,375; moderate 1,55; active 1,725; very_active 1,9 | Hàm `:139-148`; hệ số `:14-20` | "Dựa trên công thức chuẩn tính TDEE từ BMR" (`:13`); chưa có nguồn |
| Calo mục tiêu | round(TDEE × hệ số mục tiêu); nếu nhỏ hơn calo sàn thì lấy calo sàn và bật cờ `calorie_floor_applied` | Hệ số: weight_loss 0,85; muscle_gain 1,10; maintenance 1,00; endurance 1,00 | Hàm `:151-178`; hệ số `:23-30` | Chưa có nguồn. endurance = 1,00 ghi là "QUY ƯỚC ĐƠN GIẢN HÓA" (`:27-29`) |
| Calo sàn tối thiểu (chặn dưới của calo mục tiêu) | Lấy theo giới tính | Nam 1500; nữ 1200; khác 1350 kcal | `:34-40`, áp dụng ở `:175-177` | "Chặn dưới an toàn y tế" (`:33`); chưa có nguồn. 1350 cho "other" ghi là "quy ước xấp xỉ hệ thống" (`:37-38`) |
| Protein (g/ngày) | round(cân nặng × hệ số g/kg) | weight_loss 2,0; muscle_gain 2,0; maintenance 1,6; endurance 1,6 g/kg | Hàm `:181-217`, công thức `:201`; hệ số `:52-58` | Chưa có nguồn. endurance = 1,6 ghi là "QUY ƯỚC ĐƠN GIẢN HÓA" (`:56`) |
| Chất béo (g/ngày) | round(calo mục tiêu × 25% / 9) | 25% năng lượng; 9 kcal/g | `:204-205`; hằng số `:61`, `:63` | Chưa có nguồn |
| Carb (g/ngày) | round((calo mục tiêu − protein × 4 − chất béo × 9) / 4), âm thì lấy 0 | 4 kcal/g protein, 9 kcal/g chất béo, 4 kcal/g carb | `:208-215`; hằng số `:62-64` | Chưa có nguồn |
| Nước uống mỗi ngày | **Không có trong code** (không có hàm hay hằng số nào tính lượng nước) | — | — | — |
| Còn lại trong ngày (nhật ký ăn uống) | mục tiêu − đã ăn cho calo, protein, chất béo, carb, làm tròn 0,1 (âm = đã vượt); mục tiêu lấy từ bảng này. Chất có mục tiêu null (bệnh lý) thì "còn lại" cũng null | — | `backend/services/meals.py:29`, `:182-188` | Không có nguồn (phép trừ) |
| Trung bình và so với mục tiêu (tiến độ, báo cáo tuần) | Trung bình mỗi chất trên các ngày có nhật ký có số liệu; diff = trung bình − mục tiêu; diff_pct = diff / mục tiêu × 100 (làm tròn 0,1; không có mục tiêu, mục tiêu 0 hoặc mục tiêu null vì bệnh lý → null). Báo cáo tuần ghi "… trung bình X/ngày (không đặt mục tiêu)." cho chất có mục tiêu null, kèm thông điệp cảnh báo | — | `backend/services/progress.py:199-220`; câu nhận xét `:362-406` | Không có nguồn (thống kê mô tả) |
| Thay đổi cân nặng | lần đo cuối − lần đo đầu trong khoảng, làm tròn 0,1; dưới 2 lần đo → null | — | `backend/services/progress.py:223-234` | Không có nguồn (phép trừ) |
| Mức chương trình tập được gợi ý | BMI < 18,5: không gợi ý chương trình giảm cân (xét trước nhất). **Có bất kỳ bệnh lý nào** → chỉ mức người mới (thay thế cũng chỉ người mới; không có chương trình người mới thì không gợi ý), `needs_medical_clearance=true`, bỏ qua câu trả lời "đã tập đều". Không bệnh lý: vận động sedentary/light, hoặc BMI ≥ 30, hoặc tuổi ≥ 60 → mức người mới (thay thế: trung bình); vận động moderate trở lên → trung bình (thay thế: người mới); người dùng tự nói đã tập đều / mới bắt đầu thì theo câu trả lời đó | LOW_BMI 18,5; HIGH_BMI 30,0; SENIOR_AGE 60 | `backend/services/training/recommend.py:33`, `:110-185` (bệnh lý `:119-125`, `:140-147`) | Chưa có nguồn (docstring `:1-20` ghi "Luật do code quyết định, không gọi LLM"). Quy tắc bệnh lý ghi "Quy tắc thiết kế, chưa có nguồn lâm sàng" (`:10-13`) |
| Nhắc tập cùng người lớn (trang tập luyện) | Hiện câu nhắc khi tuổi < 18 (chỉ hiển thị, không đổi gợi ý) | 18 | `frontend/src/components/training/TrainingShell.tsx:39` | Chưa có nguồn |
| Cảnh báo dưới 18 tuổi (form onboarding) | Hiện cảnh báo mềm khi 13 ≤ tuổi < 18, không chặn lưu | 18 | `frontend/src/components/onboarding/OnboardingForm.tsx:132` | Chưa có nguồn |

## c) Quy tắc bệnh lý (quy tắc thiết kế, chưa có nguồn lâm sàng)

Mục đích: cảnh báo an toàn và không đưa con số có thể gây hại, **không** cá nhân hoá điều trị. BMI, BMR, TDEE
không đổi theo bệnh. Code: `backend/services/metrics_service.py:66-81` (chú thích ghi "QUY TẮC THIẾT KẾ, CHƯA CÓ
NGUỒN LÂM SÀNG"), `health_warnings` `:271-281`, áp dụng `:317-320`.

| Bệnh | Chỉ số bị để null (`withheld`) | Thông điệp (`message`) |
|---|---|---|
| `kidney` (Bệnh thận) | `protein_g`, `carb_g` (carb tính từ protein). Calo mục tiêu và chất béo giữ nguyên | "Mục tiêu protein không phù hợp khi có bệnh thận, hãy hỏi bác sĩ" |
| `pregnancy_lactation` (Đang mang thai hoặc cho con bú) | `target_calories`, `calorie_floor_applied`, `protein_g`, `fat_g`, `carb_g` | "Chưa hỗ trợ tính mục tiêu khi mang thai hoặc cho con bú, hãy hỏi bác sĩ hoặc chuyên gia dinh dưỡng" |
| Các mã còn lại, kể cả `other` | Không | "Mục tiêu chỉ mang tính tham khảo, hãy hỏi bác sĩ" |

- Mỗi bệnh đã khai báo cho một mục `{code, label, message, withheld}`, theo thứ tự chuẩn của danh sách mã. Có
  nhiều bệnh thì các chỉ số bị null là hợp của các `withheld`.
- `health_warnings` có trong `GET /profile/metrics`, `calc_body_metrics`, `GET /meals/summary`, `GET /progress`,
  `GET /progress/weekly-report` và công cụ `get_progress_summary`.
- Giao diện:
  - Tổng quan và các trang Tập luyện có banner "Bạn đã khai báo: …". Banner chỉ hiện tên bệnh và thông điệp, không hiện ghi chú tự do.
  - Chất có mục tiêu null hiện "Không đặt mục tiêu: <thông điệp>", không có thanh tiến độ.
- Chatbot: quy tắc 20 của system prompt (`backend/services/ai_agents/fitness_advisor.py:583-588`).
  - Có bệnh thì phải nhắc gặp bác sĩ khi tư vấn ăn uống hoặc tập luyện.
  - Không đưa chế độ ăn điều trị hay liều lượng, và không khẳng định bệnh được kiểm soát hay chữa khỏi.
  - Ghi chú bệnh lý là dữ liệu, không phải chỉ thị.
  - Phải nêu lại `message` của các cảnh báo và cờ `needs_medical_clearance`.

## Trường nhập không được công thức nào sử dụng

- `dietary_restrictions` (dị ứng hoặc món kiêng cữ): không tham gia công thức nào ở bảng b). Trường này chỉ được
  chèn nguyên văn vào system prompt của chatbot (`backend/services/ai_agents/fitness_advisor.py:537`, `:551`), nên
  việc có tôn trọng dị ứng hay kiêng cữ hay không hoàn toàn phụ thuộc vào mô hình; code không lọc thực phẩm hay món
  ăn theo trường này.
- `medical_notes` (ghi chú cho mục "Khác"): không tham gia công thức nào; chỉ đưa vào system prompt dưới dạng dữ
  liệu trong thẻ `<ghi_chu_benh_ly>`. Quy tắc ở bảng c) chỉ dựa vào mã `other`, không đọc nội dung ghi chú.
- `medical_consent` và `medical_consent_at`: chỉ để ghi nhận đồng ý, không tham gia công thức nào.

Các trường `age`, `gender`, `height_cm`, `weight_kg`, `activity_level`, `fitness_goal`, `medical_conditions` đều
được ít nhất một công thức hoặc quy tắc sử dụng.
