import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.models import seed_default_config
from app.router import router
from app.services.monitor_service import MonitorService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Determine the project root: where main.py lives
PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_DIR / "app" / "static"

# Ensure the Python path includes the project root
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("Starting up...")
    await init_db()
    await seed_default_config()

    monitor = MonitorService()
    app.state.monitor = monitor
    logger.info("Application ready")
    yield
    # ── Shutdown ──
    logger.info("Shutting down...")
    if monitor.is_running:
        monitor.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="WeChat Group Monitor",
    description="Detect malicious messages in WeChat groups using keyword matching + LLM review",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes FIRST
app.include_router(router)

# Mount static frontend LAST (catches all non-API routes)
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    logger.info("Static files mounted from %s", STATIC_DIR)
else:
    logger.warning("Static directory not found at %s", STATIC_DIR)
