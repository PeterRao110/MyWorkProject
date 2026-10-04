from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymysql.err import MySQLError

from app.services.database_config import (
    connection_error_message,
    read_public,
    resolve_password,
    save_database_config,
    test_database_connection,
)
from app.services.source_config import read_sources, save_akshare, save_tushare_api

router = APIRouter()


class DatabaseSettingsBody(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    user: str = Field(min_length=1)
    password: str = ""


@router.get("/settings/database")
def get_database_settings() -> dict[str, str | bool]:
    return read_public()


@router.post("/settings/database")
def update_database_settings(body: DatabaseSettingsBody) -> dict[str, str | bool]:
    save_database_config(
        body.host.strip(),
        str(body.port),
        body.database.strip(),
        body.user.strip(),
        resolve_password(body.password),
    )
    return {"ok": True, "message": "数据库配置已保存到配置文件"}


@router.post("/settings/database/test")
def test_database_settings(body: DatabaseSettingsBody) -> dict[str, str | bool]:
    try:
        test_database_connection(
            body.host.strip(),
            body.port,
            body.database.strip(),
            body.user.strip(),
            resolve_password(body.password),
        )
    except MySQLError as error:
        raise HTTPException(status_code=400, detail=connection_error_message(error)) from error
    return {"ok": True, "message": "数据库连接成功"}


class AkshareSettingsBody(BaseModel):
    enabled: bool
    baseUrl: str = ""
    timeout: int = Field(ge=1, le=300)
    retry: int = Field(ge=0, le=10)


class TushareApiBody(BaseModel):
    token: str = ""
    baseUrl: str = ""
    timeout: int = Field(ge=1, le=300)
    retry: int = Field(ge=0, le=10)


class TushareSettingsBody(BaseModel):
    rds: TushareApiBody
    promax: TushareApiBody


@router.get("/settings/sources")
def get_source_settings() -> dict[str, dict[str, str | bool]]:
    return read_sources()


@router.post("/settings/akshare")
def update_akshare_settings(body: AkshareSettingsBody) -> dict[str, str | bool]:
    save_akshare(body.enabled, body.baseUrl.strip(), str(body.timeout), str(body.retry))
    return {"ok": True, "message": "AKShare 配置已保存到配置文件"}


@router.post("/settings/tushare")
def update_tushare_settings(body: TushareSettingsBody) -> dict[str, str | bool]:
    save_tushare_api("TUSHARE_RDS", body.rds.token, body.rds.baseUrl.strip(), str(body.rds.timeout), str(body.rds.retry))
    save_tushare_api(
        "TUSHARE_PROMAX",
        body.promax.token,
        body.promax.baseUrl.strip(),
        str(body.promax.timeout),
        str(body.promax.retry),
    )
    return {"ok": True, "message": "Tushare 配置已保存到配置文件"}
