"""Local SQL snapshot before schema migrations; never prints row contents or credentials."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pymysql

from app.core.config import settings


def main():
    root = Path(__file__).resolve().parents[2]
    destination = root / "backups"
    destination.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"qiuzhao_pre_recruitment_0008_{stamp}.sql"
    connection = pymysql.connect(
        host=settings.mysql_host, port=settings.mysql_port, user=settings.mysql_user,
        password=settings.mysql_password, database=settings.mysql_db, charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor, target.open("w", encoding="utf-8") as output:
            output.write("SET FOREIGN_KEY_CHECKS=0;\n")
            cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            names = [row[0] for row in cursor.fetchall()]
            for name in names:
                escaped = name.replace("`", "``")
                cursor.execute(f"SHOW CREATE TABLE `{escaped}`")
                definition = cursor.fetchone()[1]
                output.write(f"DROP TABLE IF EXISTS `{escaped}`;\n{definition};\n")
                cursor.execute(f"SELECT * FROM `{escaped}`")
                columns = [f"`{column[0].replace('`', '``')}`" for column in cursor.description]
                placeholders = ", ".join(["%s"] * len(columns))
                prefix = f"INSERT INTO `{escaped}` ({', '.join(columns)}) VALUES ({placeholders});"
                for row in cursor.fetchall():
                    output.write(cursor.mogrify(prefix, row) + "\n")
            output.write("SET FOREIGN_KEY_CHECKS=1;\n")
        digest = sha256(target.read_bytes()).hexdigest()
        print(f"backup={target} tables={len(names)} sha256={digest}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
