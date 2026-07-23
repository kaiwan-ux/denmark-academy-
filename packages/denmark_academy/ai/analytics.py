from typing import Any


class AIAnalyticsService:
    def summarize(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        total_tokens = 0
        by_purpose: dict[str, int] = {}
        for event in events:
            usage = event.get("token_usage") or {}
            total_tokens += int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
            purpose = event.get("purpose") or "unknown"
            by_purpose[purpose] = by_purpose.get(purpose, 0) + 1
        return {"events": len(events), "total_tokens": total_tokens, "by_purpose": by_purpose}
