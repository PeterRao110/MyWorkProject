from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.env import port
from app.routes import router
from app.services import scheduler
from app.services.auth_config import session_ok, COOKIE_NAME


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        public = path == "/api/health" or path.startswith("/api/auth/")
        if request.method == "OPTIONS" or not path.startswith("/api/") or public:
            return await call_next(request)
        if session_ok(request.cookies.get(COOKIE_NAME)):
            return await call_next(request)
        return JSONResponse({"detail": "未登录"}, status_code=401)

    app.include_router(router, prefix="/api")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
