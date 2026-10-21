# FitAI Backend

## Cấu trúc dự án (Clean Architecture)

```
backend/
├── main.py                         # FastAPI app entry point
├── requirements.txt
├── Dockerfile
├── .env.example
│
├── core/                           # Cấu hình & cơ sở hạ tầng
│   ├── config.py                   # Pydantic Settings (biến môi trường)
│   ├── database.py                 # Async SQLAlchemy engine & session
│   └── security.py                 # JWT & bcrypt password hashing
│
├── models/                         # SQLAlchemy ORM models (DB schema)
│   ├── user.py
│   ├── profile.py
│   └── chat.py
│
├── api/                            # Presentation layer (HTTP)
│   ├── routers/
│   │   ├── auth.py                 # /api/v1/auth
│   │   └── chat.py                 # /api/v1/chat
│   └── dependencies/               # FastAPI Depends (auth, pagination…)
│
├── services/                       # Business logic layer
│   ├── chat_service.py
│   └── ai_agents/
│       └── fitness_advisor.py      # LangChain + Gemini agent
│
├── utils/                          # Shared helpers (logging, validators…)
└── tests/
```

## Khởi động nhanh

```bash
# 1. Sao chép biến môi trường
cp backend/.env.example backend/.env
# → Điền GOOGLE_API_KEY vào .env

# 2. Chạy toàn bộ stack
docker compose up --build

# 3. Truy cập API docs
open http://localhost:8000/api/v1/docs
```

## Chạy pgAdmin (tùy chọn)

```bash
docker compose --profile dev up
# → Mở http://localhost:5050  (admin@fitai.local / admin)
```
