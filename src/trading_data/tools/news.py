from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from ..cache import async_ttl_cache

CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"
TTL_SEC = 300


@async_ttl_cache(maxsize=64, ttl=TTL_SEC)
async def _fetch(auth_token: str, currencies: tuple[str, ...], filter_: str, public: bool) -> dict[str, Any]:
    params: dict[str, Any] = {
        "auth_token": auth_token,
        "currencies": ",".join(currencies) if currencies else None,
        "filter": filter_ if filter_ != "all" else None,
        "public": "true" if public else None,
    }
    params = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(CRYPTOPANIC_URL, params=params)
        r.raise_for_status()
        return r.json()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _within_hours(published_at: str, hours_back: float, now_utc: datetime) -> bool:
    try:
        ts = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    delta = (now_utc - ts).total_seconds() / 3600.0
    return delta <= hours_back


def make_cryptopanic_recent_news(api_key: str):
    async def cryptopanic_recent_news(
        currencies: list[str] | None = None,
        filter: Literal["rising", "hot", "important", "saved", "lol", "all"] = "rising",
        hours_back: float = 2.0,
        max: int = 20,
    ) -> dict[str, Any]:
        """Recent news posts from CryptoPanic (free tier)."""
        if not api_key:
            return {"error": {"code": "no_api_key", "message": "CRYPTOPANIC_API_KEY not configured"}}
        try:
            cur_tuple = tuple(currencies or ["ETH"])
            payload = await _fetch(api_key, cur_tuple, filter, True)
        except httpx.HTTPStatusError as exc:
            return {
                "error": {
                    "code": "upstream_error",
                    "message": str(exc),
                    "upstream_status": exc.response.status_code,
                }
            }
        except (httpx.HTTPError, TimeoutError) as exc:
            return {"error": {"code": "upstream_unreachable", "message": str(exc)}}

        now_utc = datetime.now(UTC)
        items: list[dict[str, Any]] = []
        for post in (payload.get("results") or [])[: max * 3]:
            published_at = str(post.get("published_at") or "")
            if hours_back and not _within_hours(published_at, hours_back, now_utc):
                continue
            votes = post.get("votes") or {}
            source = (post.get("source") or {}).get("title", "")
            items.append(
                {
                    "title": post.get("title"),
                    "url": post.get("url"),
                    "published_at": published_at,
                    "votes": {
                        "positive": votes.get("positive", 0),
                        "negative": votes.get("negative", 0),
                        "important": votes.get("important", 0),
                    },
                    "source": source,
                    "currencies": [c.get("code") for c in (post.get("currencies") or []) if c.get("code")],
                }
            )
            if len(items) >= max:
                break

        return {
            "data": {"items": items, "count": len(items)},
            "meta": {
                "cached_at": _now_iso(),
                "ttl_sec": TTL_SEC,
                "source": "cryptopanic_v1_posts",
                "filter": filter,
                "hours_back": hours_back,
            },
        }

    return cryptopanic_recent_news
