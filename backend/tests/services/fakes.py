import asyncio
import json
from typing import Any

from app.services.push import DeliveryResult, SubscriptionInfo


class FakePushSender:
    def __init__(self, *results: DeliveryResult, default: DeliveryResult = DeliveryResult.DELIVERED, delay: float = 0):
        self.results = list(results)
        self.default = default
        self.delay = delay
        self.calls: list[tuple[SubscriptionInfo, dict[str, Any]]] = []

    async def __call__(self, subscription: SubscriptionInfo, payload: str) -> DeliveryResult:
        self.calls.append((subscription, json.loads(payload)))
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.results.pop(0) if self.results else self.default
