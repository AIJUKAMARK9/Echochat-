import shutil
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy import desc, select
from database import get_db, AsyncSession
from models import User, Reel, Status
from auth import get_current_user
from config import settings
from pathlib import Path

router = APIRouter(prefix="/social", tags=["reels_status"])

MEDIA_ROOT = Path(settings.LOCAL_MEDIA_ROOT)

@router.post("/reels/upload")
async def upload_reel(
    file: UploadFile = File(...),
    caption: str = Form(""),
    current_user=Depends(get_current_user),
):
    safe_name = Path(file.filename).name.replace(" ", "_")
    user_dir = MEDIA_ROOT / str(current_user.id) / "reels"
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / safe_name
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    media_url = f"{current_user.id}/reels/{safe_name}"
    async with get_db() as db:
        reel = Reel(user_id=current_user.id, media_url=media_url, caption=caption)
        db.add(reel)
        await db.commit()
        await db.refresh(reel)
        return {"id": reel.id, "media_url": f"/media/{media_url}", "caption": caption}

@router.get("/reels/feed")
async def reels_feed(
    page: int = 1,
    size: int = 10,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    offset = (page - 1) * size
    stmt = select(Reel).order_by(desc(Reel.created_at)).offset(offset).limit(size)
    result = await db.execute(stmt)
    reels = result.scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": r.user.username,
            "media_url": f"/media/{r.media_url}",
            "caption": r.caption,
            "likes": r.likes,
            "views": r.views,
            "created_at": str(r.created_at),
        }
        for r in reels
    ]

@router.post("/status/upload")
async def upload_status(
    file: UploadFile = File(...),
    media_type: str = Form("image"),
    current_user=Depends(get_current_user),
):
    safe_name = Path(file.filename).name.replace(" ", "_")
    user_dir = MEDIA_ROOT / str(current_user.id) / "status"
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / safe_name
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    media_url = f"{current_user.id}/status/{safe_name}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    async with get_db() as db:
        status = Status(
            user_id=current_user.id,
            media_url=media_url,
            media_type=media_type,
            expires_at=expires_at,
        )
        db.add(status)
        await db.commit()
        await db.refresh(status)
        return {
            "id": status.id,
            "media_url": f"/media/{media_url}",
            "expires_at": str(expires_at),
        }

@router.get("/status/friends")
async def friends_statuses(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    stmt = select(Status).where(Status.expires_at > now).order_by(desc(Status.created_at))
    result = await db.execute(stmt)
    statuses = result.scalars().all()
    grouped = {}
    for s in statuses:
        if s.user_id == current_user.id:
            continue
        uid = s.user_id
        if uid not in grouped:
            grouped[uid] = {"user_id": uid, "username": s.user.username, "statuses": []}
        grouped[uid]["statuses"].append({
            "id": s.id,
            "media_url": f"/media/{s.media_url}",
            "media_type": s.media_type,
            "created_at": str(s.created_at),
        })
    return list(grouped.values())
