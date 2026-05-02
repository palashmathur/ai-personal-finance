# Tests for the health endpoint and the custom exception handlers wired in main.py.
#
# TestClient is FastAPI's synchronous test client built on httpx.
# It spins up the app in-process — no real server, no ports — so tests are fast.
# Think of it like MockMvc in Spring Boot: real request/response lifecycle, no network.

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    """
    The happy path: server is running and the DB is reachable.
    Expects exactly {"status": "ok", "db": "connected"} — no extra keys.
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "connected"}


def test_http_exception_handler_shape():
    """
    Hitting a route that doesn't exist triggers FastAPI's built-in 404 HTTPException.
    Our custom handler should intercept it and return {"detail": ..., "code": "not_found"}
    instead of FastAPI's default {"detail": "Not Found"}.

    This verifies the handler is wired correctly for all future routes too —
    any HTTPException they raise will follow the same shape.
    """
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert body["code"] == "not_found"


def test_validation_error_handler_shape():
    """
    Sending a wrong type to a typed endpoint triggers RequestValidationError.
    POST /health/echo expects {"value": <int>}. Sending a string for value
    should produce 422 with {"detail": [...], "code": "validation_error"}.

    This verifies our validation handler fires correctly. The same shape will
    apply to every future router endpoint that uses Pydantic request bodies.
    """
    response = client.post("/health/echo", json={"value": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["detail"], list)  # Pydantic error list, one entry per failing field
    assert len(body["detail"]) > 0
