import hashlib
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index, select
from app.database import Base, async_session_maker


class BotConfig(Base):
    """Key-value configuration store for UI-editable settings."""
    __tablename__ = "bot_config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)


class MonitoredGroup(Base):
    """WeChat group to monitor."""
    __tablename__ = "monitored_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Admin(Base):
    """Admin user to notify."""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_name = Column(String, nullable=False)
    wechat_id = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DetectedMessage(Base):
    """Detected suspicious message record (dedup + audit trail)."""
    __tablename__ = "detected_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String, nullable=False)
    sender = Column(String, default="")
    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, index=True)
    matched_keyword = Column(String, default="")
    llm_verdict = Column(String, nullable=True)  # "malicious" | "benign" | None (unreviewed)
    is_notified = Column(Boolean, default=False, nullable=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_dedup", "group_name", "content_hash"),
    )


DEFAULT_CONFIG = {
    "monitoring_interval": "10",
    "history_message_count": "30",
    "llm_base_url": "",
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",
    "llm_max_tokens": "512",
    "llm_temperature": "0.0",
}


async def seed_default_config():
    """Insert default BotConfig records if the table is empty."""
    async with async_session_maker() as session:
        result = await session.execute(select(BotConfig).limit(1))
        if result.scalar_one_or_none():
            return
        for key, value in DEFAULT_CONFIG.items():
            session.add(BotConfig(key=key, value=value))
        await session.commit()


def make_content_hash(group_name: str, content: str) -> str:
    """Create a SHA256 hash for deduplication."""
    return hashlib.sha256(f"{group_name}|{content}".encode("utf-8")).hexdigest()
