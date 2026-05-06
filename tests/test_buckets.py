from trading_data.ws.buckets import DAY_MS, HOUR_MS, TakerBuckets


def test_append_buy_and_sell_accumulates():
    b = TakerBuckets(venue="test", start_ms=0)
    now_ms = HOUR_MS  # 1h after start
    b.append(now_ms, "Buy", base=2.0, price=100.0)
    b.append(now_ms, "Sell", base=1.0, price=101.0)
    snap = b.snapshot(now_ms=now_ms + 1)

    assert snap.buy_base == 2.0
    assert snap.sell_base == 1.0
    assert snap.net_base == 1.0
    assert snap.buy_quote == 200.0
    assert snap.sell_quote == 101.0
    assert snap.net_quote == 99.0
    assert snap.last_price == 101.0
    assert snap.trade_count == 2


def test_evict_drops_buckets_older_than_24h():
    b = TakerBuckets(venue="test", start_ms=0)
    old_ts = 0
    fresh_ts = DAY_MS + HOUR_MS  # 25h after start
    b.append(old_ts, "Buy", base=10.0, price=1000.0)
    b.append(fresh_ts, "Buy", base=2.0, price=100.0)

    snap = b.snapshot(now_ms=fresh_ts + 1)
    assert snap.buy_base == 2.0  # the 10.0 entry was evicted (>24h old)
    assert snap.last_price == 100.0


def test_window_incomplete_for_first_hour():
    b = TakerBuckets(venue="test", start_ms=0)
    snap = b.snapshot(now_ms=30 * 60 * 1000)  # 30 min after start
    assert snap.window_incomplete is True
    assert snap.window_age_sec == 30 * 60


def test_window_complete_after_first_hour():
    b = TakerBuckets(venue="test", start_ms=0)
    snap = b.snapshot(now_ms=2 * HOUR_MS)
    assert snap.window_incomplete is False
    assert snap.window_age_sec == 2 * 3600


def test_window_age_capped_at_24h():
    b = TakerBuckets(venue="test", start_ms=0)
    snap = b.snapshot(now_ms=72 * HOUR_MS)
    assert snap.window_age_sec == DAY_MS // 1000


def test_invalid_input_ignored():
    b = TakerBuckets(venue="test", start_ms=0)
    b.append(0, "Buy", base=0.0, price=100.0)  # zero size
    b.append(0, "Sell", base=1.0, price=0.0)  # zero price
    b.append(0, "unknown", base=1.0, price=1.0)  # bad side
    snap = b.snapshot(now_ms=0)
    assert snap.trade_count == 0


def test_liveness_age_sec_with_no_messages():
    b = TakerBuckets(venue="test", start_ms=0)
    assert b.liveness_age_sec(now_ms=1000) == float("inf")


def test_liveness_age_sec_after_message():
    b = TakerBuckets(venue="test", start_ms=0)
    b.append(10_000, "Buy", base=1.0, price=100.0)
    assert b.liveness_age_sec(now_ms=15_000) == 5.0
