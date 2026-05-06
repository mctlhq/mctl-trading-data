# mctl-trading-data

MCP service exposing market intelligence tools to `labs-openclaw` (and any other authorized MCP client) over **streamable HTTP** with Bearer token auth.

## Tool surface

| Tool | Purpose |
|---|---|
| `bybit_taker_24h` | Rolling 24h taker buy/sell volume from Bybit V5 public WS (`publicTrade.<symbol>`). |
| `bitget_taker_24h` | Rolling 24h taker buy/sell volume from Bitget V2 public WS (`trade` channel, USDT-FUTURES). |
| `aggregated_taker_24h` | Per-exchange + total net USD flow with N-leg agreement cascade. |
| `news_recent` | Recent crypto news from CryptoCompare News v2 (free tier). Vendor-neutral name; swap upstreams without changing the tool surface. |
| `etherscan_gas_snapshot` | Current safeLow/standard/fast gwei. |
| `etherscan_whale_transactions` | Filtered large-value transactions for an address. |

All tools return the normalized envelope `{"data": ..., "meta": {"cached_at", "ttl_sec", "source", ...}}`. Errors return `{"error": {"code", "message", "upstream_status"}}`.

## Architecture

- **WS workers** maintain rolling 24×1h taker buckets in process memory (no Redis). Cold-start window ramp is up to 24h; tools surface `meta.window_age_sec` and `meta.window_incomplete` so consumers can downweight fresh-window legs.
- **REST tools** wrap CryptoPanic + Etherscan via `httpx` with `cachetools.TTLCache`.
- **Auth** is a static Bearer token (`TRADING_DATA_TOKEN`). Constant-time compare. No OAuth.
- **Health probes**: `/healthz` = process alive; `/readyz` = both WS workers connected within last 30s.

`replicaCount: 1` is a HARD INVARIANT — buckets are in-process. Scaling requires Redis + WS leader election first.

## Deployment

Deployed via mctl-gitops to the `labs` namespace. Service: `labs-trading-data.labs.svc.cluster.local:8080`. NetworkPolicy restricts ingress to `labs-openclaw` pods only.

See `mctl-gitops/platform-gitops/services/labs/trading-data/values.yaml` for the chart values.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export TRADING_DATA_TOKEN=$(openssl rand -base64 48)
export NEWS_API_KEY=...        # CryptoCompare News API key (free tier)
export ETHERSCAN_API_KEY=...
uvicorn trading_data.main:app --host 0.0.0.0 --port 8080
```

Run tests:
```bash
pytest -q
```

## Versioning

Semver, no `v` prefix in tags or image tags (per organization convention). `0.1.0` → `ghcr.io/mctlhq/mctl-trading-data:0.1.0`.
