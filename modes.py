import uuid
from datetime import datetime, timezone
from sqlalchemy import (Column, Integer, String, ForeignKey, Text,
                        DateTime, Boolean, Table, Date)
from sqlalchemy.orm import relationship
from database import Base

def gen_uuid():
    return str(uuid.uuid4())

group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", String, ForeignKey("groups.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role", String, default="member"),
    Column("joined_at", DateTime, default=lambda: datetime.now(timezone.utc))
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    messages = relationship("Message", back_populates="sender")
    reels = relationship("Reel", back_populates="user")
    statuses = relationship("Status", back_populates="user")
    live_streams = relationship("LiveStream", back_populates="user")

class AIUsage(Base):
    __tablename__ = "ai_usage"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    count = Column(Integer, default=0)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=gen_uuid)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    aes_key = Column(String(44))
    messages = relationship("Message", back_populates="conversation")

class Group(Base):
    __tablename__ = "groups"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    aes_key = Column(String(44))
    members = relationship("User", secondary=group_members, backref="groups")
    messages = relationship("Message", back_populates="group")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    group_id = Column(String, ForeignKey("groups.id"), nullable=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    encrypted_content = Column(Text, nullable=False)
    nonce = Column(String(24), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sender = relationship("User", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")
    group = relationship("Group", back_populates="messages")

class Reel(Base):
    __tablename__ = "reels"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    media_url = Column(String, nullable=False)
    caption = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    likes = Column(Integer, default=0)
    views = Column(Integer, default=0)
    user = relationship("User", back_populates="reels")

class Status(Base):
    __tablename__ = "statuses"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    media_url = Column(String, nullable=False)
    media_type = Column(String, default="image")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    user = relationship("User", back_populates="statuses")

class LiveStream(Base):
    __tablename__ = "live_streams"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    stream_key = Column(String, unique=True, nullable=False)
    is_live = Column(Boolean, default=False)
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    hls_url = Column(String, nullable=True)
    user = relationship("User", back_populates="live_streams")

class MeetingRoom(Base):
    __tablename__ = "meeting_rooms"
    id = Column(String, primary_key=True, default=gen_uuid)
    room_name = Column(String, unique=True, nullable=False)
    passcode = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    participants = relationship("CallParticipant", back_populates="room")

class CallParticipant(Base):
    __tablename__ = "call_participants"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("meeting_rooms.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    left_at = Column(DateTime, nullable=True)
    room = relationship("MeetingRoom", back_populates="participants")
    user = relationship("User")
