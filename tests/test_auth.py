from fastapi import FastAPI
from fastapi.testclient import TestClient

from trading_data.auth import BearerAuthMiddleware

TOKEN = "test-token-supersecret"


def make_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(BearerAuthMiddleware, token=TOKEN, protected_prefix="/mcp")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/mcp/ping")
    def mcp_ping():
        return {"pong": True}

    return app


def test_healthz_open():
    client = TestClient(make_test_app())
    r = client.get("/healthz")
    assert r.status_code == 200


def test_mcp_no_header_401():
    client = TestClient(make_test_app())
    r = client.get("/mcp/ping")
    assert r.status_code == 401


def test_mcp_wrong_token_401():
    client = TestClient(make_test_app())
    r = client.get("/mcp/ping", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_mcp_correct_token_200():
    client = TestClient(make_test_app())
    r = client.get("/mcp/ping", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json() == {"pong": True}


def test_misconfigured_no_token_500():
    app = FastAPI()
    app.add_middleware(BearerAuthMiddleware, token="", protected_prefix="/mcp")

    @app.get("/mcp/x")
    def x():
        return {}

    r = TestClient(app).get("/mcp/x", headers={"Authorization": "Bearer anything"})
    assert r.status_code == 500
