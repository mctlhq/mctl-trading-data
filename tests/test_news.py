from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from trading_data.tools import news as news_module


def _payload(items: list[dict]) -> dict:
    return {
        "Type": 100,
        "Message": "News list successfully returned",
        "Data": items,
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    news_module._fetch.cache.clear()
    yield
    news_module._fetch.cache.clear()


@pytest.mark.asyncio
async def test_no_api_key_returns_error():
    fn = news_module.make_news_recent("")
    out = await fn(categories=["ETH"])
    assert "error" in out
    assert out["error"]["code"] == "no_api_key"


@pytest.mark.asyncio
async def test_normalises_cryptocompare_payload():
    now_unix = int(datetime.now(UTC).timestamp())
    items = [
        {
            "id": "1",
            "guid": "g1",
            "published_on": now_unix - 60,  # 1 minute ago
            "title": "ETF approved",
            "url": "https://example.com/etf",
            "source": "coindesk",
            "body": "long body that should be excerpted",
            "tags": "ETH|Ethereum|ETF",
            "categories": "ETH|Markets",
            "upvotes": "5",
            "downvotes": "0",
            "imageurl": "https://img.example/1.png",
            "source_info": {"name": "CoinDesk", "lang": "EN"},
        },
        {
            "id": "2",
            "published_on": now_unix - 4 * 3600,  # 4 hours ago — outside 2h window
            "title": "old news",
            "url": "https://example.com/old",
            "source": "x",
            "body": "...",
            "tags": "ETH",
            "categories": "ETH",
            "upvotes": "0",
            "downvotes": "0",
            "source_info": {"name": "X"},
        },
    ]
    fn = news_module.make_news_recent("test-key")
    with patch.object(news_module, "_fetch", return_value=_payload(items)) as fake:
        # _fetch is decorated with @async_ttl_cache; patch object to bypass.
        async def passthrough(*args, **kwargs):
            return _payload(items)

        fake.side_effect = passthrough
        out = await fn(categories=["ETH"], hours_back=2.0, max=20)

    assert "data" in out
    assert out["data"]["count"] == 1
    item = out["data"]["items"][0]
    assert item["id"] == "1"
    assert item["title"] == "ETF approved"
    assert item["source"] == "CoinDesk"
    assert item["categories"] == ["ETH", "Markets"]
    assert item["tags"] == ["ETH", "Ethereum", "ETF"]
    assert item["votes"] == {"up": 5, "down": 0}
    assert item["body_excerpt"].startswith("long body")
    assert item["published_at"].endswith("+00:00")
    assert out["meta"]["source"] == "cryptocompare_news_v2"
    assert out["meta"]["categories"] == ["ETH"]
    assert out["meta"]["exclude_categories"] == ["Sponsored"]


@pytest.mark.asyncio
async def test_cryptocompare_error_response():
    bad = {"Type": 99, "Message": "rate limit exceeded", "Data": []}
    fn = news_module.make_news_recent("test-key")

    async def passthrough(*args, **kwargs):
        return bad

    with patch.object(news_module, "_fetch", side_effect=passthrough):
        out = await fn()
    assert "error" in out
    assert out["error"]["code"] == "cryptocompare_error"
    assert "rate limit" in out["error"]["message"]


@pytest.mark.asyncio
async def test_max_truncation():
    now_unix = int(datetime.now(UTC).timestamp())
    items = [
        {
            "id": str(i),
            "published_on": now_unix - 60,
            "title": f"item {i}",
            "url": f"https://example.com/{i}",
            "source": "s",
            "body": "",
            "tags": "ETH",
            "categories": "ETH",
            "upvotes": "0",
            "downvotes": "0",
            "source_info": {"name": "S"},
        }
        for i in range(50)
    ]
    fn = news_module.make_news_recent("test-key")

    async def passthrough(*args, **kwargs):
        return _payload(items)

    with patch.object(news_module, "_fetch", side_effect=passthrough):
        out = await fn(max=5, hours_back=2.0)
    assert out["data"]["count"] == 5
