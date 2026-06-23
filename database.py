import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, select, func
from config import settings

logger = logging.getLogger(__name__)
Base = declarative_base()

_engine = None
_async_session_maker = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
        )
        @event.listens_for(_engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return _engine

def get_session_maker():
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_maker

async def get_db():
    async with get_session_maker()() as session:
        yield session

async def check_ai_limit(user_id: int, db: AsyncSession) -> bool:
    from models import AIUsage   # avoid circular import
    today = func.current_date()
    stmt = select(AIUsage).where(AIUsage.user_id == user_id, AIUsage.date == today)
    result = await db.execute(stmt)
    usage = result.scalar_one_or_none()
    limit = settings.DAILY_AI_LIMIT_PER_USER
    if usage and usage.count >= limit:
        return False
    return True

async def log_ai_usage(db: AsyncSession, user_id: int):
    from models import AIUsage
    today = func.current_date()
    stmt = select(AIUsage).where(AIUsage.user_id == user_id, AIUsage.date == today)
    result = await db.execute(stmt)
    usage = result.scalar_one_or_none()
    if usage:
        usage.count += 1
    else:
        db.add(AIUsage(user_id=user_id, count=1))
    await db.commit()
