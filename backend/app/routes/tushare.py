from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.tushare_client import TushareError, load_schema, query_api

router = APIRouter()


class QueryBody(BaseModel):
    source: str = Field(pattern=r"^(rds|promax)$")
    apiName: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    params: dict[str, str] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list, max_length=200)


@router.get("/tushare/docs/{doc_id}")
def get_tushare_doc(doc_id: str) -> dict:
    if not doc_id.isdigit():
        raise HTTPException(status_code=400, detail="接口编号不正确")
    try:
        return load_schema(doc_id)
    except TushareError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/tushare/query")
def query_tushare(body: QueryBody) -> dict:
    if not body.fields:
        raise HTTPException(status_code=400, detail="请至少勾选一列")
    if any(not _safe_name(name) for name in body.fields):
        raise HTTPException(status_code=400, detail="返回字段不正确")
    if any(not _safe_name(key) or len(value) > 500 for key, value in body.params.items()):
        raise HTTPException(status_code=400, detail="入参不正确")
    try:
        return query_api(body.source, body.apiName, body.params, body.fields)
    except TushareError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _safe_name(value: str) -> bool:
    return bool(value) and value.replace("_", "").isalnum() and not value[0].isdigit()
