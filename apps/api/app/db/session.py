# Everything related to connecting to the SQLite database lives here.
# This is the single source of truth for how the app talks to the DB.
# Think of it as your Spring DataSource + EntityManagerFactory rolled into one file.

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Resolve the absolute path to data/finance.db, starting from this file's location.
# We go 4 levels up (db/ → app/ → api/ → apps/ → project root) then into data/.
# Using an absolute path means it works correctly no matter where you run uvicorn from.
_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "finance.db"

# Make sure the data/ directory exists before SQLite tries to create the file inside it.
# parents=True means it also creates any missing parent directories (like `data/`).
# exist_ok=True means it won't throw an error if the folder is already there.
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# The SQLAlchemy connection string for SQLite.
# Format: sqlite:///absolute/path/to/file.db
# This is what tells SQLAlchemy which database to connect to.
DATABASE_URL = f"sqlite:///{_DB_PATH}"

# The engine is the connection factory for the whole app — create it once, reuse forever.
# It manages a pool of database connections under the hood.
# `check_same_thread=False` is required for SQLite when used with FastAPI,
# because FastAPI handles requests across multiple threads but SQLite's default
# setting would reject connections from any thread other than the one that created them.
engine: Engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    """
    Fires every time SQLAlchemy opens a fresh connection to SQLite.

    SQLite PRAGMAs are per-connection settings — they're not stored in the DB file,
    so we need to re-apply them on every new connection.

    WAL mode: Allows reads and writes to happen at the same time without locking
    the entire file. Without this, a write would block every read until it finishes.

    foreign_keys=ON: SQLite has foreign key support built-in, but it's OFF by default
    for historical reasons. Without this, deleting a category that transactions reference
    would silently succeed — which would corrupt your data.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# SessionLocal is the factory that creates individual database sessions.
# Each request gets its own session (via get_db below), does its work, then closes.
# Think of it like EntityManagerFactory in Spring — you call it to get an EntityManager.
# autoflush=False: don't auto-send pending changes to the DB mid-transaction.
# autocommit=False: we'll commit explicitly, so we stay in full control of transactions.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """
    A FastAPI dependency that hands a fresh database session to each request handler
    and guarantees it gets closed when the request is done — even if an error occurs.

    Usage in a route:
        @app.get("/something")
        def my_route(db: Session = Depends(get_db)):
            ...

    The `yield` keyword is what makes this a dependency with cleanup.
    FastAPI runs everything before `yield` before calling your route,
    then everything after `yield` (the finally block) once the response is sent.
    Think of it like a @RequestScoped EntityManager with automatic cleanup in Spring.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Always close the session — releases the connection back to the pool.
        db.close()
