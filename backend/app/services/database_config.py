import os
from pathlib import Path

import pymysql
from dotenv import dotenv_values, set_key
from pymysql.err import MySQLError

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

FIELDS = {
    "host": "MYSQL_HOST",
    "port": "MYSQL_PORT",
    "database": "MYSQL_DATABASE",
    "user": "MYSQL_USER",
    "password": "MYSQL_PASSWORD",
}

DEFAULTS = {
    "host": "127.0.0.1",
    "port": "3306",
    "database": "touyan",
    "user": "root",
    "password": "",
}


def read_values() -> dict[str, str]:
    stored = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return {name: str(stored.get(key) or DEFAULTS[name]) for name, key in FIELDS.items()}


def read_public() -> dict[str, str | bool]:
    values = read_values()
    return {
        "host": values["host"],
        "port": values["port"],
        "database": values["database"],
        "user": values["user"],
        "passwordSet": bool(values["password"]),
    }


def resolve_password(submitted: str) -> str:
    if submitted:
        return submitted
    return read_values()["password"]


def save_database_config(host: str, port: str, database: str, user: str, password: str) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.write_text("PORT=3000\n", encoding="utf-8")
    updates = {
        "MYSQL_HOST": host,
        "MYSQL_PORT": port,
        "MYSQL_DATABASE": database,
        "MYSQL_USER": user,
        "MYSQL_PASSWORD": password,
    }
    for key, value in updates.items():
        set_key(str(ENV_PATH), key, value)
        os.environ[key] = value


def test_database_connection(host: str, port: int, database: str, user: str, password: str) -> None:
    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        connect_timeout=5,
        charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        connection.close()


def connection_error_message(error: MySQLError) -> str:
    detail = error.args[1] if len(error.args) > 1 else str(error)
    return f"连接失败：{detail}"
