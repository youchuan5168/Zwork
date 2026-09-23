import re
from contextlib import contextmanager
import pymysql
from sqlalchemy import event, inspect
from fastapi import Request
from sqlmodel import Session, SQLModel, create_engine
from app.core.config import Settings


def ensure_database(config: Settings):
    if not re.fullmatch(r"[A-Za-z0-9_]+", config.mysql_db):
        raise ValueError("MYSQL_DB 仅支持字母、数字和下划线")
    connection = pymysql.connect(
        host=config.mysql_host,
        port=config.mysql_port,
        user=config.mysql_user,
        password=config.mysql_password,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.mysql_db}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


def build_engine(config: Settings):
    engine = create_engine(config.db_url, pool_pre_ping=True, pool_recycle=3600)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enforce_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


def initialize_database(config: Settings):
    if config.database_url is None and config.auto_create_database:
        ensure_database(config)
    engine = build_engine(config)
    try:
        inspector = inspect(engine)
        existing = set(inspector.get_table_names())
        if not config.auto_create_tables and not {
            "users",
            "companies",
            "applications",
            "application_stages",
            "schedules",
            "auth_throttles",
        }.issubset(existing):
            raise RuntimeError("数据库安全结构不完整，请先完成 Alembic upgrade head")
        for table, column in (
            ("users", "token_version"),
            ("users", "is_active"),
            ("users", "bootstrap_slot"),
            ("companies", "user_id"),
            ("applications", "user_id"),
            ("application_stages", "user_id"),
            ("schedules", "user_id"),
        ):
            if table in existing and column not in {
                c["name"] for c in inspector.get_columns(table)
            }:
                raise RuntimeError(
                    "发现旧版数据库结构：请先备份并按照 docs/security-foundation.md 迁移到 0002"
                )
        if config.agent_enabled and "agent_runs" in existing and "skill" not in {
            column["name"] for column in inspector.get_columns("agent_runs")
        }:
            raise RuntimeError("Agent 技能需要数据库迁移 0004：请先备份并执行 Alembic upgrade head")
        profile_tables = {
            "career_documents", "career_document_versions",
            "career_document_chunks", "career_memories",
        }
        if "users" in existing and not profile_tables.issubset(existing):
            raise RuntimeError("画像与文档需要数据库迁移 0005：请先备份并执行 Alembic upgrade head")
        if "career_documents" in existing and "is_default" not in {
            column["name"] for column in inspector.get_columns("career_documents")
        }:
            raise RuntimeError("简历中心需要数据库迁移 0012：请先备份并执行 Alembic upgrade head")
        if "users" in existing and not {"career_tasks", "career_reviews"}.issubset(existing):
            raise RuntimeError("Career Agent 需要数据库迁移 0006：请先备份并执行 Alembic upgrade head")
        if "users" in existing and not {"recruitment_preferences", "recruitment_jobs"}.issubset(existing):
            raise RuntimeError("平台招聘需要数据库迁移 0008：请先备份并执行 Alembic upgrade head")
        if config.auto_create_tables:
            from app import models  # noqa: F401

            SQLModel.metadata.create_all(engine)
        if config.agent_enabled:
            inspector = inspect(engine)
            if not {"agent_runs", "agent_events"}.issubset(set(inspector.get_table_names())):
                raise RuntimeError("启用 Agent 前请备份并执行 Alembic upgrade head")
            if "skill" not in {column["name"] for column in inspector.get_columns("agent_runs")}:
                raise RuntimeError("Agent 技能需要数据库迁移 0004：请先备份并执行 Alembic upgrade head")
        return engine
    except Exception:
        engine.dispose()
        raise


@contextmanager
def transaction(session: Session):
    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
