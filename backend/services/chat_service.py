"""
Chat Service — business logic for creating sessions and persisting messages.
Placeholder: detailed DB operations will be added here.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from models.chat import ChatSession, ChatMessage
from services.ai_agents.fitness_advisor import fitness_agent


class ChatService:
    """Handles chat session lifecycle and message persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(self, user_id: str) -> ChatSession:
        """Create a new chat session for a user."""
        session = ChatSession(user_id=user_id, title="New Chat")
        self.db.add(session)
        await self.db.flush()
        return session

    async def send_message(
        self, session_id: str, user_id: str, content: str
    ) -> ChatMessage:
        """
        Persist user message → call AI agent → persist AI reply.
        Returns the AI's ChatMessage.
        """
        # TODO: fetch history from DB
        history: list[dict] = []

        # Save user message
        user_msg = ChatMessage(session_id=session_id, role="user", content=content)
        self.db.add(user_msg)

        # Get AI response
        ai_content = await fitness_agent.chat(history, content)

        # Save AI message
        ai_msg = ChatMessage(session_id=session_id, role="assistant", content=ai_content)
        self.db.add(ai_msg)
        await self.db.flush()

        return ai_msg
