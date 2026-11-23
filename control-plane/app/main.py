# Nguyễn Tâm Bình - 2324801030003
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import get_settings
from app.routers import admin, agent, auth, billing, instances, nodes, notifications, os_images, plans, public
from app.web import serve_web
from app.workers.scheduler import create_scheduler
from app.services import notify


@asynccontextmanager
async def lifespan(app):
    notify.start_sender()
    scheduler = create_scheduler() if get_settings().workers_enabled else None
    if scheduler:
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=True)
    notify.stop_sender()


def create_app():
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
    for router in (auth.router, plans.router, instances.router, nodes.router, os_images.router, billing.router, admin.router, agent.router, public.router, notifications.router):
        application.include_router(router, prefix="/api/v1")

    @application.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Dữ liệu không hợp lệ. Vui lòng kiểm tra các trường nhập.", "fields": [".".join(str(part) for part in error["loc"]) for error in exc.errors()]})

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "Dữ liệu đã tồn tại hoặc đang được cập nhật. Vui lòng thử lại."})

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "Dịch vụ dữ liệu tạm thời chưa sẵn sàng. Vui lòng thử lại."})

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": "Hệ thống chưa thể xử lý yêu cầu. Vui lòng liên hệ quản trị viên."})

    if settings.web_dir:
        serve_web(application, settings.web_dir)
    return application


app = create_app()
