from typing import Any, Callable, Awaitable


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, event_type: type, handler: Callable[[Any], Awaitable[None]]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Any) -> None:
        for handler in self._subscribers.get(type(event), []):
            await handler(event)
