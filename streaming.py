import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy import select
from database import get_db, AsyncSession
from models import User, LiveStream
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/stream", tags=["streaming"])

@router.post("/create")
async def create_stream(
    title: str = Form(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    existing = (
        await db.execute(
            select(LiveStream).where(
                LiveStream.user_id == current_user.id, LiveStream.is_live == True
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Already have an active stream")
    stream_key = f"{current_user.id}_{uuid.uuid4().hex[:12]}"
    hls_url = f"{settings.LOCAL_MEDIA_URL_PREFIX}hls/{stream_key}.m3u8"
    stream = LiveStream(
        user_id=current_user.id,
        title=title,
        stream_key=stream_key,
        is_live=False,
        hls_url=hls_url,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return {
        "stream_id": stream.id,
        "stream_key": stream_key,
        "rtmp_url": "rtmp://your-server:1935/live",
        "hls_url": hls_url,
    }

@router.post("/auth")
async def rtmp_auth(request: Request, db=Depends(get_db)):
    form = await request.form()
    key = form.get("name")
    if not key:
        raise HTTPException(403)
    stream = (
        await db.execute(select(LiveStream).where(LiveStream.stream_key == key))
    ).scalar_one_or_none()
    if not stream:
        raise HTTPException(403)
    stream.is_live = True
    stream.started_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "ok"}

@router.post("/done")
async def rtmp_done(request: Request, db=Depends(get_db)):
    form = await request.form()
    key = form.get("name")
    if not key:
        raise HTTPException(403)
    stream = (
        await db.execute(select(LiveStream).where(LiveStream.stream_key == key))
    ).scalar_one_or_none()
    if stream:
        stream.is_live = False
        stream.stopped_at = datetime.now(timezone.utc)
        await db.commit()
    return {"status": "ok"}

@router.get("/active")
async def active_streams(db=Depends(get_db)):
    result = await db.execute(select(LiveStream).where(LiveStream.is_live == True))
    streams = result.scalars().all()
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "username": s.user.username,
            "title": s.title,
            "hls_url": s.hls_url,
            "started_at": str(s.started_at),
        }
        for s in streams
  ]
