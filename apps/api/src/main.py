import importlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Preload anyio's asyncio backend before Starlette/FastAPI run anyio.to_thread (e.g. campaign
# compositing). A partial venv or wrong interpreter can otherwise raise on first request:
# ModuleNotFoundError: No module named 'anyio._backends'
importlib.import_module("anyio._backends._asyncio")

from dotenv import load_dotenv  # noqa: E402

# Load env BEFORE importing route modules (they import dependencies, which validates JWTs at request time).
repo_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # apps/api/.env
output_dir = repo_root / "output"
output_dir.mkdir(parents=True, exist_ok=True)

from fastapi import FastAPI, Request, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .errors import (  # noqa: E402
    APIError,
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from .routes import auth_router, campaign_router, health_router  # noqa: E402

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting creative automation API...")
    yield
    logger.info("Shutting down API...")


app = FastAPI(
    title="Creative automation API",
    description="Campaign brief to social ad creatives (SSE)",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:5173",
)
cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(
        status_code=401,
        content={"error": exc.message, "details": exc.details, "status": 401},
    )


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError):
    return JSONResponse(
        status_code=403,
        content={"error": exc.message, "details": exc.details, "status": 403},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": exc.message, "details": exc.details, "status": 404},
    )


@app.exception_handler(BadRequestError)
async def bad_request_handler(request: Request, exc: BadRequestError):
    return JSONResponse(
        status_code=400,
        content={"error": exc.message, "details": exc.details, "status": 400},
    )


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "details": exc.details,
            "status": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "details": str(exc), "status": 500},
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "creative-automation-api",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(campaign_router, prefix="/generate", tags=["Generate"])
app.mount(
    "/output-files",
    StaticFiles(directory=str(output_dir)),
    name="output_files",
)
