from contextlib import contextmanager
from datetime import date, datetime

import pymysql
from pymysql.cursors import DictCursor

from app.services.database_config import read_values


def list_plans() -> list[dict]:
    with database() as connection:
        rows = fetch_rows(connection)
    return group_plans(rows)


def add_item(trade_date: str, item: dict) -> dict:
    with database() as connection:
        plan_id = ensure_plan(connection, trade_date)
        sort_order = next_sort(connection, plan_id)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO daily_plan_item (
                  plan_id, sort_order, symbol, symbol_name, price, trend, operation_plan, strategy
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    plan_id,
                    sort_order,
                    item["symbol"],
                    item["symbolName"],
                    item["price"],
                    item["trend"],
                    item["operationPlan"],
                    item["strategy"],
                ),
            )
        return plan_of(connection, trade_date)


def move_item(trade_date: str, item_id: int, direction: int) -> dict:
    with database() as connection:
        items = items_of(connection, trade_date)
        index = next((position for position, item in enumerate(items) if item["id"] == item_id), -1)
        target = index + direction
        if index < 0 or target < 0 or target >= len(items):
            return plan_of(connection, trade_date)
        current = items[index]
        other = items[target]
        with connection.cursor() as cursor:
            cursor.execute("UPDATE daily_plan_item SET sort_order = %s WHERE id = %s", (other["sort_order"], current["id"]))
            cursor.execute("UPDATE daily_plan_item SET sort_order = %s WHERE id = %s", (current["sort_order"], other["id"]))
        return plan_of(connection, trade_date)


def remove_item(trade_date: str, item_id: int) -> dict:
    with database() as connection:
        plan_id = find_plan_id(connection, trade_date)
        if plan_id is None:
            return empty_plan(trade_date)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM daily_plan_item WHERE id = %s AND plan_id = %s", (item_id, plan_id))
        return plan_of(connection, trade_date)


def save_review(trade_date: str, item_id: int, review: dict) -> dict:
    with database() as connection:
        plan_id = find_plan_id(connection, trade_date)
        if plan_id is None:
            return empty_plan(trade_date)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE daily_plan_item
                SET result = %s, result_note = %s, next_plan = %s, reviewed = 1
                WHERE id = %s AND plan_id = %s
                """,
                (review["result"], review["resultNote"], review["nextPlan"], item_id, plan_id),
            )
        return plan_of(connection, trade_date)


def ensure_plan(connection: pymysql.Connection, trade_date: str) -> int:
    found = find_plan_id(connection, trade_date)
    if found is not None:
        return found
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO daily_plan (trade_date) VALUES (%s)", (trade_date,))
        return int(cursor.lastrowid)


def find_plan_id(connection: pymysql.Connection, trade_date: str) -> int | None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM daily_plan WHERE trade_date = %s", (trade_date,))
        row = cursor.fetchone()
    return int(row["id"]) if row else None


def next_sort(connection: pymysql.Connection, plan_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_sort FROM daily_plan_item WHERE plan_id = %s", (plan_id,))
        row = cursor.fetchone()
    return int(row["next_sort"])


def items_of(connection: pymysql.Connection, trade_date: str) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT item.id, item.sort_order
            FROM daily_plan_item item
            JOIN daily_plan plan ON plan.id = item.plan_id
            WHERE plan.trade_date = %s
            ORDER BY item.sort_order, item.id
            """,
            (trade_date,),
        )
        return list(cursor.fetchall())


def plan_of(connection: pymysql.Connection, trade_date: str) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              plan.trade_date,
              item.id,
              item.symbol,
              item.symbol_name,
              item.price,
              item.trend,
              item.operation_plan,
              item.strategy,
              item.result,
              item.result_note,
              item.next_plan,
              item.reviewed
            FROM daily_plan plan
            LEFT JOIN daily_plan_item item ON item.plan_id = plan.id
            WHERE plan.trade_date = %s
            ORDER BY item.sort_order, item.id
            """,
            (trade_date,),
        )
        rows = list(cursor.fetchall())
    plans = group_plans(rows)
    if not plans:
        return empty_plan(trade_date)
    return plans[0]


def fetch_rows(connection: pymysql.Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              plan.trade_date,
              item.id,
              item.symbol,
              item.symbol_name,
              item.price,
              item.trend,
              item.operation_plan,
              item.strategy,
              item.result,
              item.result_note,
              item.next_plan,
              item.reviewed
            FROM daily_plan plan
            JOIN daily_plan_item item ON item.plan_id = plan.id
            ORDER BY plan.trade_date DESC, item.sort_order, item.id
            """
        )
        return list(cursor.fetchall())


def group_plans(rows: list[dict]) -> list[dict]:
    plans: list[dict] = []
    index: dict[str, dict] = {}
    for row in rows:
        if row["id"] is None:
            continue
        trade_date = format_date(row["trade_date"])
        plan = index.get(trade_date)
        if plan is None:
            plan = {"date": trade_date, "items": []}
            index[trade_date] = plan
            plans.append(plan)
        plan["items"].append(to_item(row))
    return plans


def to_item(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "symbol": row["symbol"],
        "symbolName": row["symbol_name"],
        "price": None if row["price"] is None else float(row["price"]),
        "trend": row["trend"],
        "operationPlan": row["operation_plan"],
        "strategy": row["strategy"],
        "result": row["result"],
        "resultNote": row["result_note"],
        "nextPlan": row["next_plan"],
        "reviewed": bool(row["reviewed"]),
    }


def empty_plan(trade_date: str) -> dict:
    return {"date": trade_date, "items": []}


def format_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


@contextmanager
def database():
    values = read_values()
    connection = pymysql.connect(
        host=values["host"],
        port=int(values["port"]),
        user=values["user"],
        password=values["password"],
        database=values["database"],
        charset="utf8mb4",
        autocommit=False,
        cursorclass=DictCursor,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
