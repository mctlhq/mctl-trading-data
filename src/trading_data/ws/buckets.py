from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

HOUR_MS = 60 * 60 * 1000
DAY_MS = 24 * HOUR_MS


@dataclass
class HourBucket:
    hour_ms: int
    buy_base: float = 0.0
    sell_base: float = 0.0
    buy_quote: float = 0.0
    sell_quote: float = 0.0
    last_price: float = 0.0
    last_ts_ms: int = 0
    trade_count: int = 0


@dataclass
class Snapshot:
    buy_base: float
    sell_base: float
    buy_quote: float
    sell_quote: float
    net_base: float
    net_quote: float
    last_price: float
    last_ts_ms: int
    trade_count: int
    window_age_sec: int
    window_incomplete: bool


@dataclass
class TakerBuckets:
    venue: str
    start_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    last_message_ms: int = 0
    _buckets: dict[int, HourBucket] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, ts_ms: int, side: str, base: float, price: float) -> None:
        if base <= 0 or price <= 0:
            return
        side_l = side.lower()
        if side_l not in ("buy", "sell"):
            return
        hour = (ts_ms // HOUR_MS) * HOUR_MS
        quote = base * price
        with self._lock:
            bucket = self._buckets.get(hour)
            if bucket is None:
                bucket = HourBucket(hour_ms=hour)
                self._buckets[hour] = bucket
            if side_l == "buy":
                bucket.buy_base += base
                bucket.buy_quote += quote
            else:
                bucket.sell_base += base
                bucket.sell_quote += quote
            if ts_ms >= bucket.last_ts_ms:
                bucket.last_ts_ms = ts_ms
                bucket.last_price = price
            bucket.trade_count += 1
            self.last_message_ms = max(self.last_message_ms, ts_ms)

    def _evict(self, now_ms: int) -> None:
        cutoff = now_ms - DAY_MS
        stale = [h for h in self._buckets if h < cutoff]
        for h in stale:
            del self._buckets[h]

    def snapshot(self, now_ms: int | None = None) -> Snapshot:
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        with self._lock:
            self._evict(now_ms)
            buy_base = sum(b.buy_base for b in self._buckets.values())
            sell_base = sum(b.sell_base for b in self._buckets.values())
            buy_quote = sum(b.buy_quote for b in self._buckets.values())
            sell_quote = sum(b.sell_quote for b in self._buckets.values())
            trade_count = sum(b.trade_count for b in self._buckets.values())
            latest = max(self._buckets.values(), key=lambda b: b.last_ts_ms, default=None)
            last_price = latest.last_price if latest else 0.0
            last_ts_ms = latest.last_ts_ms if latest else 0

        age_sec = max(0, (now_ms - self.start_ms) // 1000)
        window_age_sec = min(DAY_MS // 1000, age_sec)
        window_incomplete = age_sec < 3600

        return Snapshot(
            buy_base=buy_base,
            sell_base=sell_base,
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            net_base=buy_base - sell_base,
            net_quote=buy_quote - sell_quote,
            last_price=last_price,
            last_ts_ms=last_ts_ms,
            trade_count=trade_count,
            window_age_sec=window_age_sec,
            window_incomplete=window_incomplete,
        )

    def liveness_age_sec(self, now_ms: int | None = None) -> float:
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        if self.last_message_ms == 0:
            return float("inf")
        return (now_ms - self.last_message_ms) / 1000.0
