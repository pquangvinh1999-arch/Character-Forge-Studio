"""Real-time event hub supporting both Server-Sent Events (SSE) and WebSockets."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict, deque
from typing import Any, AsyncIterator


class EventHub:
    """Manage per-project event history and live async subscribers for SSE and WebSockets."""

    def __init__(self, max_history: int = 200) -> None:
        self.max_history = max_history
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=self.max_history))
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def publish(self, project_id: str, event: dict[str, Any]) -> None:
        """Record an event in history and push it to all active async queues for project_id."""
        self._history[project_id].append(event)
        queues = list(self._subscribers.get(project_id, ()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def get_history(self, project_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(project_id, ()))

    def subscribe(self, project_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[project_id].add(q)
        return q

    def unsubscribe(self, project_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[project_id].discard(q)

    async def sse_stream(
        self,
        project_id: str,
        *,
        replay_history: bool = True,
        once: bool = False,
    ) -> AsyncIterator[str]:
        """Yield Server-Sent Events formatted lines for a project."""
        q = self.subscribe(project_id)
        try:
            if replay_history:
                for past_event in self.get_history(project_id):
                    data = json.dumps(past_event, ensure_ascii=False)
                    yield f"event: {past_event.get('type', 'message')}\ndata: {data}\n\n"
            if once:
                return
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    data = json.dumps(event, ensure_ascii=False)
                    yield f"event: {event.get('type', 'message')}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self.unsubscribe(project_id, q)
