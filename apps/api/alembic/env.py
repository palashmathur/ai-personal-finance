# This file is the brain of Alembic's migration system.
# Every time you run any `alembic` command (upgrade, downgrade, revision, etc.),
# Alembic executes this script. It sets up the DB connection and tells Alembic
# where to find your models so it can compare them against the real schema.

from logging.config import fileConfig

from sqlalchemy import engine_from_config, event, pool

from alembic import context

# The Alembic config object — reads values from alembic.ini.
config = context.config

# Wire up Python's standard logging using the [loggers] section in alembic.ini.
# This is what makes Alembic print "Running upgrade ... -> ..." to your terminal.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base (which has seen all 6 ORM models) and pull the DB URL from session.py.
# These imports must come after the config setup above — hence the noqa comments
# to silence the "import not at top of file" linter warning.
from app.db.session import DATABASE_URL  # noqa: E402
from app.models import Base  # noqa: E402

# Override the URL from alembic.ini with the one from session.py.
# This means there's exactly one place in the codebase that defines the DB path —
# session.py. Alembic and the app always point to the same file.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# This is what enables `alembic revision --autogenerate` to work.
# Alembic compares Base.metadata (all the table/column definitions from your ORM models)
# against the actual schema in the DB file, and generates a migration for the diff.
target_metadata = Base.metadata


def _set_pragmas(dbapi_conn, _connection_record):
    """
    Apply the same SQLite PRAGMAs during migrations that the app applies at runtime.
    Without this, foreign key constraints wouldn't be enforced during migration runs —
    which means a migration that violates a FK rule would silently succeed.

    See session.py's `_set_sqlite_pragmas` for a full explanation of each pragma.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def run_migrations_offline() -> None:
    """
    'Offline' mode: generates SQL statements to stdout or a file,
    without actually connecting to the database. Useful if you want
    to review the raw SQL before running it, or run it manually via a DBA.
    We use it with render_as_batch=True so SQLite's lack of ALTER TABLE support
    is handled correctly even in the generated SQL.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite doesn't support ALTER TABLE for adding/dropping constraints.
        # render_as_batch tells Alembic to use the "copy-and-replace" strategy instead:
        # create a new temp table, copy data, drop old, rename new. Transparent to you.
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    'Online' mode: connects to the actual database and runs migrations directly.
    This is what runs when you do `alembic upgrade head` or `alembic downgrade base`.
    """
    # Create an engine just for running migrations (NullPool = no connection pooling,
    # since we only need one connection for the duration of the migration run).
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Apply the same PRAGMAs here that the app applies at runtime.
    event.listen(connectable, "connect", _set_pragmas)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # same reason as offline mode above
        )
        with context.begin_transaction():
            context.run_migrations()


# Alembic calls this script in one of two modes depending on the command.
# `alembic upgrade head` → online. `alembic upgrade head --sql` → offline.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
