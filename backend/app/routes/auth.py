from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.services.auth_config import (
    COOKIE_NAME,
    MAX_AGE_SECONDS,
    issue_session,
    password_configured,
    save_password,
    session_ok,
    verify_password,
)

router = APIRouter()


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class SetupBody(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(min_length=1, max_length=128)


def _accept(password: str) -> str:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    return password


def _start_session(response: Response) -> dict[str, bool]:
    response.set_cookie(
        COOKIE_NAME,
        issue_session(),
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True}


@router.get("/auth/status")
def auth_status(request: Request) -> dict[str, bool]:
    return {
        "configured": password_configured(),
        "authenticated": session_ok(request.cookies.get(COOKIE_NAME)),
    }


@router.post("/auth/setup")
def auth_setup(body: SetupBody, response: Response) -> dict[str, bool]:
    if password_configured():
        raise HTTPException(status_code=400, detail="登录密码已设置")
    password = _accept(body.password)
    if password != body.confirm:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")
    save_password(password)
    return _start_session(response)


@router.post("/auth/login")
def auth_login(body: LoginBody, response: Response) -> dict[str, bool]:
    if not password_configured():
        raise HTTPException(status_code=400, detail="请先设置登录密码")
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="密码不正确")
    return _start_session(response)


@router.post("/auth/logout")
def auth_logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
