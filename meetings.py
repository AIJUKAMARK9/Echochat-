import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from database import get_db, AsyncSession
from models import User, MeetingRoom, CallParticipant
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/create")
async def create_meeting(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    room_name = uuid.uuid4().hex[:12]
    passcode = uuid.uuid4().hex[:6]
    room = MeetingRoom(
        room_name=room_name,
        passcode=passcode,
        created_by=current_user.id,
        is_active=True,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    meeting_url = f"https://{settings.JITSI_DOMAIN}/{room_name}#config.prejoinPageEnabled=true&config.passcode={passcode}"
    return {
        "room_id": room.id,
        "room_name": room_name,
        "url": meeting_url,
        "passcode": passcode,
    }

@router.post("/join/{room_id}")
async def join_meeting(
    room_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    room = await db.get(MeetingRoom, room_id)
    if not room:
        raise HTTPException(404, "Meeting not found")
    participant = CallParticipant(
        room_id=room.id,
        user_id=current_user.id,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(participant)
    await db.commit()
    return {"status": "joined", "passcode": room.passcode}

@router.post("/leave/{room_id}")
async def leave_meeting(
    room_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    room = await db.get(MeetingRoom, room_id)
    if not room:
        raise HTTPException(404)
    stmt = (
        select(CallParticipant)
        .where(
            CallParticipant.room_id == room.id,
            CallParticipant.user_id == current_user.id,
            CallParticipant.left_at == None,
        )
        .order_by(CallParticipant.joined_at.desc())
    )
    result = await db.execute(stmt)
    participant = result.scalars().first()
    if participant:
        participant.left_at = datetime.now(timezone.utc)
        await db.commit()
    # Check if any active participants remain
    active_count = await db.execute(
        select(CallParticipant).where(
            CallParticipant.room_id == room.id,
            CallParticipant.left_at == None,
        )
    )
    if not active_count.scalars().all():
        room.is_active = False
        await db.commit()
    return {"status": "left"}

@router.get("/active")
async def active_meetings(db=Depends(get_db)):
    result = await db.execute(select(MeetingRoom).where(MeetingRoom.is_active == True))
    rooms = result.scalars().all()
    output = []
    for room in rooms:
        participants = await db.execute(
            select(CallParticipant).where(
                CallParticipant.room_id == room.id,
                CallParticipant.left_at == None,
            )
        )
        participants_list = participants.scalars().all()
        output.append({
            "id": room.id,
            "room_name": room.room_name,
            "creator": room.created_by,
            "participant_count": len(participants_list),
            "url": f"https://{settings.JITSI_DOMAIN}/{room.room_name}#config.prejoinPageEnabled=true&config.passcode={room.passcode}",
        })
    return output

@router.get("/history")
async def call_history(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    stmt = (
        select(MeetingRoom, CallParticipant)
        .join(CallParticipant, MeetingRoom.id == CallParticipant.room_id)
        .where(CallParticipant.user_id == current_user.id)
        .order_by(CallParticipant.joined_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    history = []
    for room, part in rows:
        history.append({
            "room_id": room.id,
            "room_name": room.room_name,
            "joined_at": str(part.joined_at),
            "left_at": str(part.left_at) if part.left_at else None,
            "duration": (part.left_at - part.joined_at).seconds if part.left_at else None,
        })
    return history
