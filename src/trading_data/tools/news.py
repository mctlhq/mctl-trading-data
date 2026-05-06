from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from ..cache import async_ttl_cache

CRYPTOCOMPARE_URL = "https://min-api.cryptocompare.com/data/v2/news/"
TTL_SEC = 300

LangType = Literal["EN", "PT", "ES", "TR", "FR", "JP", "RU", "DE", "IT", "KO", "ZH"]
SortType = Literal["latest", "popular"]


@async_ttl_cache(maxsize=64, ttl=TTL_SEC)
async def _fetch(
    api_key: str,
    categories: tuple[str, ...],
    exclude_categories: tuple[str, ...],
    lang: str,
    sort_order: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "lang": lang,
        "sortOrder": sort_order,
        "categories": ",".join(categories) if categories else None,
        "excludeCategories": ",".join(exclude_categories) if exclude_categories else None,
    }
    params = {k: v for k, v in params.items() if v is not None}
    headers = {"Authorization": f"Apikey {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(CRYPTOCOMPARE_URL, params=params, headers=headers)
        r.raise_for_status()
        return r.json()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _published_iso(unix_seconds: int) -> str:
    return datetime.fromtimestamp(unix_seconds, tz=UTC).isoformat()


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [t for t in value.split("|") if t]


def make_news_recent(api_key: str):
    async def news_recent(
        categories: list[str] | None = None,
        exclude_categories: list[str] | None = None,
        hours_back: float = 2.0,
        max: int = 20,
        lang: LangType = "EN",
        sort_order: SortType = "latest",
    ) -> dict[str, Any]:
        """Recent crypto news from CryptoCompare News (free tier).

        `categories` is matched server-side against CryptoCompare's category
        taxonomy (e.g. "ETH", "BTC", "Trading", "Mining"). Pass `["ETH"]` to
        get the same scope as the previous CryptoPanic `currencies=["ETH"]`.
        `exclude_categories` defaults to `["Sponsored"]` — promo posts that
        should never reach the news_score gate.

        `hours_back` is applied client-side after the upstream response,
        because CryptoCompare returns the latest items globally and does not
        accept a time-window filter.
        """
        if not api_key:
            return {"error": {"code": "no_api_key", "message": "NEWS_API_KEY not configured"}}
        cats = tuple(c.strip() for c in (categories or ["ETH"]) if c and c.strip())
        excl = tuple(
            c.strip()
            for c in (exclude_categories if exclude_categories is not None else ["Sponsored"])
            if c and c.strip()
        )
        try:
            payload = await _fetch(api_key, cats, excl, lang, sort_order)
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

        if str(payload.get("Type", "")) not in ("100", ""):
            return {
                "error": {
                    "code": "cryptocompare_error",
                    "message": str(payload.get("Message") or "unknown"),
                }
            }

        cutoff_unix = (
            int(datetime.now(UTC).timestamp() - hours_back * 3600) if hours_back else 0
        )
        items: list[dict[str, Any]] = []
        for post in payload.get("Data") or []:
            try:
                published_on = int(post.get("published_on", 0))
            except (TypeError, ValueError):
                continue
            if cutoff_unix and published_on < cutoff_unix:
                continue
            source_info = post.get("source_info") or {}
            items.append(
                {
                    "id": post.get("id"),
                    "title": post.get("title"),
                    "url": post.get("url"),
                    "published_at": _published_iso(published_on),
                    "published_on": published_on,
                    "source": source_info.get("name") or post.get("source"),
                    "categories": _split_pipe(post.get("categories")),
                    "tags": _split_pipe(post.get("tags")),
                    "votes": {
                        "up": int(post.get("upvotes", 0) or 0),
                        "down": int(post.get("downvotes", 0) or 0),
                    },
                    "body_excerpt": (post.get("body") or "")[:400],
                    "image_url": post.get("imageurl"),
                }
            )
            if len(items) >= max:
                break

        return {
            "data": {"items": items, "count": len(items)},
            "meta": {
                "cached_at": _now_iso(),
                "ttl_sec": TTL_SEC,
                "source": "cryptocompare_news_v2",
                "categories": list(cats),
                "exclude_categories": list(excl),
                "hours_back": hours_back,
                "sort_order": sort_order,
                "lang": lang,
            },
        }

    return news_recent
