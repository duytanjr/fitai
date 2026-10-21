"""
AI Agent Service — Fitness & Nutrition Advisor
Placeholder: full LangChain agent logic will go here.
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from core.config import settings


SYSTEM_PROMPT = """
You are FitAI, an expert fitness and nutrition advisor.
Your role is to provide personalized, science-backed advice on:
- Exercise routines tailored to the user's goals and fitness level
- Nutritional guidance, meal plans, and macro/calorie targets
- Recovery, sleep, and lifestyle habits

Always ask for relevant user information (age, weight, goal) before giving detailed advice.
Reply in the same language the user writes in.
"""


class FitnessAdvisorAgent:
    """LangChain-powered agent for fitness & nutrition consultations."""

    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7,
            convert_system_message_to_human=True,
        )

    async def chat(self, history: list[dict], user_message: str) -> str:
        """
        Send a message and return the AI response.

        Args:
            history: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
            user_message: The new user message.

        Returns:
            AI response string.
        """
        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_message))

        response = await self.llm.ainvoke(messages)
        return response.content


# Singleton instance (lazy-loaded per request or app startup)
fitness_agent = FitnessAdvisorAgent()
