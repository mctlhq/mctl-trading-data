"""Verify the FastAPI app exposes the MCP endpoint exactly at /mcp.

Regression: FastMCP's default `streamable_http_path="/mcp"` compounds with
`api.mount("/mcp", mcp_app)` into the surprise public path /mcp/mcp.
0.2.1 sets `streamable_http_path="/"` so the public path is clean /mcp.
"""

from __future__ import annotations

import os

# Settings must be configured before importing main.
os.environ.setdefault("TRADING_DATA_TOKEN", "test-token")
os.environ.setdefault("NEWS_API_KEY", "x")
os.environ.setdefault("ETHERSCAN_API_KEY", "x")


def _all_paths(routes, prefix: str = "") -> list[str]:
    out: list[str] = []
    for r in routes:
        path = getattr(r, "path", None)
        if path is None:
            continue
        if hasattr(r, "app") and hasattr(r.app, "routes"):
            out.extend(_all_paths(r.app.routes, prefix + path))
        else:
            out.append(prefix + path)
    return out


def test_mcp_endpoint_at_clean_path():
    from trading_data.main import create_app

    app = create_app()
    paths = _all_paths(app.routes)
    # FastMCP exposes /mcp at its sub-app root; we mount the sub-app at
    # FastAPI's "/" so the public path is exactly /mcp (no trailing
    # slash, no /mcp/mcp). Anything else is a regression worth blocking.
    assert "/mcp" in paths, paths
    assert "/mcp/mcp" not in paths, paths
    assert "/mcp/" not in paths, paths


def test_health_routes_present():
    from trading_data.main import create_app

    app = create_app()
    paths = _all_paths(app.routes)
    assert "/healthz" in paths
    assert "/readyz" in paths
