"""
Cost Guard — Bảo vệ budget LLM.

Đếm tokens mỗi ngày, block khi vượt budget.
Trong production: lưu trong Redis/DB, không phải in-memory.
"""
import time
import logging
from dataclasses import dataclass, field
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

PRICE_PER_1K_INPUT = 0.00015   # GPT-4o-mini: $0.15/1M input tokens
PRICE_PER_1K_OUTPUT = 0.0006   # GPT-4o-mini: $0.60/1M output tokens


@dataclass
class UsageRecord:
    user_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    day: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))

    @property
    def total_cost_usd(self) -> float:
        return round(
            (self.input_tokens / 1000) * PRICE_PER_1K_INPUT
            + (self.output_tokens / 1000) * PRICE_PER_1K_OUTPUT,
            6,
        )


class CostGuard:
    def __init__(
        self,
        daily_budget_usd: float = 10.0,
        warn_at_pct: float = 0.8,
    ):
        self.daily_budget_usd = daily_budget_usd
        self.warn_at_pct = warn_at_pct
        self._records: dict[str, UsageRecord] = {}
        self._global_cost = 0.0
        self._global_day = time.strftime("%Y-%m-%d")

    def _get_record(self, user_id: str) -> UsageRecord:
        today = time.strftime("%Y-%m-%d")
        if today != self._global_day:
            self._records.clear()
            self._global_cost = 0.0
            self._global_day = today
        record = self._records.get(user_id)
        if not record or record.day != today:
            self._records[user_id] = UsageRecord(user_id=user_id, day=today)
        return self._records[user_id]

    def check_budget(self, user_id: str) -> None:
        """Raise 402 nếu vượt budget, 503 nếu vượt global budget."""
        record = self._get_record(user_id)
        if self._global_cost >= self.daily_budget_usd:
            logger.critical(f"Global budget exceeded: ${self._global_cost:.4f}")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable due to budget limits. Try again tomorrow.",
            )
        if record.total_cost_usd >= self.daily_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Daily budget exceeded",
                    "used_usd": record.total_cost_usd,
                    "budget_usd": self.daily_budget_usd,
                    "resets_at": "midnight UTC",
                },
            )
        if record.total_cost_usd >= self.daily_budget_usd * self.warn_at_pct:
            logger.warning(
                f"User {user_id} at {record.total_cost_usd / self.daily_budget_usd * 100:.0f}% budget"
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        """Ghi nhận usage sau khi gọi LLM."""
        record = self._get_record(user_id)
        record.input_tokens += input_tokens
        record.output_tokens += output_tokens
        record.request_count += 1
        cost = (input_tokens / 1000 * PRICE_PER_1K_INPUT
                + output_tokens / 1000 * PRICE_PER_1K_OUTPUT)
        self._global_cost += cost
        logger.info(f"Usage: user={user_id} cost=${record.total_cost_usd:.4f}/{self.daily_budget_usd}")
        return record

    def get_usage(self, user_id: str) -> dict:
        record = self._get_record(user_id)
        return {
            "user_id": user_id,
            "date": record.day,
            "requests": record.request_count,
            "cost_usd": record.total_cost_usd,
            "budget_usd": self.daily_budget_usd,
            "budget_used_pct": round(record.total_cost_usd / self.daily_budget_usd * 100, 1),
        }


cost_guard = CostGuard(daily_budget_usd=settings.daily_budget_usd)
