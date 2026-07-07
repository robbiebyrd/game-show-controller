import logging
from typing import Any, Callable, Awaitable

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, event_type: type, handler: Callable[[Any], Awaitable[None]]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Any) -> None:
        # Central log of every event on the bus. CountdownTick fires ~4x/sec,
        # so it stays at DEBUG to avoid flooding the default INFO log.
        if type(event).__name__ == "CountdownTick":
            log.debug("event %s", event)
        else:
            log.info("event %s", event)
        for handler in self._subscribers.get(type(event), []):
            try:
                await handler(event)
            except Exception:
                log.exception("Handler %s raised for event %s", handler, type(event).__name__)
