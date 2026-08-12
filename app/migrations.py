"""One-shot bootstrap migrations for existing SQLite databases.

The project does not yet use Alembic; this module performs the small ALTER
TABLE the rest of the codebase needs at app startup. It is intentionally
idempotent — running it on a fresh DB where ``Base.metadata.create_all``
already added the columns is a no-op.

When the project moves to Alembic, this module can be retired.
"""

import logging

from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError


logger = logging.getLogger(__name__)


def _add_column_if_missing(
    conn,
    table: str,
    column: str,
    ddl: str,
) -> bool:
    """Run ``ALTER TABLE <table> ADD COLUMN <column> <ddl>`` if the column
    is not already present on ``<table>``. Returns True when an ALTER was
    actually issued.
    """
    existing = conn.exec_driver_sql(
        f"PRAGMA table_info({table})"
    ).fetchall()
    column_names = {row[1] for row in existing}

    if column in column_names:
        logger.info("%s.%s already present, skipping ALTER", table, column)
        return False

    logger.info(
        "Adding %s.%s via ALTER TABLE (one-shot bootstrap)", table, column
    )
    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    return True


def run_task_assignee_migration(engine: Engine) -> bool:
    """Add ``tasks.assignee_id`` if it does not already exist.

    Returns True when an ALTER was actually issued, False otherwise.
    Never raises — logs and moves on so app startup cannot be blocked by
    a migration that turns out unnecessary.
    """

    try:
        with engine.begin() as conn:
            return _add_column_if_missing(
                conn,
                table="tasks",
                column="assignee_id",
                ddl="INTEGER REFERENCES users(id)",
            )

    except OperationalError as exc:
        logger.warning(
            "run_task_assignee_migration failed (non-fatal): %s", exc
        )
        return False
    except Exception as exc:  # pragma: no cover - safety net
        logger.warning(
            "run_task_assignee_migration unexpected error (non-fatal): %s",
            exc,
        )
        return False


def run_user_auth_columns_migration(engine: Engine) -> bool:
    """Add ``users.hashed_password`` / ``is_active`` / ``role`` columns to an
    older SQLite DB that was created before auth was wired in.

    Returns True when at least one ALTER was issued, False if every column
    was already present or the helper bailed.
    Never raises — logs and moves on.
    """

    additions = [
        ("hashed_password", "VARCHAR(200) NOT NULL DEFAULT ''"),
        ("is_active", "BOOLEAN NOT NULL DEFAULT 1"),
        ("role", "VARCHAR(50) NOT NULL DEFAULT 'researcher'"),
    ]

    try:
        altered_any = False
        with engine.begin() as conn:
            for column, ddl in additions:
                if _add_column_if_missing(conn, "users", column, ddl):
                    altered_any = True
        return altered_any

    except OperationalError as exc:
        logger.warning(
            "run_user_auth_columns_migration failed (non-fatal): %s", exc
        )
        return False
    except Exception as exc:  # pragma: no cover - safety net
        logger.warning(
            "run_user_auth_columns_migration unexpected error (non-fatal): %s",
            exc,
        )
        return False


def run_inventory_barcode_migration(engine: Engine) -> bool:
    """Add ``inventory.barcode`` to an existing SQLite DB.

    The barcode column is nullable and unique; older rows get NULL.
    Returns True when an ALTER was actually issued.
    Never raises.
    """
    try:
        with engine.begin() as conn:
            altered = _add_column_if_missing(
                conn,
                table="inventory",
                column="barcode",
                ddl="VARCHAR(100)",
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_inventory_barcode ON inventory (barcode)"
            )
            return altered
    except OperationalError as exc:
        logger.warning(
            "run_inventory_barcode_migration failed (non-fatal): %s", exc
        )
        return False
    except Exception as exc:  # pragma: no cover - safety net
        logger.warning(
            "run_inventory_barcode_migration unexpected error (non-fatal): %s",
            exc,
        )
        return False
