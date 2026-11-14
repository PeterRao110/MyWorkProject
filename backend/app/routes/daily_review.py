import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymysql.err import MySQLError

from app.services import daily_review

router = APIRouter()
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ItemBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    symbolName: str = Field(min_length=1, max_length=64)
    price: float | None = None
    trend: str = Field(default="", max_length=500)
    operationPlan: str = Field(min_length=1, max_length=2000)
    strategy: str = Field(default="", max_length=2000)


class MoveBody(BaseModel):
    direction: Literal[-1, 1]


class ReviewBody(BaseModel):
    result: Literal["pending", "success", "failure"]
    resultNote: str = Field(default="", max_length=2000)
    nextPlan: str = Field(default="", max_length=2000)


@router.get("/daily-plans")
def get_daily_plans() -> list[dict]:
    return run(daily_review.list_plans)


@router.post("/daily-plans/{trade_date}/items")
def create_daily_plan_item(trade_date: str, body: ItemBody) -> dict:
    checked = require_date(trade_date)
    return run(
        lambda: daily_review.add_item(
            checked,
            {
                "symbol": body.symbol.strip(),
                "symbolName": body.symbolName.strip(),
                "price": body.price,
                "trend": body.trend.strip(),
                "operationPlan": body.operationPlan.strip(),
                "strategy": body.strategy.strip(),
            },
        )
    )


@router.put("/daily-plans/{trade_date}/items/{item_id}/move")
def move_daily_plan_item(trade_date: str, item_id: int, body: MoveBody) -> dict:
    checked = require_date(trade_date)
    return run(lambda: daily_review.move_item(checked, item_id, body.direction))


@router.delete("/daily-plans/{trade_date}/items/{item_id}")
def delete_daily_plan_item(trade_date: str, item_id: int) -> dict:
    checked = require_date(trade_date)
    return run(lambda: daily_review.remove_item(checked, item_id))


@router.put("/daily-plans/{trade_date}/items/{item_id}/review")
def save_daily_plan_review(trade_date: str, item_id: int, body: ReviewBody) -> dict:
    checked = require_date(trade_date)
    if body.result != "pending" and not body.resultNote.strip():
        raise HTTPException(status_code=400, detail="请填写执行结果描述")
    return run(
        lambda: daily_review.save_review(
            checked,
            item_id,
            {
                "result": body.result,
                "resultNote": body.resultNote.strip(),
                "nextPlan": body.nextPlan.strip(),
            },
        )
    )


def require_date(value: str) -> str:
    if not _DATE.fullmatch(value):
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise HTTPException(status_code=400, detail="日期无效") from error
    return value


def run(action):
    try:
        return action()
    except MySQLError as error:
        raise HTTPException(status_code=400, detail="每日计划保存失败") from error
