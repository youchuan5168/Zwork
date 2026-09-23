"""Back up configured MySQL, verify 0003 on a new clone, optionally upgrade target.

Generated SQL contains private data. Never print its contents or commit backups.
No existing database is dropped or restored over.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.config import Settings  # noqa: E402


def fingerprint(connection, tables):
    result = {}
    for table in tables:
        digest = hashlib.sha256()
        ordering = "`key`" if table == "auth_throttles" else "id"
        rows = connection.execute(text(f"SELECT * FROM `{table}` ORDER BY {ordering}"))
        count = 0
        for row in rows:
            digest.update(json.dumps(list(row), default=str, ensure_ascii=False).encode())
            digest.update(b"\n")
            count += 1
        result[table] = (count, digest.hexdigest())
    return result


def migrate(engine):
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0003")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003"
        assert {"agent_runs", "agent_events"}.issubset(inspect(connection).get_table_names())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysql-bin", required=True, type=Path)
    parser.add_argument("--upgrade-target", action="store_true")
    args = parser.parse_args()
    url = Settings().db_url
    url = make_url(url) if isinstance(url, str) else url
    if not url.drivername.startswith("mysql") or not re.fullmatch(r"[A-Za-z0-9_]+", url.database or ""):
        raise RuntimeError("Expected a named MySQL database")
    for executable in ("mysqldump.exe", "mysql.exe"):
        if not (args.mysql_bin / executable).is_file():
            raise RuntimeError("Official MySQL CLI missing")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    tables = ["users", "companies", "applications", "application_stages", "schedules", "auth_throttles"]
    with engine.connect() as connection:
        if connection.execute(text("SELECT version_num FROM alembic_version")).scalar() != "0002":
            raise RuntimeError("This verifier requires target revision 0002")
        before = fingerprint(connection, tables)
        charset, collation = connection.execute(text(
            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA "
            "WHERE SCHEMA_NAME=:name"), {"name": url.database}).one()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    backup_dir = BACKEND.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"{url.database}_pre_agent_{stamp}.sql"
    if backup.exists():
        raise RuntimeError("Backup path already exists")
    credentials = os.environ.copy()
    credentials["MYSQL_PWD"] = url.password or ""
    cli = ["--host", url.host or "127.0.0.1", "--port", str(url.port or 3306),
           "--user", url.username or "", "--default-character-set=utf8mb4"]
    dump = subprocess.run([str(args.mysql_bin / "mysqldump.exe"), *cli,
                           "--single-transaction", "--skip-lock-tables", "--no-tablespaces",
                           "--set-gtid-purged=OFF", "--routines", "--events", "--triggers",
                           f"--result-file={backup}", url.database],
                          env=credentials, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if dump.returncode or not backup.exists() or not backup.stat().st_size:
        raise RuntimeError("Backup failed; raw stderr suppressed to protect credentials")
    clone = "agent_verify_" + stamp.lower()
    if not all(re.fullmatch(r"[A-Za-z0-9_]+", item) for item in (clone, charset, collation)):
        raise RuntimeError("Unsafe database metadata")
    with engine.begin() as connection:
        connection.execute(text(f"CREATE DATABASE `{clone}` CHARACTER SET {charset} COLLATE {collation}"))
    # mysql reads the generated dump directly, never a shell command or existing destination.
    with backup.open("rb") as input_file:
        restored = subprocess.run([str(args.mysql_bin / "mysql.exe"), *cli, clone],
                                  stdin=input_file, env=credentials, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE)
    if restored.returncode:
        raise RuntimeError("Clone restore failed; target untouched")
    clone_engine = create_engine(url.set(database=clone))
    try:
        with clone_engine.connect() as connection:
            assert fingerprint(connection, tables) == before, "Restored data mismatch"
        migrate(clone_engine)
        with clone_engine.connect() as connection:
            assert fingerprint(connection, tables) == before, "Clone migration changed business data"
        if args.upgrade_target:
            with engine.connect() as connection:
                assert fingerprint(connection, tables) == before, "Target changed during verification; stop application first"
            migrate(engine)
            with engine.connect() as connection:
                assert fingerprint(connection, tables) == before, "Target business data changed"
        print(json.dumps({"backup": str(backup), "backup_bytes": backup.stat().st_size,
                          "restored_clone": clone, "clone_revision": "0003",
                          "target_revision": "0003" if args.upgrade_target else "0002",
                          "business_data_unchanged": True}, ensure_ascii=False))
    finally:
        clone_engine.dispose()
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"ok": False, "error_type": type(error).__name__,
                          "hint": "Verification stopped; keep backup/clone and inspect locally. No automatic rollback."}))
        sys.exit(1)
