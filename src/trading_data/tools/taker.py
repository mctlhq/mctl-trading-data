from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..ws.buckets import TakerBuckets


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _venue_envelope(venue: str, symbol: str, buckets: TakerBuckets) -> dict[str, Any]:
    snap = buckets.snapshot()
    return {
        "data": {
            "symbol": symbol,
            "buy_vol_base": snap.buy_base,
            "sell_vol_base": snap.sell_base,
            "net_base": snap.net_base,
            "buy_vol_quote": snap.buy_quote,
            "sell_vol_quote": snap.sell_quote,
            "net_quote": snap.net_quote,
            "net_usd_estimate": snap.net_quote,
            "last_close_price": snap.last_price,
            "trade_count": snap.trade_count,
        },
        "meta": {
            "cached_at": _now_iso(),
            "ttl_sec": 0,
            "source": f"{venue}_publictrade_ws",
            "window_age_sec": snap.window_age_sec,
            "window_incomplete": snap.window_incomplete,
            "last_trade_ts_ms": snap.last_ts_ms,
        },
    }


def _agreement(net_a: float, net_b: float, has_a: bool, has_b: bool) -> str:
    if not has_a and not has_b:
        return "all_missing"
    if has_a and not has_b:
        return "bybit_only"
    if has_b and not has_a:
        return "bitget_only"
    if net_a == 0.0 and net_b == 0.0:
        return "both_zero"
    if net_a == 0.0 or net_b == 0.0:
        return "partial_zero"
    if (net_a > 0 and net_b > 0) or (net_a < 0 and net_b < 0):
        return "aligned"
    return "split"


def make_bybit_taker_24h(buckets: dict[str, TakerBuckets]):
    def bybit_taker_24h(symbol: str = "ETHUSDT", category: str = "linear") -> dict[str, Any]:
        """Rolling 24h taker buy/sell volume from Bybit V5 publicTrade WS.

        Returns net taker flow in base + quote (USDT for *USDT pairs).
        """
        sym = symbol.upper()
        b = buckets.get(sym)
        if b is None:
            return {"error": {"code": "symbol_not_subscribed", "message": f"{sym} not in WATCH_SYMBOLS"}}
        return _venue_envelope("bybit_v5", sym, b)

    return bybit_taker_24h


def make_bitget_taker_24h(buckets: dict[str, TakerBuckets]):
    def bitget_taker_24h(symbol: str = "ETHUSDT", productType: str = "USDT-FUTURES") -> dict[str, Any]:
        """Rolling 24h taker buy/sell volume from Bitget V2 trade-channel WS (USDT-FUTURES)."""
        sym = symbol.upper()
        b = buckets.get(sym)
        if b is None:
            return {"error": {"code": "symbol_not_subscribed", "message": f"{sym} not in WATCH_SYMBOLS"}}
        return _venue_envelope("bitget_v2", sym, b)

    return bitget_taker_24h


def make_aggregated_taker_24h(
    bybit_buckets: dict[str, TakerBuckets],
    bitget_buckets: dict[str, TakerBuckets],
):
    def aggregated_taker_24h(symbol: str = "ETHUSDT") -> dict[str, Any]:
        """Per-exchange + total net flow across Bybit + Bitget WS taker streams.

        Returns agreement cascade tag and lists missing/incomplete legs.
        """
        sym = symbol.upper()
        bybit_b = bybit_buckets.get(sym)
        bitget_b = bitget_buckets.get(sym)
        if bybit_b is None and bitget_b is None:
            return {
                "error": {
                    "code": "symbol_not_subscribed",
                    "message": f"{sym} not in WATCH_SYMBOLS for either venue",
                }
            }

        per_exchange: dict[str, Any] = {}
        missing: list[str] = []

        bybit_snap = bybit_b.snapshot() if bybit_b else None
        bitget_snap = bitget_b.snapshot() if bitget_b else None

        # window_incomplete legs are excluded from agreement to avoid noise
        bybit_usable = bybit_snap is not None and not bybit_snap.window_incomplete
        bitget_usable = bitget_snap is not None and not bitget_snap.window_incomplete

        if bybit_snap:
            per_exchange["bybit"] = {
                "net_quote": bybit_snap.net_quote,
                "last_price": bybit_snap.last_price,
                "window_age_sec": bybit_snap.window_age_sec,
                "window_incomplete": bybit_snap.window_incomplete,
            }
            if not bybit_usable:
                missing.append("bybit_window_incomplete")
        else:
            missing.append("bybit_unreachable")

        if bitget_snap:
            per_exchange["bitget"] = {
                "net_quote": bitget_snap.net_quote,
                "last_price": bitget_snap.last_price,
                "window_age_sec": bitget_snap.window_age_sec,
                "window_incomplete": bitget_snap.window_incomplete,
            }
            if not bitget_usable:
                missing.append("bitget_window_incomplete")
        else:
            missing.append("bitget_unreachable")

        net_bybit = bybit_snap.net_quote if bybit_snap else 0.0
        net_bitget = bitget_snap.net_quote if bitget_snap else 0.0
        agreement = _agreement(net_bybit, net_bitget, bybit_usable, bitget_usable)

        # total only includes usable legs
        total = 0.0
        if bybit_usable:
            total += net_bybit
        if bitget_usable:
            total += net_bitget

        return {
            "data": {
                "symbol": sym,
                "per_exchange": per_exchange,
                "total_net_quote": total,
                "total_net_usd_estimate": total,
                "agreement": agreement,
                "missing": missing,
            },
            "meta": {
                "cached_at": _now_iso(),
                "ttl_sec": 0,
                "source": "bybit_v5+bitget_v2_publictrade_ws",
            },
        }

    return aggregated_taker_24h
