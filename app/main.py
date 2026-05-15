import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware import RequestContextMiddleware
from app.api.routes import analytics, auth, health, projects, tasks
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging

configure_logging(logging.DEBUG if settings.debug else logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Enterprise Backend API",
    description="Backend service with layered architecture and strict DTOs",
    version="1.0.0",
)

# ── Middleware ────────────────────────────────────────────────────────────────
# Order: request-context wraps everything (innermost runs last), CORS outermost.
app.add_middleware(RequestContextMiddleware)

cors_origins = settings.allowed_origins or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Error envelope ────────────────────────────────────────────────────────────
def _error_response(code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(AppException)
async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
    return _error_response(exc.status_code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Covers both fastapi.HTTPException and starlette's built-in 404/405."""
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _error_response(exc.status_code, message)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "message": "Validation failed",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def handle_sqlalchemy_error(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An internal database error occurred",
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Hitting the bare host sends you to Swagger UI."""
    return RedirectResponse(url="/docs")


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
