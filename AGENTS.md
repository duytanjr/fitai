# Hướng dẫn dành cho AI Agent & Lập trình viên (AGENTS.md)

Tài liệu này cung cấp các quy chuẩn phát triển và hướng dẫn lệnh chạy kiểm thử, vận hành dự án FitAI.

---

## 1. Lệnh chạy kiểm thử (Backend Pytest)

Backend sử dụng `pytest` kết hợp `pytest-asyncio` và `httpx` để kiểm thử tự động.

### Chạy kiểm thử qua Docker (Khuyến nghị)
Khi các container đang chạy (`docker compose up -d`):

```bash
# Chạy toàn bộ test suite
docker compose exec backend pytest -v

# Hoặc dùng trực tiếp tên container
docker exec fitai_backend pytest -v

# Chạy một file test cụ thể
docker compose exec backend pytest tests/test_health.py -v

# Chạy kèm đo coverage (nếu cần)
docker compose exec backend pytest --cov=. -v
```

### Chạy kiểm thử trực tiếp trên máy host
Nếu phát triển trực tiếp trong môi trường Python ảo (`.venv`):

```bash
cd backend
source .venv/bin/activate  # Trên macOS/Linux
pytest -v
```

---

## 2. Cấu trúc thư mục kiểm thử
- `backend/pytest.ini`: Cấu hình chung cho pytest (`asyncio_mode = auto`, `testpaths = tests`, `pythonpath = .`).
- `backend/tests/conftest.py`: Fixture cung cấp `async_client` (FastAPI test client qua ASGI transport) và thiết lập môi trường test.
- `backend/tests/test_health.py`: Test mẫu kiểm tra endpoint `/health`.
- `backend/tests/test_security.py`: Test unit cho hashing mật khẩu và sinh mã JWT token.

---

## 3. Quy tắc bảo mật khi phát triển
- Tuyệt đối không commit file `.env` hoặc file chứa secret/API key thật lên Git.
- Mọi biến môi trường mới cần được khai báo mẫu (chỉ tên biến, không giá trị) tại `.env.example` ở thư mục gốc và `backend/.env.example`.
- `SECRET_KEY` là trường bắt buộc (không có giá trị mặc định), backend sẽ từ chối khởi động nếu thiếu.
