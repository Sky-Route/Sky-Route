"""Bus de eventos interno en memoria para comunicación asíncrona entre módulos (API-05, API-09, API-13)."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

TZ_COLOMBIA = timezone(timedelta(hours=-5))


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = defaultdict(list)
        self.published_events: list[dict[str, Any]] = []

    def subscribe(self, topic: str, handler: Callable[[dict[str, Any]], None]) -> None:
        handler_name = getattr(handler, "__qualname__", str(handler))
        existing_names = {getattr(h, "__qualname__", str(h)) for h in self._subscribers[topic]}
        if handler_name not in existing_names:
            self._subscribers[topic].append(handler)

    def publish(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "topico": topic,
            "fechaPublicacion": datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds"),
            "payload": payload,
        }
        self.published_events.append(event)
        for handler in list(self._subscribers.get(topic, [])):
            handler(payload)
        return event

    def clear_history(self) -> None:
        self.published_events.clear()


event_bus = EventBus()
