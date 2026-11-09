# FitAI — Tư vấn thể dục và dinh dưỡng bằng AI

FitAI là ứng dụng web tư vấn thể dục và dinh dưỡng cá nhân hoá bằng tiếng Việt. Chatbot là một AI agent (Gemini)
biết gọi công cụ: tính chỉ số cơ thể từ hồ sơ, tra kho tri thức khoa học (RAG, có trích nguồn), tra bảng thành
phần thực phẩm, đọc nhật ký ăn uống, tiến độ và chương trình tập luyện. Ngoài chat còn có nhật ký bữa ăn, theo dõi
cân nặng và báo cáo tuần, chương trình tập theo video YouTube, và trang quản trị (thực phẩm, tài liệu RAG, hội thoại
ẩn danh).

**Công nghệ:** FastAPI (Python, SQLAlchemy async, Alembic), PostgreSQL 16, ChromaDB 1.5.9, Next.js (React),
Google Gemini (`gemini-2.5-flash`, embedding `models/gemini-embedding-001`), Docker Compose.

---

## 1. Yêu cầu

- **Docker Desktop** (có Docker Compose).
- **Khoá Gemini API riêng của mỗi người** (lấy tại Google AI Studio). Không dùng chung khoá.
  - Hạn mức free tier thấp: khoảng 20 lượt gọi mô hình mỗi ngày cho mỗi mô hình. Một câu chat có dùng công cụ tốn
    từ 2 lượt trở lên, nên thực tế chỉ chat được ít hơn 20 câu mỗi ngày.
  - Embedding cũng có hạn mức: nạp tài liệu RAG, lập chỉ mục tài liệu tải lên và mỗi lần chatbot tìm tài liệu
    (`search_knowledge`) đều tốn lượt embedding.

---

## 2. Chạy từ đầu

Các lệnh dưới chạy ở thư mục gốc của repo. Mọi script chạy **bên trong container backend**
(`docker compose exec backend ...`).

### 2.1. Biến môi trường

```bash
cp backend/.env.example backend/.env
```

Mở `backend/.env` và điền:

| Biến | Giá trị |
|---|---|
| `SECRET_KEY` | **Bắt buộc**: chuỗi ngẫu nhiên dài, vd. kết quả của `openssl rand -hex 32`. Thiếu thì backend không khởi động. |
| `GOOGLE_API_KEY` | **Bắt buộc**: khoá Gemini của bạn. |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:3000"]` (dạng danh sách JSON) để trình duyệt ở cổng 3000 gọi được API. |

**Quan trọng:** xoá (hoặc đặt `#` trước) mọi dòng còn để trống trong `backend/.env`. Dòng trống như `CHROMA_PORT=`
làm backend báo lỗi khi khởi động, còn `GEMINI_MODEL=` trống thì thành tên mô hình rỗng. Các biến không điền đều có
giá trị mặc định trong `backend/core/config.py`. `DATABASE_URL` và `CHROMA_HOST` do `docker-compose.yml` tự đặt.

File `.env` ở thư mục gốc là **tuỳ chọn**: docker compose đọc nó để lấy `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB` (mặc định `postgres` / `postgres` / `fitai_db`). Muốn đổi thì `cp .env.example .env` và chỉ giữ các
dòng có giá trị. Frontend không cần file `.env` (địa chỉ API đã đặt trong `docker-compose.yml`).

### 2.2. Khởi động

```bash
docker compose up -d --build
```

### 2.3. Tạo bảng (migration)

```bash
docker compose exec backend alembic upgrade head
```

### 2.4. Nạp dữ liệu (theo thứ tự)

Mỗi script đều chạy lại được nhiều lần mà không nhân đôi dữ liệu; nên chạy `--dry-run` trước khi có.

```bash
# 1) Bảng thành phần thực phẩm Việt Nam 2007 (đọc data/knowledge/raw/vn_food_composition_2007_vi.pdf)
docker compose exec backend python scripts/ingest_foods.py --dry-run
docker compose exec backend python scripts/ingest_foods.py

# 2) 20 thực phẩm USDA đã duyệt (đọc data/foods/usda_selected.csv)
docker compose exec backend python scripts/ingest_usda_foods.py --dry-run
docker compose exec backend python scripts/ingest_usda_foods.py

# 3) Hai chương trình tập luyện (đọc data/training/programs.csv, schedule.csv)
docker compose exec backend python scripts/seed_training.py --dry-run
docker compose exec backend python scripts/seed_training.py

# 4) Tài liệu RAG ISSN và WHO (đọc data/knowledge/sources.csv + raw/*.pdf) — TỐN LƯỢT EMBEDDING
docker compose exec backend python scripts/ingest_knowledge.py --dry-run   # chỉ chia đoạn, không gọi API
docker compose exec backend python scripts/ingest_knowledge.py
```

Bước 4 nhúng 134 đoạn (ISSN 34, WHO 100). Nếu gặp lỗi hạn mức, đợi một lúc rồi chạy lại: đoạn đã nhúng không bị
nhúng lại.

**5) Tạo tài khoản admin:** mở http://localhost:3000/register, đăng ký một tài khoản, rồi cấp quyền:

```bash
docker compose exec backend python scripts/make_admin.py <email-vừa-đăng-ký>
# thu hồi: docker compose exec backend python scripts/make_admin.py <email> --revoke
```

**6) Nạp 70 món chế biến, đồ uống và thực phẩm cơ bản** (nguồn "Quản trị viên nhập"; không tốn lượt Gemini):

```bash
# Đợt 1: 8 món (file mặc định data/foods/manual/dishes.csv)
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin> --dry-run
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin>

# Đợt 2: 62 món mới + cập nhật 6 món của đợt 1
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin> \
  --file /app/data/foods/manual/dishes_all.csv --update-existing --dry-run
docker compose exec backend python scripts/import_admin_foods.py --admin-email <email-admin> \
  --file /app/data/foods/manual/dishes_all.csv --update-existing
```

Cột CSV và cách quy đổi số liệu xem `data/foods/manual/README.md`.

**7) Hai chương NASM:** tải lên qua trang quản trị, xem mục 3.

---

## 3. Dữ liệu nằm trong repo

- **USDA FoodData Central** (SR Legacy, Foundation, Survey/FNDDS) ở `data/foods/external/`: không cần tải thêm.
  Bước nạp USDA chỉ dùng file con đã duyệt `data/foods/usda_selected.csv`; thư mục thô dùng để tạo lại file con
  (`scripts/build_usda_subset.py`) và tra cứu.
- **PDF nguồn** ở `data/knowledge/raw/`: ISSN 2017, WHO 2020 (cho RAG) và bảng thành phần thực phẩm VN 2007 (cho
  bảng thực phẩm, không nạp vào RAG). Danh mục ở `data/knowledge/sources.csv`.
- **Hai chương NASM** ở `data/knowledge/extra/` (`chuong7.pdf`, `chuong13.pdf`): **KHÔNG tự nạp** (`ingest_knowledge.py`
  không đọc thư mục này). Sau khi chạy xong mục 2: đăng nhập bằng tài khoản admin → vào http://localhost:3000/admin →
  tab **Tài liệu** → tải lên từng file, điền các ô bên dưới → bấm **Xem trước** rồi **Lập chỉ mục** (mỗi file khoảng
  32 đoạn, tốn lượt embedding).

| Ô | chuong13.pdf | chuong7.pdf |
|---|---|---|
| Tiêu đề | NASM Essentials of Personal Fitness Training, 6th edition, chương 13: Resistance Training Concepts (trích) | NASM Essentials of Personal Fitness Training, 6th edition, chương 7: Flexibility Training Concepts (trích) |
| Tác giả / tổ chức | National Academy of Sports Medicine (NASM); Brian G. Sutton (biên tập) | National Academy of Sports Medicine (NASM); Brian G. Sutton (biên tập) |
| Năm | 2018 | 2018 |
| Ngôn ngữ | en | en |
| Chủ đề | kỹ thuật tập sức mạnh, nguyên tắc tập tạ, tăng dần cường độ | khởi động, giãn cơ, các kỹ thuật giãn cơ |
| Giấy phép / quyền sử dụng | Giáo trình thương mại của NASM, © 2018 NASM (Jones & Bartlett Learning); chỉ dùng trích đoạn chương 13 cho mục đích học thuật của đồ án, có ghi nguồn | Giáo trình thương mại của NASM, © 2018 NASM (Jones & Bartlett Learning); chỉ dùng trích đoạn chương 7 cho mục đích học thuật của đồ án, có ghi nguồn |

Số trang chatbot trích dẫn cho NASM là số trang của file cắt: trang sách = trang + 160 (chương 7), trang + 302
(chương 13).

- **KHÔNG nằm trong repo:** dữ liệu PostgreSQL và ChromaDB (Docker volume `postgres_data`, `chroma_data` trên máy
  mỗi người). Vì vậy mỗi người phải tự chạy mục 2. File `.env`, tài liệu đã tải lên (`data/knowledge/uploads/`) và
  kết quả đánh giá (`data/eval/results/`) cũng không nằm trong repo.

---

## 4. Địa chỉ dịch vụ, test và đánh giá

| Dịch vụ | Địa chỉ trên máy |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend (FastAPI) | http://localhost:8000 — tài liệu API: http://localhost:8000/api/v1/docs |
| ChromaDB | http://localhost:8001 |
| PostgreSQL | `localhost:5433` (trong mạng Docker là `db:5432`) |
| pgAdmin (tuỳ chọn) | http://localhost:5050, chạy bằng `docker compose --profile dev up -d` |

**Chạy test** (dùng PostgreSQL thật trong transaction tự rollback, không gọi Gemini):

```bash
docker compose exec backend pytest
docker compose exec backend pytest tests/test_health.py -v   # một file
```

Chưa chạy migration hoặc chưa nạp bảng thực phẩm thì một số test tự bỏ qua (skip) kèm lời nhắc chạy
`alembic upgrade head` / `scripts/ingest_foods.py`; nên chạy test sau mục 2.

**Bộ đánh giá chatbot** (`data/eval/eval_questions.csv`, 38 câu nhóm A–F; kết quả ghi ra `data/eval/results/`):

```bash
docker compose exec backend python scripts/run_eval.py --group A --retrieval-only   # chỉ truy xuất, tốn embedding
docker compose exec backend python scripts/run_eval.py --id C04 --delay 0           # một câu
docker compose exec backend python scripts/run_eval.py --group B --group C
```

Bộ đánh giá gọi **Gemini thật** và tốn nhiều lượt (mỗi câu từ 2 lượt trở lên; mặc định nghỉ 45 giây giữa các câu).
Với free tier, chỉ nên chạy từng nhóm hoặc từng câu; dùng `--resume <file kết quả>` để chạy tiếp.

---

## 5. Lưu ý và lỗi thường gặp

- **Sửa `docker-compose.yml`** (nhất là phần `volumes`) thì phải chạy
  `docker compose up -d --force-recreate backend`; `restart` không áp dụng mount mới.
- **Đổi giao diện:** frontend chạy bản build production, nên sau khi sửa code frontend cần
  `docker compose build frontend && docker compose up -d frontend`.
- **Không tải lên được tài liệu ở /admin:** giao diện chỉ báo "Không tải lên được tài liệu. Kiểm tra các trường
  và thử lại." mà không nêu nguyên nhân. Xem nguyên nhân trong log:

  ```bash
  docker compose logs backend --tail=40
  ```

  Nếu thấy `FileNotFoundError: ... '/app/uploads/...'` (thư mục tải lên chưa được gắn vào container):

  ```bash
  mkdir -p data/knowledge/uploads
  docker compose up -d --force-recreate backend
  docker compose exec backend sh -c 'touch /app/uploads/.test && echo ghi duoc && rm /app/uploads/.test'
  ```

  Lệnh cuối phải in `ghi duoc`. Lưu ý: `docker compose up -d` thường không tạo lại container khi mount thay đổi,
  nên phải dùng `--force-recreate`.
- **Lỗi hạn mức Gemini** (`ResourceExhausted`, chatbot báo lỗi, tài liệu lập chỉ mục báo `loi_han_muc`): đã hết lượt
  của khoá. Đợi rồi thử lại (hạn mức tính theo ngày); với tài liệu thì bấm Lập chỉ mục lại, đoạn đã nhúng không bị
  nhúng lại.
- **Backend không khởi động:** xem `docker compose logs backend`; hay gặp nhất là thiếu `SECRET_KEY` hoặc còn dòng
  trống trong `backend/.env` (mục 2.1).

---

## 6. Giấy phép dữ liệu

| Dữ liệu | Nguồn / giấy phép |
|---|---|
| USDA FoodData Central (`data/foods/external/`, `usda_selected.csv`) | U.S. Department of Agriculture, CC0 (miền công cộng) |
| ISSN 2017 "diets and body composition" | Aragon A.A. et al., J Int Soc Sports Nutr 14:16; CC BY 4.0 |
| WHO 2020 "physical activity and sedentary behaviour" | WHO; CC BY-NC-SA 3.0 IGO (phi thương mại, phải ghi nguồn) |
| Bảng thành phần thực phẩm Việt Nam 2007 | Viện Dinh dưỡng (Bộ Y tế), NXB Y học; dùng cho mục đích học tập của đồ án, có ghi nguồn |
| 70 món nhập thủ công (`data/foods/manual/`) | Số liệu ước tính từ nguồn thứ cấp (bảng dinh dưỡng chuỗi nhà hàng, ứng dụng đếm calo, blog), độ chính xác thấp; chi tiết trong `data/foods/manual/dishes_sources_all.md` |
| Hai chương NASM (`data/knowledge/extra/`) | Giáo trình thương mại có bản quyền (© 2018 NASM, Jones & Bartlett Learning); chỉ dùng cho đồ án học thuật. **Repo phải để Private.** |
| Video tập luyện | Chỉ lưu link YouTube; bản quyền video thuộc kênh đăng tải |

---

## 7. Cấu trúc thư mục

```text
.
├── backend/            # FastAPI: api/, core/, models/, services/, scripts/, alembic/, tests/
├── frontend/           # Next.js: src/app, src/components, src/lib
├── data/
│   ├── foods/          # README bảng thực phẩm, usda_selected.csv, external/ (USDA thô), manual/ (70 món)
│   ├── knowledge/      # sources.csv, raw/ (ISSN, WHO, VN 2007), extra/ (NASM), uploads/ (ngoài git)
│   ├── training/       # programs.csv, schedule.csv của hai chương trình tập
│   └── eval/           # eval_questions.csv, results/ (ngoài git)
├── docs/PROJECT_STATE.md
├── SPEC.md
├── AGENTS.md
└── docker-compose.yml
```

**Nên đọc:**

- `SPEC.md` — khảo sát, yêu cầu chức năng FR1–FR20, thiết kế, và bảng "Trạng thái thực hiện" (mục 4).
- `docs/PROJECT_STATE.md` — trạng thái hiện tại: các lát đã làm, kiến trúc đang chạy, quy ước, hạn chế, việc còn lại.
- `AGENTS.md` — quy ước phát triển, cách chạy test, quy tắc bảo mật (không commit `.env`).
- `data/foods/README.md`, `data/foods/manual/README.md`, `data/knowledge/README.md`, `data/training/README.md` —
  chi tiết từng bộ dữ liệu.
