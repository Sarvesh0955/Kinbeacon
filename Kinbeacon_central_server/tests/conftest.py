import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db_session, get_transport, set_transport
from app.database import Base
from app.main import create_app
from app.transport.mock import MockAnchorTransport


@pytest.fixture
def mock_transport():
    transport = MockAnchorTransport()
    set_transport(transport)
    return transport


@pytest.fixture
async def test_session():
    # Use SQLite in-memory database
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def client(test_session, mock_transport):
    app = create_app()

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_transport] = lambda: mock_transport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
