import json

from trading_data.ws.bitget import parse_bitget_message
from trading_data.ws.buckets import HOUR_MS, TakerBuckets
from trading_data.ws.bybit import parse_bybit_message


def test_bybit_publictrade_message():
    msg = {
        "topic": "publicTrade.ETHUSDT",
        "type": "snapshot",
        "ts": 1_700_000_000_000,
        "data": [
            {"T": 1_700_000_000_000, "s": "ETHUSDT", "S": "Buy", "v": "0.5", "p": "2000.0"},
            {"T": 1_700_000_000_500, "s": "ETHUSDT", "S": "Sell", "v": "0.25", "p": "2001.0"},
        ],
    }
    buckets = {"ETHUSDT": TakerBuckets(venue="bybit", start_ms=0)}
    n = parse_bybit_message(json.dumps(msg), buckets)
    assert n == 2
    snap = buckets["ETHUSDT"].snapshot(now_ms=1_700_000_000_500 + 10)
    assert snap.buy_base == 0.5
    assert snap.sell_base == 0.25
    assert snap.last_price == 2001.0


def test_bybit_unknown_topic_ignored():
    msg = {"topic": "orderbook.50.ETHUSDT", "data": []}
    buckets = {"ETHUSDT": TakerBuckets(venue="bybit", start_ms=0)}
    assert parse_bybit_message(json.dumps(msg), buckets) == 0


def test_bybit_unknown_symbol_ignored():
    msg = {"topic": "publicTrade.BTCUSDT", "data": [{"T": 1, "S": "Buy", "v": "1", "p": "100"}]}
    buckets = {"ETHUSDT": TakerBuckets(venue="bybit", start_ms=0)}
    assert parse_bybit_message(json.dumps(msg), buckets) == 0


def test_bybit_malformed_json_ignored():
    buckets = {"ETHUSDT": TakerBuckets(venue="bybit", start_ms=0)}
    assert parse_bybit_message("not json", buckets) == 0


def test_bybit_bytes_input():
    msg = {
        "topic": "publicTrade.ETHUSDT",
        "data": [{"T": HOUR_MS, "S": "Buy", "v": "1", "p": "100"}],
    }
    buckets = {"ETHUSDT": TakerBuckets(venue="bybit", start_ms=0)}
    assert parse_bybit_message(json.dumps(msg).encode("utf-8"), buckets) == 1


def test_bitget_trade_message():
    msg = {
        "action": "snapshot",
        "arg": {"instType": "USDT-FUTURES", "channel": "trade", "instId": "ETHUSDT"},
        "data": [
            {"ts": "1700000000000", "price": "2000.5", "size": "0.01", "side": "buy", "tradeId": "1"},
            {"ts": "1700000000500", "price": "2001.0", "size": "0.02", "side": "sell", "tradeId": "2"},
        ],
    }
    buckets = {"ETHUSDT": TakerBuckets(venue="bitget", start_ms=0)}
    n = parse_bitget_message(json.dumps(msg), buckets)
    assert n == 2
    snap = buckets["ETHUSDT"].snapshot(now_ms=1_700_000_000_500 + 10)
    assert snap.buy_base == 0.01
    assert snap.sell_base == 0.02
    assert snap.last_price == 2001.0


def test_bitget_pong_string_ignored():
    buckets = {"ETHUSDT": TakerBuckets(venue="bitget", start_ms=0)}
    assert parse_bitget_message("pong", buckets) == 0


def test_bitget_unknown_channel_ignored():
    msg = {"arg": {"channel": "ticker", "instId": "ETHUSDT"}, "data": [{}]}
    buckets = {"ETHUSDT": TakerBuckets(venue="bitget", start_ms=0)}
    assert parse_bitget_message(json.dumps(msg), buckets) == 0
