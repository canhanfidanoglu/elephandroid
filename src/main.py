import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.auth.routes import router as auth_router
from src.config import settings
from src.database import create_tables
from src.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from src.planner.routes import router as planner_router
from src.sync.routes import router as sync_router
from src.ai.routes import router as ai_router
from src.reports.routes import router as reports_router
from src.chat.routes import router as chat_router
from src.emails.routes import router as emails_router
from src.meetings.routes import router as meetings_router
from src.teams_chat.routes import router as teams_chat_router
from src.bot.routes import router as bot_router
from src.wizard.routes import router as wizard_router

# ── Logging ──────────────────────────────────────────────────────────

_log_fmt = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    if settings.log_json
    else "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format=_log_fmt,
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)

# Quiet noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ── Templates ────────────────────────────────────────────────────────

templates = Jinja2Templates(directory="src/frontend/templates")

# ── Lifespan ─────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting Elephandroid (LLM=%s, DB=%s)",
        settings.llm_provider,
        "postgres" if settings.is_postgres else "sqlite",
    )
    await create_tables()
    yield
    logger.info("Shutting down Elephandroid")


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(title="Elephandroid", version="0.1.0", lifespan=lifespan)

# Middleware order matters — outermost first, innermost last.

# 1. Request logging (outermost — logs everything including errors)
app.add_middleware(RequestLoggingMiddleware)

# 2. Rate limiting
app.add_middleware(RateLimitMiddleware, rpm=settings.rate_limit_rpm)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Session (innermost — needs to run before route handlers)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    max_age=settings.session_max_age,
)

# ── Global exception handler ─────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# ── Routers ──────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(planner_router)
app.include_router(sync_router)
app.include_router(ai_router)
app.include_router(reports_router)
app.include_router(chat_router)
app.include_router(emails_router)
app.include_router(meetings_router)
app.include_router(teams_chat_router)
app.include_router(bot_router)
app.include_router(wizard_router)


# ── Root ─────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = request.session.get("user_id")
    return templates.TemplateResponse(
        "index.html", {"request": request, "user_id": user_id}
    )
