import asyncio, os, time, shutil, logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from database import get_session_maker
from models import Status
from config import settings

logger = logging.getLogger(__name__)

async def cleanup_expired_statuses():
    while True:
        try:
            async with get_session_maker()() as db:
                now = datetime.now(timezone.utc)
                result = await db.execute(select(Status).where(Status.expires_at <= now))
                expired = result.scalars().all()
                for status in expired:
                    file_path = os.path.join(settings.LOCAL_MEDIA_ROOT, status.media_url)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    await db.delete(status)
                await db.commit()
        except Exception as e:
            logger.exception("Status cleanup error")
        await asyncio.sleep(3600)

async def cleanup_temp_chunks():
    TEMP_DIR = Path("/tmp/echochat_chunks")
    while True:
        try:
            now = time.time()
            if TEMP_DIR.exists():
                for user_dir in TEMP_DIR.iterdir():
                    if user_dir.is_dir():
                        for chunk in user_dir.glob("*.part"):
                            if now - chunk.stat().st_mtime > 3600:
                                chunk.unlink()
                        if not any(user_dir.iterdir()):
                            user_dir.rmdir()
        except Exception as e:
            logger.exception("Temp cleanup error")
        await asyncio.sleep(600)
