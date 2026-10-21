from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/sessions")
async def create_session(db: AsyncSession = Depends(get_db)):
    """Create a new chat session."""
    # TODO: get current_user from JWT dependency
    service = ChatService(db)
    # session = await service.create_session(user_id=current_user.id)
    return {"message": "Session creation stub"}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Send a user message and receive the AI response."""
    service = ChatService(db)
    # ai_reply = await service.send_message(session_id, current_user.id, body.content)
    return {"message": "Message send stub"}
