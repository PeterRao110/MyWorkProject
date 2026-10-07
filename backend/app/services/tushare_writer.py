import re
from datetime import datetime

import pymysql

from app.services.database_config import read_values

DATA_DATABASE = "tusharedata"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INT = re.compile(r"-?\d+$")
_FLOAT = re.compile(r"-?\d+\.\d+$")


class WriterError(Exception):
    pass


def valid_ident(name: str) -> bool:
    return bool(_IDENT.fullmatch(name or ""))


def connect_data() -> pymysql.Connection:
    values = read_values()
    server = pymysql.connect(
        host=values["host"],
        port=int(values["port"]),
        user=values["user"],
        password=values["password"],
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with server.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DATA_DATABASE}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        server.commit()
    finally:
        server.close()
    return pymysql.connect(
        host=values["host"],
        port=int(values["port"]),
        user=values["user"],
        password=values["password"],
        database=DATA_DATABASE,
        charset="utf8mb4",
        autocommit=False,
    )


def write_result(
    app_conn: pymysql.Connection,
    table: str,
    pks: list[str],
    fields: list[str],
    items: list[list],
    source: str,
    field_types: dict[str, str] | None = None,
) -> int:
    if not valid_ident(table):
        raise WriterError("目标表名不正确")
    if not fields or any(not valid_ident(name) for name in fields):
        raise WriterError("写入字段不正确")
    if any(not valid_ident(name) for name in pks):
        raise WriterError("主键不正确")
    missing = [key for key in pks if key not in fields]
    if missing:
        raise WriterError(f"主键必须包含在勾选字段中：{', '.join(missing)}")
    columns = [(name, _type_for(name, index, field_types, items)) for index, name in enumerate(fields)]
    data_conn = connect_data()
    try:
        with data_conn.cursor() as cursor:
            _ensure_table(cursor, app_conn, table, columns, pks)
            if pks:
                _upsert(cursor, table, fields, items, source)
            else:
                _replace(cursor, table, fields, items, source)
        data_conn.commit()
        return len(items)
    except Exception:
        data_conn.rollback()
        raise
    finally:
        data_conn.close()


def _ensure_table(cursor, app_conn: pymysql.Connection, table: str, columns: list[tuple[str, str]], pks: list[str]) -> None:
    defs = [
        "`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT",
        "`source` VARCHAR(16) NOT NULL COMMENT '调用源'",
    ]
    defs += [f"`{name}` {sql_type} NULL" for name, sql_type in columns]
    defs.append("`synced_at` DATETIME NOT NULL COMMENT '写入时间'")
    keys = ["PRIMARY KEY (`id`)"]
    if pks:
        keys.append(_unique_key_ddl(pks))
    ddl = (
        f"CREATE TABLE IF NOT EXISTS `{table}` (" + ", ".join(defs + keys) + ") "
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    cursor.execute(ddl)
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (DATA_DATABASE, table),
    )
    existing = {row[0] for row in cursor.fetchall()}
    for name, sql_type in columns:
        if name not in existing:
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {sql_type} NULL")
    if pks:
        _align_unique_key(cursor, app_conn, table, pks)
    _record_ddl(app_conn, table, ddl)


def _unique_key_ddl(pks: list[str]) -> str:
    joined = ", ".join(f"`{name}`" for name in pks)
    return f"UNIQUE KEY `uk_biz` ({joined})"


def _align_unique_key(cursor, app_conn: pymysql.Connection, table: str, pks: list[str]) -> None:
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME='uk_biz' ORDER BY SEQ_IN_INDEX",
        (DATA_DATABASE, table),
    )
    current = [row[0] if not isinstance(row, dict) else row["COLUMN_NAME"] for row in cursor.fetchall()]
    if current == pks:
        return
    if current:
        cursor.execute(f"ALTER TABLE `{table}` DROP INDEX `uk_biz`")
    ddl = f"ALTER TABLE `{table}` ADD {_unique_key_ddl(pks)}"
    cursor.execute(ddl)
    _record_alter(app_conn, table, ddl, "唯一索引 uk_biz 与业务主键保持一致")


def _record_ddl(app_conn: pymysql.Connection, table: str, ddl: str) -> None:
    version = f"data-{table}"
    with app_conn.cursor() as cursor:
        cursor.execute("SELECT 1 FROM schema_model_change WHERE version=%s AND seq=1", (version,))
        if cursor.fetchone():
            return
        cursor.execute(
            "INSERT INTO schema_model_change (version, seq, model_name, action, summary, ddl) "
            "VALUES (%s, 1, %s, 'create', %s, %s)",
            (version, table, f"调度任务首次创建数据表 {table}", ddl),
        )


def _record_alter(app_conn: pymysql.Connection, table: str, ddl: str, summary: str) -> None:
    version = f"data-{table}"
    with app_conn.cursor() as cursor:
        cursor.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM schema_model_change WHERE version=%s", (version,))
        row = cursor.fetchone()
        seq = int(row["seq"] if isinstance(row, dict) else row[0]) + 1
        cursor.execute(
            "INSERT INTO schema_model_change (version, seq, model_name, action, summary, ddl) "
            "VALUES (%s, %s, %s, 'alter', %s, %s)",
            (version, seq, table, summary, ddl),
        )


def _upsert(cursor, table: str, fields: list[str], items: list[list], source: str) -> None:
    columns = ["`source`"] + [f"`{name}`" for name in fields] + ["`synced_at`"]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"`{name}`=VALUES(`{name}`)" for name in fields)
    sql = (
        f"INSERT INTO `{table}` ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE `source`=VALUES(`source`), {updates}, `synced_at`=VALUES(`synced_at`)"
    )
    cursor.executemany(sql, _rows(fields, items, source))


def _replace(cursor, table: str, fields: list[str], items: list[list], source: str) -> None:
    cursor.execute(f"DELETE FROM `{table}` WHERE `source`=%s", (source,))
    if not items:
        return
    # 业务唯一索引不含 source。另一调用源已占用同一主键时，更新该行并改写 source。
    _upsert(cursor, table, fields, items, source)


def _rows(fields: list[str], items: list[list], source: str) -> list[list]:
    now = datetime.now()
    width = len(fields)
    return [
        [source, *[_clean(row[index] if index < len(row) else None) for index in range(width)], now]
        for row in items
    ]


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def _type_for(name: str, index: int, field_types: dict[str, str] | None, items: list[list]) -> str:
    doc_type = (field_types or {}).get(name, "")
    mapped = _column_type(doc_type)
    if mapped:
        return mapped
    for row in items[:200]:
        value = row[index] if index < len(row) else None
        if value is None or value == "":
            continue
        text = str(value).strip()
        if _INT.fullmatch(text):
            return "BIGINT"
        if _FLOAT.fullmatch(text):
            return "DOUBLE"
        return "VARCHAR(191)"
    return "VARCHAR(191)"


def _column_type(doc_type: str) -> str:
    lowered = (doc_type or "").lower()
    if "int" in lowered:
        return "BIGINT"
    if "float" in lowered or "double" in lowered or "decimal" in lowered:
        return "DOUBLE"
    if "str" in lowered:
        return "VARCHAR(191)"
    return ""
