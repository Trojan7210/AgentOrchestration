import logging

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.api.middleware import AuthMiddleware


def build_client(handler, *, raise_server_exceptions=True):
    app = Starlette(
        routes=[Route("/api/v2/tasks", handler, methods=["GET", "OPTIONS"])]
    )
    app.add_middleware(AuthMiddleware)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_cors_preflight_short_circuits_without_auth_or_handler(caplog):
    calls = {"count": 0}

    async def handler(request):
        calls["count"] += 1
        return PlainTextResponse("handler reached")

    client = build_client(handler)

    with caplog.at_level(logging.INFO, logger="src.api.middleware"):
        response = client.options(
            "/api/v2/tasks",
            headers={
                "Origin": "https://agent.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 204
    assert calls["count"] == 0
    assert response.headers["access-control-allow-credentials"] == "true"
    assert (
        response.headers["access-control-allow-origin"]
        == "https://agent.example"
    )
    assert response.headers["access-control-allow-methods"] == "POST"
    assert (
        response.headers["access-control-allow-headers"]
        == "authorization,content-type"
    )
    assert response.headers["x-auth-result"] == "preflight"
    assert "authorization" not in caplog.text.lower()


def test_real_options_request_without_preflight_headers_requires_auth():
    calls = {"count": 0}

    async def handler(request):
        calls["count"] += 1
        return PlainTextResponse("handler reached")

    client = build_client(handler)

    response = client.options("/api/v2/tasks")

    assert response.status_code == 401
    assert response.text == "Unauthorized"
    assert response.headers["x-auth-result"] == "rejected"
    assert calls["count"] == 0


def test_rejected_real_cors_request_keeps_cors_headers():
    calls = {"count": 0}

    async def handler(request):
        calls["count"] += 1
        return PlainTextResponse("handler reached")

    client = build_client(handler)

    response = client.get(
        "/api/v2/tasks",
        headers={"Origin": "https://agent.example"},
    )

    assert response.status_code == 401
    assert calls["count"] == 0
    assert (
        response.headers["access-control-allow-origin"]
        == "https://agent.example"
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["x-auth-result"] == "rejected"


def test_authenticated_request_reaches_handler_without_leaking_token_headers():
    async def handler(request):
        assert request.scope["state"]["auth_result"] == "authenticated"
        return PlainTextResponse("ok")

    client = build_client(handler)

    response = client.get(
        "/api/v2/tasks",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 200
    assert response.text == "ok"
    assert response.headers["x-auth-result"] == "authenticated"
    assert "secret-token" not in str(response.headers)


def test_exception_path_clears_request_local_auth_state():
    captured_state = []

    async def handler(request):
        captured_state.append(request.scope["state"])
        raise RuntimeError("boom")

    client = build_client(handler, raise_server_exceptions=False)

    response = client.get(
        "/api/v2/tasks",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 500
    assert captured_state
    assert "auth_result" not in captured_state[0]
