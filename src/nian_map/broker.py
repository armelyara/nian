"""In-process pub/sub used to fan out new feed items to SSE clients.

One producer, N subscribers, bounded queues: a slow client drops its own
oldest messages instead of growing memory. To run several workers or
instances, swap this class for a Redis pub/sub with the same interface.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Iterator


class TooManySubscribers(Exception):
    pass


class Broker:
    def __init__(self, max_subscribers: int = 200, queue_size: int = 100):
        self._subs: set[asyncio.Queue[str]] = set()
        self._max = max_subscribers
        self._qsize = queue_size

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    @contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[str]]:
        if len(self._subs) >= self._max:
            raise TooManySubscribers()
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=self._qsize)
        self._subs.add(q)
        try:
            yield q
        finally:
            self._subs.discard(q)

    def publish(self, message: str) -> None:
        for q in list(self._subs):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(message)
