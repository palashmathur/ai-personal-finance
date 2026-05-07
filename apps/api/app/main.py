# Entry point of the FastAPI application.
# uvicorn imports this file and looks for the `app` object to serve.
# Think of this as the Spring Boot @SpringBootApplication class —
# it's where the app is wired together: middleware, exception handlers, routers.

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers.accounts_router import router as accounts_router
from app.routers.categories_router import router as categories_router
from app.routers.health_router import router as health_router
from app.routers.instruments_router import router as instruments_router
from app.routers.transactions_router import router as transactions_router

app = FastAPI(title="AI Personal Finance API", version="0.1.0")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Allow all origins in development so the Vite frontend (localhost:5173) and
# Postman can reach the API without a browser CORS error.
# Will be locked down to the production domain in PF-42.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
# Override FastAPI's default error responses so every error — whether it's a
# 404, a 409 conflict, or a bad request body — comes back in one consistent
# shape: {"detail": "...", "code": "..."}.
#
# "detail" is the human-readable message; "code" is the machine-readable slug
# that the frontend can switch on without parsing the detail string.


def _code_for(status_code: int) -> str:
    """
    Map an HTTP status code to a short machine-readable slug.
    Any status not in the map falls back to "http_{status_code}" (e.g. "http_418").
    This means future routers get a sensible code automatically just by raising
    HTTPException — no manual code string needed at each call site.
    """
    _map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable_entity",
        500: "internal_server_error",
    }
    return _map.get(status_code, f"http_{status_code}")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """
    Catches every HTTP error raised anywhere in the app and returns the standard shape.

    We register against StarletteHTTPException (not FastAPI's HTTPException) because
    FastAPI is built on Starlette, and route-not-found 404s are raised by Starlette's
    routing layer using its own exception class. FastAPI's HTTPException inherits from
    it, so this single handler covers both — unknown routes AND explicit raises inside
    route functions.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": _code_for(exc.status_code)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """
    Catches Pydantic validation failures (wrong types, missing required fields)
    and returns them in the same standard shape as HTTPException errors.

    `exc.errors()` returns a list of dicts — one per failing field — with the
    field location, the failing value, and the error message. We pass this list
    as `detail` so the frontend knows exactly which fields failed and why.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "code": "validation_error"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(transactions_router)
app.include_router(instruments_router)
