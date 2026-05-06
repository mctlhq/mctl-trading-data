from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

from .auth import BearerAuthMiddleware
from .config import settings
from .tools.news import make_news_recent
from .tools.onchain import make_etherscan_gas_snapshot, make_etherscan_whale_transactions
from .tools.taker import (
    make_aggregated_taker_24h,
    make_bitget_taker_24h,
    make_bybit_taker_24h,
)
from .ws.bitget import BitgetWorker
from .ws.buckets import TakerBuckets
from .ws.bybit import BybitWorker

log = logging.getLogger("trading_data")


def _build_state() -> dict:
    symbols = settings.symbols or ["ETHUSDT"]
    bybit_buckets = {s: TakerBuckets(venue="bybit") for s in symbols}
    bitget_buckets = {s: TakerBuckets(venue="bitget") for s in symbols}
    bybit_worker = BybitWorker(settings.bybit_ws_url, symbols, bybit_buckets)
    bitget_worker = BitgetWorker(settings.bitget_ws_url, symbols, bitget_buckets)
    return {
        "symbols": symbols,
        "bybit_buckets": bybit_buckets,
        "bitget_buckets": bitget_buckets,
        "bybit_worker": bybit_worker,
        "bitget_worker": bitget_worker,
    }


def _register_tools(mcp: FastMCP, state: dict) -> None:
    bybit_taker_24h = make_bybit_taker_24h(state["bybit_buckets"])
    bitget_taker_24h = make_bitget_taker_24h(state["bitget_buckets"])
    aggregated_taker_24h = make_aggregated_taker_24h(state["bybit_buckets"], state["bitget_buckets"])
    news_recent = make_news_recent(settings.news_api_key)
    etherscan_gas_snapshot = make_etherscan_gas_snapshot(settings.etherscan_api_key)
    etherscan_whale_transactions = make_etherscan_whale_transactions(settings.etherscan_api_key)

    mcp.tool(name="bybit_taker_24h")(bybit_taker_24h)
    mcp.tool(name="bitget_taker_24h")(bitget_taker_24h)
    mcp.tool(name="aggregated_taker_24h")(aggregated_taker_24h)
    mcp.tool(name="news_recent")(news_recent)
    mcp.tool(name="etherscan_gas_snapshot")(etherscan_gas_snapshot)
    mcp.tool(name="etherscan_whale_transactions")(etherscan_whale_transactions)


def create_app() -> FastAPI:
    logging.basicConfig(level=settings.log_level.upper())

    mcp = FastMCP("trading-data")
    state = _build_state()
    _register_tools(mcp, state)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state["bybit_worker"].start()
        state["bitget_worker"].start()
        async with mcp.session_manager.run():
            try:
                yield
            finally:
                await state["bybit_worker"].stop()
                await state["bitget_worker"].stop()

    api = FastAPI(title="mctl-trading-data", lifespan=lifespan)
    api.add_middleware(BearerAuthMiddleware, token=settings.trading_data_token, protected_prefix="/mcp")

    @api.get("/healthz")
    def healthz() -> JSONResponse:
        return JSONResponse({"ok": True})

    @api.get("/readyz")
    def readyz() -> JSONResponse:
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        venues_ready: dict[str, dict] = {}
        ready = True
        for name, buckets_map in (
            ("bybit", state["bybit_buckets"]),
            ("bitget", state["bitget_buckets"]),
        ):
            symbols_status = {}
            venue_ready = False
            for sym, b in buckets_map.items():
                age = b.liveness_age_sec(now_ms)
                fresh = age <= 60
                symbols_status[sym] = {
                    "liveness_age_sec": None if age == float("inf") else round(age, 2),
                    "fresh": fresh,
                }
                if fresh:
                    venue_ready = True
            venues_ready[name] = {"ready": venue_ready, "symbols": symbols_status}
            if not venue_ready:
                ready = False

        return JSONResponse({"ready": ready, "venues": venues_ready}, status_code=200 if ready else 503)

    api.mount("/mcp", mcp_app)

    api.state.runtime = state  # for tests / introspection
    return api


app = create_app()
