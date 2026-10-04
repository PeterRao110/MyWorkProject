import re

import pymysql
from pymysql.err import MySQLError

from app.models.changelog import ModelChange, SchemaVersion, load_versions, write_document
from app.services.database_config import connection_error_message, read_values


def apply_versions() -> list[str]:
    document = write_document()
    print(f"已更新文档 {document}")
    connection = connect_database()
    applied: list[str] = []
    try:
        versions = load_versions()
        ensure_change_table(connection, versions[0])
        existing = load_applied(connection)
        for item in versions:
            pending = [change for change in item.changes if (item.version, change.seq) not in existing]
            if not pending:
                print(f"{item.version} 已记录，跳过")
                continue
            for change in pending:
                with connection.cursor() as cursor:
                    cursor.execute(change.ddl)
                record_change(connection, item.version, change)
            connection.commit()
            applied.append(item.version)
            print(f"{item.version} 已写入 {len(pending)} 条变更")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return applied


def connect_database() -> pymysql.Connection:
    values = read_values()
    database = values["database"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise RuntimeError("数据库名只能包含字母、数字和下划线")
    server = connect(values, database=None)
    try:
        with server.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        server.commit()
    finally:
        server.close()
    return connect(values, database=database)


def connect(values: dict[str, str], database: str | None) -> pymysql.Connection:
    return pymysql.connect(
        host=values["host"],
        port=int(values["port"]),
        user=values["user"],
        password=values["password"],
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )


def ensure_change_table(connection: pymysql.Connection, first: SchemaVersion) -> None:
    bootstrap = next(change for change in first.changes if change.model_name == "schema_model_change")
    with connection.cursor() as cursor:
        cursor.execute(bootstrap.ddl)
    connection.commit()


def load_applied(connection: pymysql.Connection) -> set[tuple[str, int]]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version, seq FROM schema_model_change")
        return {(row[0], int(row[1])) for row in cursor.fetchall()}


def record_change(connection: pymysql.Connection, version: str, change: ModelChange) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO schema_model_change (version, seq, model_name, action, summary, ddl)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (version, change.seq, change.model_name, change.action, change.summary, change.ddl),
        )


def main() -> None:
    try:
        apply_versions()
    except MySQLError as error:
        raise SystemExit(connection_error_message(error)) from error


if __name__ == "__main__":
    main()
