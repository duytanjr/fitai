"""Đối tượng giả dùng chung cho test RAG/agent — KHÔNG gọi Gemini hay embedding thật."""
import hashlib
import math
from typing import Callable

from langchain_core.messages import AIMessage


class FakeEmbedder:
    """Embedding giả, xác định: vector từ hash của văn bản (cùng văn bản → cùng vector)."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim
        self.document_calls = 0
        self.embedded_texts: list[str] = []

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [b - 127.5 for b in digest[: self.dim]]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        self.embedded_texts.extend(texts)
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def tool_call(name: str, args: dict | None = None, call_id: str | None = None) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id or f"call-{name}"}])


class FakeChatModel:
    """Thay ChatGoogleGenerativeAI: `script(messages, call_index, tool_choice)` trả AIMessage."""

    def __init__(self, script: Callable) -> None:
        self.script = script
        self.calls: list[dict] = []
        self.bound_tools: list[str] = []

    def bind_tools(self, tools, tool_choice=None, **kwargs):
        self.bound_tools = [t.name for t in tools]
        return _BoundFake(self, tool_choice)


class _BoundFake:
    def __init__(self, parent: FakeChatModel, tool_choice) -> None:
        self.parent = parent
        self.tool_choice = tool_choice

    async def ainvoke(self, messages):
        index = len(self.parent.calls)
        self.parent.calls.append({"messages": list(messages), "tool_choice": self.tool_choice})
        return self.parent.script(list(messages), index, self.tool_choice)
