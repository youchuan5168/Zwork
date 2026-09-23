from alembic import context
from sqlmodel import SQLModel
from app import models  # noqa: F401
from app.core.config import settings
from app.db.session import build_engine

target_metadata = SQLModel.metadata


def run_migrations_offline():
    context.configure(
        url=settings.db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        if (
            connection.dialect.name == "sqlite"
            and connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
        ):
            raise RuntimeError(
                "SQLite batch 迁移需要调用者在事务前关闭 foreign_keys，完成后核对并恢复；应用运行必须启用"
            )
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            sqlite = connection.dialect.name == "sqlite"
            if sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.commit()
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
            if sqlite:
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("迁移后 SQLite 外键检查失败")
                connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
