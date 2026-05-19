import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import bootstrap
from .finnhub_client import FinnhubError
from .market_hours import is_market_open
from .price_hub import hub
from .routes import history as history_routes
from .routes import portfolio as portfolio_routes
from .routes import quotes as quotes_routes
from .routes import search as search_routes
from .routes import trades as trades_routes
from .routes import users as users_routes
from .routes import ws as ws_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    await hub.start()
    try:
        yield
    finally:
        await hub.stop()


app = FastAPI(title="MarketSimulator", lifespan=lifespan)

# Permissive CORS — this is a localhost-only learning app.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(FinnhubError)
async def _finnhub_error(_req: Request, exc: FinnhubError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(portfolio_routes.router, prefix="/api")
app.include_router(trades_routes.router, prefix="/api")
app.include_router(quotes_routes.router, prefix="/api")
app.include_router(history_routes.router, prefix="/api")
app.include_router(search_routes.router, prefix="/api")
app.include_router(users_routes.router, prefix="/api")
app.include_router(ws_routes.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "market_open": is_market_open()}
