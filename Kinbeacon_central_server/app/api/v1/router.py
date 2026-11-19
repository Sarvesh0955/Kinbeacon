from fastapi import APIRouter, Depends
from app.api.v1.admin import router as admin_router
from app.api.v1.anchors import router as anchors_router
from app.api.v1.devices import router as devices_router
from app.api.v1.health import router as health_router
from app.api.v1.searches import router as searches_router
from app.api.v1.zones import router as zones_router
from app.core.auth import verify_api_key

api_v1_router = APIRouter()
# Health check is public
api_v1_router.include_router(health_router)

# Protected with optional API key header
api_v1_router.include_router(zones_router, dependencies=[Depends(verify_api_key)])
api_v1_router.include_router(anchors_router, dependencies=[Depends(verify_api_key)])
api_v1_router.include_router(devices_router, dependencies=[Depends(verify_api_key)])
api_v1_router.include_router(searches_router, dependencies=[Depends(verify_api_key)])
api_v1_router.include_router(admin_router, dependencies=[Depends(verify_api_key)])
