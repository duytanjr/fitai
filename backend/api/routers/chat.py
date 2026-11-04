"""API Routers cho tính năng Chatbot (FR4, FR6)."""
import uuid
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.user import User
from api.dependencies.auth import get_current_user
from api.schemas.chat import (
    ChatMessageCreate,
    ChatResponse,
    ChatSessionOut,
    ChatMessageOut,
)
from services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def send_chat_message(
    body: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gửi tin nhắn đến FitAI Advisor.

    Yêu cầu đăng nhập (JWT).
    - Tạo session mới nếu không truyền session_id.
    - Kiểm tra quyền sở hữu nếu truyền session_id (404 nếu không khớp).
    - Nạp 10 tin nhắn trước đó làm ngữ cảnh hội thoại.
    - Cá nhân hóa system prompt từ hồ sơ; agent tự gọi search_knowledge (RAG) và
      calc_body_metrics (đọc hồ sơ của chính user này).
    - Trả kèm `sources`: các đoạn tài liệu đã dùng (tối đa 5, bỏ trùng tài liệu + trang).
    - Lưu tin nhắn (kèm sources) vào DB chỉ khi AI phản hồi thành công.
    """
    service = ChatService(db)
    session_id, reply, sources = await service.handle_chat(
        user_id=current_user.id,
        message=body.message,
        session_id=body.session_id,
    )
    return ChatResponse(session_id=session_id, reply=reply, sources=sources)


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách các phiên trò chuyện của người dùng hiện tại (mới nhất xếp trước)."""
    service = ChatService(db)
    sessions = await service.get_user_sessions(user_id=current_user.id)
    return sessions


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_session_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lấy toàn bộ lịch sử tin nhắn của một phiên chat cụ thể theo thứ tự thời gian.

    Trả về 404 nếu phiên không tồn tại hoặc không thuộc người dùng hiện tại.
    """
    service = ChatService(db)
    messages = await service.get_session_messages(
        user_id=current_user.id, session_id=session_id
    )
    return messages


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Người dùng xoá phiên của CHÍNH mình (kèm mọi tin nhắn — FK ON DELETE CASCADE).

    Trả 404 nếu phiên không tồn tại hoặc không thuộc người dùng hiện tại.
    """
    await ChatService(db).delete_session(user_id=current_user.id, session_id=session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
