import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.rtc.peer import close_all_peers
from app.ws.control import router as control_router
from app.ws.signaling import router as signaling_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("realtime-assistant starting on %s:%s", settings.APP_HOST, settings.APP_PORT)
    log.info("frontend origin allowed: %s", settings.FRONTEND_ORIGIN)
    yield
    await close_all_peers()
    log.info("realtime-assistant stopped")


app = FastAPI(title="Realtime Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signaling_router)
app.include_router(control_router)


@app.get("/health")
async def health():
    return {"status": "ok", "milestone": "M3"}
