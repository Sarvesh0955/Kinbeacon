import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_transport
from app.api.v1.demo import Demo, router as demo_router
from app.api.v1.live_find import LiveFind, router as live_find_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import KinBeaconError
from app.core.logging import logger
from app.database import async_session_factory, init_db
from app.repositories.search_repo import SearchRepository
from app.services.health_service import HealthService
from app.transport.http import HttpAnchorTransport


async def background_fleet_prober():
    """Periodically probes anchor fleet health."""
    while True:
        try:
            await asyncio.sleep(settings.health_probe_interval_s)
            async with async_session_factory() as session:
                transport = get_transport()
                service = HealthService(session, transport)
                await service.probe_anchor_fleet()
                await session.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Fleet prober tick failed: %s", e)


async def background_ttl_purger(live_find: LiveFind):
    """Periodically purges searches & sightings older than TTL."""
    while True:
        try:
            await asyncio.sleep(60.0)
            live_find.expire()
            async with async_session_factory() as session:
                repo = SearchRepository(session)
                purged = await repo.purge_older_than(settings.retention_ttl_s)
                if purged > 0:
                    logger.info("Purged %d expired searches", purged)
                await session.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("TTL purger tick failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()

    # Launch background tasks
    prober_task = asyncio.create_task(background_fleet_prober())
    purger_task = asyncio.create_task(background_ttl_purger(app.state.live_find))

    logger.info("KinBeacon Central Server started successfully.")
    yield

    # Shutdown
    logger.info("Shutting down KinBeacon Central Server...")
    prober_task.cancel()
    purger_task.cancel()
    await asyncio.gather(prober_task, purger_task, return_exceptions=True)

    transport = get_transport()
    if isinstance(transport, HttpAnchorTransport):
        await transport.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="KinBeacon Central Server API for device tracking and zone identification.",
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

    @app.exception_handler(KinBeaconError)
    async def kinbeacon_error_handler(request: Request, exc: KinBeaconError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "message": exc.message},
        )

    @app.get("/health", tags=["Health"])
    async def root_health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": "1.0.0",
        }

    app.state.demo = Demo()
    app.state.live_find = LiveFind()
    app.include_router(demo_router, prefix=settings.api_prefix)
    app.include_router(live_find_router, prefix=settings.api_prefix)
    app.include_router(api_v1_router, prefix=settings.api_prefix)

    return app


app = create_app()
