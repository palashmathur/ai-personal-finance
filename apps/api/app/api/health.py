# Health check router.
# A single GET /health endpoint that confirms both the server and the database are alive.
# This is the first thing you check when a deployment looks broken.

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

# Tag name displays on swagger UI
router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Ping the server and the database in one call.

    Runs a lightweight SELECT 1 against SQLite to confirm the DB file is reachable
    and the connection is healthy. If the DB call throws for any reason, FastAPI
    surfaces it as a 500 — which is correct behaviour (the server is up but broken).

    Returns {"status": "ok", "db": "connected"} on success.
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


class _EchoRequest(BaseModel):
    # A strictly typed field so sending the wrong type produces a RequestValidationError.
    value: int


@router.post("/health/echo", include_in_schema=False)
def echo(payload: _EchoRequest):
    """
    Test scaffolding only — used by test_health.py to trigger RequestValidationError.
    Sending {"value": "not-a-number"} produces a 422 with our custom error shape.
    Excluded from the OpenAPI docs (include_in_schema=False).
    Will be removed in PF-42.
    """
    return payload
