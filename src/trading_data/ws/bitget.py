from __future__ import annotations

import asyncio
import json
import logging
import random

import websockets

from .buckets import TakerBuckets

log = logging.getLogger(__name__)


def parse_bitget_message(raw: str | bytes, buckets_by_symbol: dict[str, TakerBuckets]) -> int:
    """Parse a Bitget V2 USDT-FUTURES trade-channel message; append trades to matching bucket."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    if raw == "pong":
        return 0
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    arg = msg.get("arg") or {}
    if arg.get("channel") != "trade":
        return 0
    symbol = str(arg.get("instId", "")).upper()
    bucket = buckets_by_symbol.get(symbol)
    if bucket is None:
        return 0

    data = msg.get("data") or []
    applied = 0
    for trade in data:
        try:
            ts_ms = int(trade["ts"])
            side = str(trade["side"])
            base = float(trade["size"])
            price = float(trade["price"])
        except (KeyError, ValueError, TypeError):
            continue
        bucket.append(ts_ms, side, base, price)
        applied += 1
    return applied


class BitgetWorker:
    def __init__(
        self,
        url: str,
        symbols: list[str],
        buckets_by_symbol: dict[str, TakerBuckets],
        product_type: str = "USDT-FUTURES",
    ) -> None:
        self._url = url
        self._symbols = [s.upper() for s in symbols]
        self._buckets = buckets_by_symbol
        self._product_type = product_type
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="bitget-ws")

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
                    ping_interval=None,
                    close_timeout=5,
                    max_size=2**20,
                ) as ws:
                    await self._subscribe(ws)
                    backoff = 1.0
                    log.info("bitget ws connected url=%s symbols=%s", self._url, self._symbols)
                    ping_task = asyncio.create_task(self._app_ping(ws))
                    try:
                        async for raw in ws:
                            if self._stop.is_set():
                                break
                            if isinstance(raw, bytes):
                                raw = raw.decode("utf-8", errors="ignore")
                            if raw == "pong":
                                continue
                            parse_bitget_message(raw, self._buckets)
                    finally:
                        ping_task.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("bitget ws disconnect: %s; reconnecting in %.1fs", exc, backoff)
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff + random.uniform(0, backoff / 2))
            backoff = min(60.0, backoff * 2)

    async def _subscribe(self, ws) -> None:
        args = [
            {"instType": self._product_type, "channel": "trade", "instId": s}
            for s in self._symbols
        ]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))

    async def _app_ping(self, ws) -> None:
        try:
            while True:
                await asyncio.sleep(20)
                await ws.send("ping")
        except asyncio.CancelledError:
            return
        except Exception:
            return
