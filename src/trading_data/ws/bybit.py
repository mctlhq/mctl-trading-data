from __future__ import annotations

import asyncio
import json
import logging
import random

import websockets

from .buckets import TakerBuckets

log = logging.getLogger(__name__)


def parse_bybit_message(raw: str | bytes, buckets_by_symbol: dict[str, TakerBuckets]) -> int:
    """Parse a Bybit V5 publicTrade.<symbol> message; append trades to matching bucket.

    Returns the number of trades applied.
    """
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    topic = msg.get("topic", "")
    if not topic.startswith("publicTrade."):
        return 0
    symbol = topic.split(".", 1)[1].upper()
    bucket = buckets_by_symbol.get(symbol)
    if bucket is None:
        return 0

    data = msg.get("data") or []
    applied = 0
    for trade in data:
        try:
            ts_ms = int(trade["T"])
            side = str(trade["S"])
            base = float(trade["v"])
            price = float(trade["p"])
        except (KeyError, ValueError, TypeError):
            continue
        bucket.append(ts_ms, side, base, price)
        applied += 1
    return applied


class BybitWorker:
    def __init__(
        self,
        url: str,
        symbols: list[str],
        buckets_by_symbol: dict[str, TakerBuckets],
    ) -> None:
        self._url = url
        self._symbols = [s.upper() for s in symbols]
        self._buckets = buckets_by_symbol
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="bybit-ws")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    max_size=2**20,
                ) as ws:
                    await self._subscribe(ws)
                    backoff = 1.0
                    log.info("bybit ws connected url=%s symbols=%s", self._url, self._symbols)
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        parse_bybit_message(raw, self._buckets)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("bybit ws disconnect: %s; reconnecting in %.1fs", exc, backoff)
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff + random.uniform(0, backoff / 2))
            backoff = min(60.0, backoff * 2)

    async def _subscribe(self, ws) -> None:
        topics = [f"publicTrade.{s}" for s in self._symbols]
        await ws.send(json.dumps({"op": "subscribe", "args": topics}))
