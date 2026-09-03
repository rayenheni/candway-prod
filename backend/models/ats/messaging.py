"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Conversation(Base, TenantMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conv_updated", "last_message_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(255), nullable=True)
    type = Column(String(20), default="direct")  # "direct" or "group"
    last_message_at = Column(DateTime, default=utcnow, index=True)
    last_message_preview = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    participants = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class ConversationParticipant(Base, TenantMixin):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        Index("idx_cp_user_conv", "user_id", "conversation_id", unique=True),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), default="member")
    last_read_at = Column(DateTime, default=utcnow)
    is_muted = Column(Boolean, default=False)
    left_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User")


class Message(Base, TenantMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_msg_conv", "conversation_id", "created_at"),
        Index("idx_msg_sender", "sender_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True
    )
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), default="text")
    attachments = Column(Text, nullable=True)  # JSON array
    reply_to_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    edited_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    reply_to = relationship("Message", remote_side=[id], backref="replies")


# ============================================================================
# RECRUITER PLATFORM ENHANCEMENTS (v5.0)
# ============================================================================
