"""Chạy app FastAPI NGAY TRONG TIẾN TRÌNH (httpx ASGITransport) để lấy vết gọi công cụ.

Vết công cụ (tên + TÊN tham số, không giá trị) và loại lỗi gốc của agent được ghi lại bằng cách bọc
FitnessAdvisorAgent._run_tool / _run trong tiến trình đánh giá — không sửa code ứng dụng, không ghi
gì vào log server. DB thật và Gemini thật (không mock).
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Iterator

from httpx import ASGITransport, AsyncClient

from core.database import AsyncSessionLocal
from evaluation.accounts import API, EvalAccounts
from evaluation.checks import FOOD_CHECKS, References
from evaluation.questions import Question
from evaluation.runner import ChatOutcome
from models.food import Food
from services.ai_agents.fitness_advisor import FitnessAdvisorAgent
from services.foods.aliases import AMBIGUOUS, COOKED_DISHES
from services.foods.lookup import search_foods

NUTRIENTS = (("energy_kcal", "kcal"), ("protein_g", "protein"), ("fat_g", "lipid"), ("carb_g", "glucid"))


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error_type: str | None = None

    def reset(self) -> None:
        self.calls, self.error_type = [], None


RECORDER = _Recorder()


@contextlib.contextmanager
def instrument_agent() -> Iterator[_Recorder]:
    orig_tool, orig_run = FitnessAdvisorAgent._run_tool, FitnessAdvisorAgent._run

    async def run_tool(self, tools_by_name, call, ctx):
        RECORDER.calls.append({"name": call.get("name", ""), "args": sorted((call.get("args") or {}).keys())})
        return await orig_tool(self, tools_by_name, call, ctx)

    async def run(self, messages, ctx):
        try:
            return await orig_run(self, messages, ctx)
        except Exception as exc:
            RECORDER.error_type = type(exc).__name__
            raise

    FitnessAdvisorAgent._run_tool, FitnessAdvisorAgent._run = run_tool, run
    try:
        yield RECORDER
    finally:
        FitnessAdvisorAgent._run_tool, FitnessAdvisorAgent._run = orig_tool, orig_run


def app_client() -> AsyncClient:
    from main import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://eval", timeout=120)


class InProcessChat:
    def __init__(self, client: AsyncClient, accounts: EvalAccounts) -> None:
        self.client, self.accounts = client, accounts

    async def __call__(self, q: Question) -> ChatOutcome:
        RECORDER.reset()
        res = await self.client.post(f"{API}/chat", json={"message": q.cau_hoi},
                                     headers=self.accounts.headers(q.account))
        body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        error = RECORDER.error_type
        if res.status_code != 200 and error is None and res.status_code == 504:
            error = "Timeout"
        return ChatOutcome(http_status=res.status_code, reply=body.get("reply", "") if res.status_code == 200 else "",
                           sources=body.get("sources", []) if res.status_code == 200 else [],
                           calls=list(RECORDER.calls), error_type=error)


def _values(foods: list) -> list[tuple[str, float]]:
    return [(f"{f.name_vi} {label}", getattr(f, attr)) for f in foods for attr, label in NUTRIENTS
            if getattr(f, attr) is not None]


async def load_references(client: AsyncClient, accounts: EvalAccounts) -> References:
    refs = References()
    for account in accounts.user_ids:
        h = accounts.headers(account)
        refs.metrics[account] = (await client.get(f"{API}/profile/metrics", headers=h)).json()
        refs.summary[account] = (await client.get(f"{API}/meals/summary", headers=h)).json()
    avocado_butter = [c for m in AMBIGUOUS["bơ"] for c in m.codes]
    rice = list(COOKED_DISHES["cơm"].codes)
    codes = {c for c, *_ in FOOD_CHECKS.values()} | set(avocado_butter) | set(rice)
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Food).where(Food.code.in_(codes)))).scalars().all()
        refs.foods = {f.code: f for f in rows}
        suggestions = [m.food for m in await search_foods(db, "ức gà", limit=10)]
    refs.substitutes = {
        "C04": _values(suggestions),
        "C06": _values([refs.foods[c] for c in avocado_butter if c in refs.foods]),
        "C09": _values([refs.foods[c] for c in rice if c in refs.foods]),
    }
    return refs


async def retrieve_top_k(question: str, k: int) -> list[dict]:
    from services.rag_service import query_knowledge
    return await asyncio.to_thread(query_knowledge, question, k)
