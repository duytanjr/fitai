from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.log_filters import install_access_log_filter
from api.routers import admin_conversations, admin_documents, admin_foods, auth, body_metrics, chat, foods, meals, progress, training, users
from api.routers.profile import router as profile_router

# Access log không ghi query string (có thể chứa từ khoá tìm thực phẩm của người dùng)
install_access_log_filter()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(profile_router, prefix=settings.API_V1_STR)
app.include_router(foods.router, prefix=settings.API_V1_STR)
app.include_router(meals.router, prefix=settings.API_V1_STR)
app.include_router(body_metrics.router, prefix=settings.API_V1_STR)
app.include_router(progress.router, prefix=settings.API_V1_STR)
app.include_router(training.router, prefix=settings.API_V1_STR)
app.include_router(admin_foods.router, prefix=settings.API_V1_STR)
app.include_router(admin_documents.router, prefix=settings.API_V1_STR)
app.include_router(admin_conversations.router, prefix=settings.API_V1_STR)

ADMIN_PREFIX = f"{settings.API_V1_STR}/admin/"


@app.middleware("http")
async def no_store_for_admin(request, call_next):
    """Mọi phản hồi /admin/* (kể cả 401/403/422/429) không được lưu cache — có thể chứa dữ liệu nhạy cảm."""
    response = await call_next(request)
    if request.url.path.startswith(ADMIN_PREFIX):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


@app.on_event("startup")
async def recover_knowledge_documents() -> None:
    """Bản ghi kẹt ở 'indexing' → failed (gian_doan); đăng ký tài liệu có sẵn. Lỗi chỉ ghi log, không chặn app."""
    import logging

    from core.database import AsyncSessionLocal
    from services.knowledge.documents import recover_interrupted, sync_builtin_documents

    try:
        async with AsyncSessionLocal() as db:
            recovered = await recover_interrupted(db)
            await sync_builtin_documents(db)
            await db.commit()
        if recovered:
            logging.getLogger(__name__).warning("Recovered %d interrupted indexing job(s)", recovered)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("Knowledge documents startup check failed: %s", type(exc).__name__)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
