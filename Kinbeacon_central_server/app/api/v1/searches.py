from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session, get_transport
from app.repositories.search_repo import SearchRepository
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.transport.base import AnchorTransport

router = APIRouter(tags=["Searches"])


@router.post("/searches", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_device(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = SearchService(session, transport)
    return await service.execute_search(request)


@router.get("/searches/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: str,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = SearchService(session, transport)
    return await service.get_search(search_id)


@router.get("/devices/{device_id}/searches", response_model=List[SearchResponse])
async def get_device_searches(
    device_id: str,
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    repo = SearchRepository(session)
    searches = await repo.get_by_device_id(device_id, limit=limit)
    service = SearchService(session, transport)
    results = []
    for s in searches:
        results.append(await service.get_search(s.id))
    return results
