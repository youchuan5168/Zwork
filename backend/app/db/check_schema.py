"""只读检查：接管旧数据库之前，核对它与当前模型的差异。"""

import argparse
import importlib
from sqlalchemy import Index, MetaData, create_mock_engine, inspect
from sqlalchemy.schema import CreateIndex, CreateTable
from alembic.operations import Operations
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlmodel import SQLModel
from app import models  # noqa: F401
from app.core.config import settings
from app.db.session import build_engine


def baseline_metadata():
    """从冻结迁移收集原始类型与索引；mock 引擎绝不连接数据库。"""
    metadata = MetaData()

    def collect(statement, *args, **kwargs):
        if isinstance(statement, CreateTable):
            statement.element.to_metadata(metadata)
        elif isinstance(statement, CreateIndex):
            index = statement.element
            table = metadata.tables[index.table.key]
            Index(
                index.name, *(table.c[column.name] for column in index.columns), unique=index.unique
            )

    mock = create_mock_engine("mysql+pymysql://", collect)
    with Operations.context(MigrationContext.configure(mock)):
        importlib.import_module("migrations.versions.0001_baseline").upgrade()
    return metadata


def equivalent_mysql_restrict_differences(differences, innodb_tables):
    """仅消除 InnoDB 默认限制规则的成对表示差异，保留真正结构差异。"""

    def signature(constraint):
        def restrictive(action):
            return action is None or action.upper() in {"RESTRICT", "NO ACTION"}

        table = constraint.table
        if (table.schema, table.name) not in innodb_tables:
            return None
        if not restrictive(constraint.ondelete) or not restrictive(constraint.onupdate):
            return None
        return (
            table.schema,
            table.name,
            tuple(column.name for column in constraint.columns),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.deferrable,
            constraint.initially,
            constraint.match,
            tuple(sorted(constraint.dialect_kwargs.items())),
        )

    ignored = set()
    for index, difference in enumerate(differences):
        if not isinstance(difference, tuple) or difference[0] != "remove_fk":
            continue
        expected_signature = signature(difference[1])
        if expected_signature is None:
            continue
        for other, addition in enumerate(differences):
            if other in ignored or not isinstance(addition, tuple) or addition[0] != "add_fk":
                continue
            if signature(addition[1]) == expected_signature:
                ignored.update((index, other))
                break
    return [difference for index, difference in enumerate(differences) if index not in ignored]


def main():
    parser = argparse.ArgumentParser(description="只读核对数据库结构")
    parser.add_argument("--revision", choices=["head", "0001"], default="head")
    parser.add_argument("--database", help="指定 MySQL 数据库；覆盖 DATABASE_URL，连接账号沿用配置")
    arguments = parser.parse_args()
    revision = arguments.revision
    metadata = SQLModel.metadata
    if revision == "0001":
        metadata = baseline_metadata()
    config = settings
    if arguments.database:
        config = settings.model_copy(update={"database_url": None, "mysql_db": arguments.database})
    engine = build_engine(config)
    print(f"连接目标: {engine.url.host or '本地'} {engine.url.port or ''} {engine.url.database}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            differences = compare_metadata(context, metadata)
            if connection.dialect.name == "mysql":
                inspector = inspect(connection)
                innodb_tables = set()
                for difference in differences:
                    if isinstance(difference, tuple) and difference[0] == "remove_fk":
                        table = difference[1].table
                        options = inspector.get_table_options(table.name, schema=table.schema)
                        if options.get("mysql_engine", "").lower() == "innodb":
                            innodb_tables.add((table.schema, table.name))
                differences = equivalent_mysql_restrict_differences(differences, innodb_tables)
        if differences:
            for difference in differences:
                print(difference)
            raise SystemExit("结构不匹配：请先人工审查，禁止直接 stamp")
        print(
            f"结构与 {revision} 匹配（本命令没有写入数据库）；仅 0001 核对通过的旧库可备份后 stamp 0001"
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
