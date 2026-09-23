"""用户数据归属与认证基座；必须在线预检查，拒绝猜测旧数据所有者。"""

from alembic import context, op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
TABLES = ("companies", "applications", "application_stages", "schedules")
NAMES = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def options():
    return {**context.get_x_argument(as_dictionary=True), **context.config.attributes}


def preflight():
    if context.is_offline_mode():
        raise RuntimeError("0002 需要在线核对旧数据归属，不支持离线 SQL；请在独立库验证")
    bind = op.get_bind()
    users = list(bind.execute(sa.text("SELECT id FROM users ORDER BY id")).scalars())
    has_data = any(
        bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in TABLES
    )
    explicit = options().get("legacy_owner_id")
    owner = int(explicit) if explicit is not None else (users[0] if len(users) == 1 else None)
    if explicit is not None and owner not in users:
        raise RuntimeError("legacy_owner_id 必须对应已有用户")
    if has_data and owner is None:
        raise RuntimeError(
            "旧数据无明确归属：只有一个用户时自动回填，否则须指定 -x legacy_owner_id=<id>"
        )
    for table, field, parent in (
        ("applications", "company_id", "companies"),
        ("application_stages", "application_id", "applications"),
        ("schedules", "application_id", "applications"),
    ):
        count = bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} t LEFT JOIN {parent} p ON t.{field}=p.id "
                f"WHERE t.{field} IS NOT NULL AND p.id IS NULL"
            )
        ).scalar()
        if count:
            raise RuntimeError(f"{table} 存在悬空关联，请先修复后再迁移")
    return owner, users


def upgrade():
    owner, users = preflight()  # 必须在任何 MySQL DDL 之前失败。
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("users", sa.Column("bootstrap_slot", sa.Integer(), nullable=True))
    if users:
        op.get_bind().execute(
            sa.text("UPDATE users SET bootstrap_slot=1 WHERE id=:id"), {"id": users[0]}
        )
    op.create_index("ix_users_bootstrap_slot", "users", ["bootstrap_slot"], unique=True)
    for table in TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        if owner is not None:
            op.get_bind().execute(sa.text(f"UPDATE {table} SET user_id=:owner"), {"owner": owner})
    for table in TABLES:
        old_fks = sa.inspect(op.get_bind()).get_foreign_keys(table)
        with op.batch_alter_table(table, naming_convention=NAMES) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(f"fk_{table}_user", "users", ["user_id"], ["id"])
            if table != "companies":
                field, parent = (
                    ("company_id", "companies")
                    if table == "applications"
                    else ("application_id", "applications")
                )
                for fk in old_fks:
                    if fk["constrained_columns"] == [field]:
                        name = fk["name"] or f"fk_{table}_{field}_{parent}"
                        batch.drop_constraint(name, type_="foreignkey")
                batch.create_foreign_key(
                    f"fk_{table}_{'company' if table == 'applications' else 'application'}_owner",
                    parent,
                    [field, "user_id"],
                    ["id", "user_id"],
                )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        if table in ("companies", "applications"):
            op.create_index(f"uq_{table}_id_owner", table, ["id", "user_id"], unique=True)
        if table == "companies":
            op.drop_index("ix_companies_name", table_name="companies")
            op.create_index("ix_companies_name", "companies", ["name"])
            op.create_index(
                "uq_companies_owner_name", "companies", ["user_id", "name"], unique=True
            )
        else:
            field = "company_id" if table == "applications" else "application_id"
            op.create_index(
                f"ix_{table}_{'company' if table == 'applications' else 'application'}_owner",
                table,
                [field, "user_id"],
            )
    op.create_table(
        "auth_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_started", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_auth_throttles_window_started", "auth_throttles", ["window_started"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("安全降级需要在线预检查")
    if str(options().get("allow_ownership_downgrade", "")).lower() != "true":
        raise RuntimeError("降级会丢失安全边界；须备份并显式 -x allow_ownership_downgrade=true")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM users")).scalar() > 1:
        raise RuntimeError("多用户数据库禁止降级到全局共享数据模型")
    op.drop_table("auth_throttles")
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        if table != "companies":
            role = "company" if table == "applications" else "application"
            field, parent = (
                ("company_id", "companies")
                if table == "applications"
                else ("application_id", "applications")
            )
            op.drop_index(f"ix_{table}_{role}_owner", table_name=table)
        if table in ("companies", "applications"):
            op.drop_index(f"uq_{table}_id_owner", table_name=table)
        if table == "companies":
            op.drop_index("uq_companies_owner_name", table_name=table)
        with op.batch_alter_table(table, naming_convention=NAMES) as batch:
            batch.drop_constraint(f"fk_{table}_user", type_="foreignkey")
            if table != "companies":
                batch.drop_constraint(f"fk_{table}_{role}_owner", type_="foreignkey")
                batch.create_foreign_key(f"fk_{table}_{field}_{parent}", parent, [field], ["id"])
            batch.drop_column("user_id")
        if table == "companies":
            op.drop_index("ix_companies_name", table_name=table)
            op.create_index("ix_companies_name", table, ["name"], unique=True)
    op.drop_index("ix_users_bootstrap_slot", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("bootstrap_slot")
        batch.drop_column("is_active")
        batch.drop_column("token_version")
