"""共享数据库上的原子计数；多 worker 不依赖进程内内存。"""

import hashlib
import hmac
import math
import time

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.errors import BusinessError
from app.db.session import transaction
from app.models import AuthThrottle


def consume(session, config, scope: str, identity: str, limit: int, *, now=None, window_seconds=None):
    timestamp = int(time.time() if now is None else now)
    window = window_seconds or config.auth_rate_window_seconds
    key = hmac.new(
        config.jwt_secret.encode(), (scope + ":" + identity).encode(), hashlib.sha256
    ).hexdigest()
    table = AuthThrottle.__table__
    stale = table.c.window_started <= timestamp - window
    values = {"key": key, "window_started": timestamp, "attempts": 1}
    updated = {
        "attempts": case((stale, 1), else_=table.c.attempts + 1),
        "window_started": case((stale, timestamp), else_=table.c.window_started),
    }
    dialect = session.get_bind().dialect.name
    if dialect == "mysql":
        statement = (
            mysql_insert(table)
            .values(**values)
            .on_duplicate_key_update(
                # attempts must be evaluated before window_started changes on MySQL.
                [(name, updated[name]) for name in ("attempts", "window_started")]
            )
        )
    elif dialect == "sqlite":
        statement = (
            sqlite_insert(table)
            .values(**values)
            .on_conflict_do_update(index_elements=["key"], set_=updated)
        )
    else:
        raise RuntimeError("认证限流暂只支持 MySQL 和 SQLite")
    with transaction(session):
        session.execute(delete(table).where(table.c.window_started < timestamp - 86400))
        session.execute(statement)
        row = session.execute(
            select(table.c.attempts, table.c.window_started).where(table.c.key == key)
        ).one()
    if row.attempts > limit:
        retry = max(1, math.ceil(row.window_started + window - timestamp))
        raise BusinessError("尝试次数过多，请稍后重试", 429, headers={"Retry-After": str(retry)})
