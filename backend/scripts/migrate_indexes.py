"""One-shot migration: add missing indexes to existing SQLite DB.

Re-runnable. Reads the same DATABASE_URL the app uses and issues
``CREATE INDEX IF NOT EXISTS`` for every column in ``app.models`` that the
ORM currently declares as ``index=True`` but the live DB doesn't have.

Run from the backend directory:

    python -m scripts.migrate_indexes

or:

    python backend/scripts/migrate_indexes.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow execution from repo root or backend dir.
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import inspect, text  # noqa: E402

from app.db.session import engine  # noqa: E402
import app.models  # noqa: F401, E402  - register models on Base


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("migrate_indexes")


def _existing_indexes(conn, table: str) -> set[tuple[str, ...]]:
    """Return a set of column-tuples that already have an index."""
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return set()
    out: set[tuple[str, ...]] = set()
    for idx in inspector.get_indexes(table):
        cols = tuple(idx.get("column_names") or ())
        if cols:
            out.add(cols)
    # Primary keys count as covering indexes for their column.
    pk_cols = inspector.get_pk_constraint(table).get("constrained_columns") or []
    if pk_cols:
        out.add(tuple(pk_cols))
    return out


def main() -> int:
    from app.db.session import Base

    created = 0
    skipped = 0
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspect(conn).has_table(table.name):
                logger.warning("table %s missing — run init_db first", table.name)
                continue
            covered = _existing_indexes(conn, table.name)
            for col in table.columns:
                if not col.index:
                    continue
                key = (col.name,)
                if key in covered:
                    skipped += 1
                    continue
                idx_name = f"ix_{table.name}_{col.name}"
                stmt = text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table.name}" ("{col.name}")')
                logger.info("creating %s on %s(%s)", idx_name, table.name, col.name)
                conn.execute(stmt)
                created += 1
                covered.add(key)
    logger.info("done — created %d, already-present %d", created, skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
