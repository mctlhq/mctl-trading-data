from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from ..cache import async_ttl_cache

ETHERSCAN_URL = "https://api.etherscan.io/api"
GAS_TTL_SEC = 15
WHALE_TTL_SEC = 120

VITALIK_ADDRESS = "0xab5801a7d398351b8be11c439e05c5b3259aec9b"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@async_ttl_cache(maxsize=4, ttl=GAS_TTL_SEC)
async def _fetch_gas(api_key: str) -> dict[str, Any]:
    params = {"module": "gastracker", "action": "gasoracle", "apikey": api_key}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(ETHERSCAN_URL, params=params)
        r.raise_for_status()
        return r.json()


@async_ttl_cache(maxsize=64, ttl=WHALE_TTL_SEC)
async def _fetch_txlist(api_key: str, address: str, limit: int) -> dict[str, Any]:
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": min(max(limit, 1), 100),
        "sort": "desc",
        "apikey": api_key,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(ETHERSCAN_URL, params=params)
        r.raise_for_status()
        return r.json()


def make_etherscan_gas_snapshot(api_key: str):
    async def etherscan_gas_snapshot() -> dict[str, Any]:
        """Current ETH gas oracle (safeLow / standard / fast in gwei)."""
        if not api_key:
            return {"error": {"code": "no_api_key", "message": "ETHERSCAN_API_KEY not configured"}}
        try:
            payload = await _fetch_gas(api_key)
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

        if str(payload.get("status")) != "1":
            return {
                "error": {
                    "code": "etherscan_error",
                    "message": str(payload.get("message") or payload.get("result") or "unknown"),
                }
            }
        result = payload.get("result") or {}
        try:
            data = {
                "safe_gwei": float(result.get("SafeGasPrice", 0)),
                "standard_gwei": float(result.get("ProposeGasPrice", 0)),
                "fast_gwei": float(result.get("FastGasPrice", 0)),
                "suggest_base_fee_gwei": float(result.get("suggestBaseFee", 0)),
                "gas_used_ratio": result.get("gasUsedRatio"),
            }
        except (TypeError, ValueError):
            return {"error": {"code": "parse_error", "message": "unexpected gas response shape"}}

        return {
            "data": data,
            "meta": {
                "cached_at": _now_iso(),
                "ttl_sec": GAS_TTL_SEC,
                "source": "etherscan_gastracker_gasoracle",
            },
        }

    return etherscan_gas_snapshot


def make_etherscan_whale_transactions(api_key: str):
    async def etherscan_whale_transactions(
        address: str = VITALIK_ADDRESS,
        min_value_eth: float = 100.0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Recent transactions for an address with ETH value above the threshold (default 100 ETH)."""
        if not api_key:
            return {"error": {"code": "no_api_key", "message": "ETHERSCAN_API_KEY not configured"}}
        try:
            payload = await _fetch_txlist(api_key, address.lower(), 100)
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

        if str(payload.get("status")) != "1":
            msg = str(payload.get("message") or "")
            if "No transactions found" in msg:
                return {
                    "data": {"address": address, "items": [], "count": 0},
                    "meta": {
                        "cached_at": _now_iso(),
                        "ttl_sec": WHALE_TTL_SEC,
                        "source": "etherscan_account_txlist",
                    },
                }
            return {
                "error": {
                    "code": "etherscan_error",
                    "message": msg or "unknown",
                }
            }

        threshold_wei = int(min_value_eth * 10**18)
        items: list[dict[str, Any]] = []
        for tx in payload.get("result") or []:
            try:
                value_wei = int(tx.get("value", "0"))
            except (TypeError, ValueError):
                continue
            if value_wei < threshold_wei:
                continue
            items.append(
                {
                    "hash": tx.get("hash"),
                    "from": tx.get("from"),
                    "to": tx.get("to"),
                    "value_eth": value_wei / 10**18,
                    "block_number": tx.get("blockNumber"),
                    "timestamp": tx.get("timeStamp"),
                    "gas_used": tx.get("gasUsed"),
                }
            )
            if len(items) >= limit:
                break

        return {
            "data": {"address": address, "items": items, "count": len(items)},
            "meta": {
                "cached_at": _now_iso(),
                "ttl_sec": WHALE_TTL_SEC,
                "source": "etherscan_account_txlist",
                "min_value_eth": min_value_eth,
            },
        }

    return etherscan_whale_transactions
