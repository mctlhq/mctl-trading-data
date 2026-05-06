import time

from trading_data.tools.taker import (
    make_aggregated_taker_24h,
    make_bitget_taker_24h,
    make_bybit_taker_24h,
)
from trading_data.ws.buckets import HOUR_MS, TakerBuckets


def _seed_buckets(venue: str, buy: float, sell: float, price: float = 2000.0) -> TakerBuckets:
    """Seed mature (non-incomplete) buckets aligned to current time."""
    now_ms = int(time.time() * 1000)
    # start the worker 2h ago so window is mature; trades 30m ago so they're inside the 24h window
    start_ms = now_ms - 2 * HOUR_MS
    trade_ts = now_ms - 30 * 60 * 1000
    b = TakerBuckets(venue=venue, start_ms=start_ms)
    if buy > 0:
        b.append(trade_ts, "buy", buy, price)
    if sell > 0:
        b.append(trade_ts, "sell", sell, price)
    return b


def test_bybit_taker_24h_returns_envelope():
    buckets = {"ETHUSDT": _seed_buckets("bybit", buy=10.0, sell=5.0)}
    fn = make_bybit_taker_24h(buckets)
    out = fn(symbol="ETHUSDT")
    assert "data" in out and "meta" in out
    assert out["data"]["buy_vol_base"] == 10.0
    assert out["data"]["sell_vol_base"] == 5.0
    assert out["data"]["net_base"] == 5.0
    assert out["data"]["net_quote"] == 10000.0  # (10-5) * 2000
    assert out["meta"]["source"].startswith("bybit_v5")


def test_bybit_taker_24h_unknown_symbol_error():
    fn = make_bybit_taker_24h({})
    out = fn(symbol="NOPE")
    assert "error" in out
    assert out["error"]["code"] == "symbol_not_subscribed"


def test_bitget_taker_24h_returns_envelope():
    buckets = {"ETHUSDT": _seed_buckets("bitget", buy=3.0, sell=4.0)}
    fn = make_bitget_taker_24h(buckets)
    out = fn(symbol="ETHUSDT")
    assert out["data"]["net_base"] == -1.0
    assert out["meta"]["source"].startswith("bitget_v2")


def test_aggregated_aligned_when_same_sign():
    bybit = {"ETHUSDT": _seed_buckets("bybit", buy=10.0, sell=2.0)}
    bitget = {"ETHUSDT": _seed_buckets("bitget", buy=8.0, sell=1.0)}
    out = make_aggregated_taker_24h(bybit, bitget)(symbol="ETHUSDT")
    assert out["data"]["agreement"] == "aligned"
    assert out["data"]["per_exchange"]["bybit"]["net_quote"] > 0
    assert out["data"]["per_exchange"]["bitget"]["net_quote"] > 0
    assert out["data"]["total_net_quote"] > 0
    assert out["data"]["missing"] == []


def test_aggregated_split_when_opposite_signs():
    bybit = {"ETHUSDT": _seed_buckets("bybit", buy=10.0, sell=2.0)}
    bitget = {"ETHUSDT": _seed_buckets("bitget", buy=1.0, sell=8.0)}
    out = make_aggregated_taker_24h(bybit, bitget)(symbol="ETHUSDT")
    assert out["data"]["agreement"] == "split"


def test_aggregated_window_incomplete_excluded():
    bybit = {"ETHUSDT": _seed_buckets("bybit", buy=10.0, sell=2.0)}
    # bitget bucket fresh — window_incomplete=True
    bitget = {"ETHUSDT": TakerBuckets(venue="bitget")}  # uses real time → fresh
    out = make_aggregated_taker_24h(bybit, bitget)(symbol="ETHUSDT")
    assert "bitget_window_incomplete" in out["data"]["missing"]
    assert out["data"]["agreement"] == "bybit_only"


def test_aggregated_unknown_symbol_error():
    out = make_aggregated_taker_24h({}, {})(symbol="NOPE")
    assert "error" in out
