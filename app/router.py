import math
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models import (
    MonitoredGroup, Admin, DetectedMessage, BotConfig, make_content_hash, seed_default_config
)
from app.schemas import (
    ApiResponse, BotStatusResponse,
    ConfigResponse, ConfigUpdate,
    KeywordList,
    MonitoredGroupCreate, MonitoredGroupResponse,
    AdminCreate, AdminResponse,
    DetectedMessageResponse, DetectedMessageList,
    WeChatSessionResponse,
)
from app.config import get_keywords, save_keywords, get_env_config, get_db_config, build_config_dict
from app.services.monitor_service import MonitorService

router = APIRouter(prefix="/api/v1")


def get_monitor(request: Request) -> MonitorService:
    """Dependency: get MonitorService from app state."""
    return request.app.state.monitor


# ─── Status ───────────────────────────────────────────────────────────

@router.get("/status", response_model=BotStatusResponse)
async def get_status(
    monitor: MonitorService = Depends(get_monitor),
    db: AsyncSession = Depends(get_db),
):
    """Get bot status: running state, counts, last check time."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    groups_count = (
        await db.execute(select(func.count(MonitoredGroup.id)).where(MonitoredGroup.is_active == True))
    ).scalar() or 0
    admins_count = (
        await db.execute(select(func.count(Admin.id)).where(Admin.is_active == True))
    ).scalar() or 0
    detected_today = (
        await db.execute(
            select(func.count(DetectedMessage.id)).where(DetectedMessage.detected_at >= today_start)
        )
    ).scalar() or 0

    return BotStatusResponse(
        is_running=monitor.is_running,
        last_check_time=monitor.last_check_time,
        monitored_groups_count=groups_count,
        admins_count=admins_count,
        detected_today=detected_today,
    )


# ─── Bot Control ──────────────────────────────────────────────────────

@router.post("/bot/start", response_model=ApiResponse)
async def bot_start(monitor: MonitorService = Depends(get_monitor)):
    """Start the monitoring loop."""
    if monitor.is_running:
        return ApiResponse(success=True, message="Monitor is already running")
    monitor.start()
    return ApiResponse(success=True, message="Monitor started")


@router.post("/bot/stop", response_model=ApiResponse)
async def bot_stop(monitor: MonitorService = Depends(get_monitor)):
    """Stop the monitoring loop."""
    if not monitor.is_running:
        return ApiResponse(success=True, message="Monitor is already stopped")
    monitor.stop()
    return ApiResponse(success=True, message="Monitor stopped")


# ─── Config ───────────────────────────────────────────────────────────

@router.get("/config", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    """Get merged configuration (DB + env overrides)."""
    env_config = get_env_config()
    db_config = await get_db_config(db)
    merged = build_config_dict(db_config, env_config)

    return ConfigResponse(
        monitoring_interval=merged.get("monitoring_interval", 10),
        history_message_count=merged.get("history_message_count", 30),
        llm_base_url=merged.get("llm_base_url", ""),
        llm_model=merged.get("llm_model", "gpt-4o-mini"),
        llm_max_tokens=merged.get("llm_max_tokens", 512),
        llm_temperature=merged.get("llm_temperature", 0.0),
        has_api_key=bool(merged.get("llm_api_key")),
    )


@router.put("/config", response_model=ApiResponse)
async def update_config(update: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Update configuration values in DB."""
    updates = update.model_dump(exclude_none=True, exclude_unset=True)

    # Normalize field names to DB keys
    field_map = {
        "monitoring_interval": "monitoring_interval",
        "history_message_count": "history_message_count",
        "llm_base_url": "llm_base_url",
        "llm_api_key": "llm_api_key",
        "llm_model": "llm_model",
        "llm_max_tokens": "llm_max_tokens",
        "llm_temperature": "llm_temperature",
    }

    for field, value in updates.items():
        db_key = field_map.get(field)
        if db_key is None:
            continue
        # Upsert
        result = await db.execute(select(BotConfig).where(BotConfig.key == db_key))
        config_row = result.scalar_one_or_none()
        if config_row:
            config_row.value = str(value)
        else:
            db.add(BotConfig(key=db_key, value=str(value)))

    await db.commit()
    return ApiResponse(success=True, message="Config updated")


# ─── Keywords ─────────────────────────────────────────────────────────

@router.get("/config/keywords", response_model=KeywordList)
async def get_keywords_endpoint():
    """Get keywords from keywords.txt."""
    return KeywordList(keywords=get_keywords())


@router.put("/config/keywords", response_model=ApiResponse)
async def update_keywords(data: KeywordList):
    """Save keywords to keywords.txt."""
    save_keywords(data.keywords)
    return ApiResponse(success=True, message=f"Saved {len(data.keywords)} keywords")


# ─── Monitored Groups ─────────────────────────────────────────────────

@router.get("/groups", response_model=list[MonitoredGroupResponse])
async def list_groups(db: AsyncSession = Depends(get_db)):
    """List all monitored groups."""
    result = await db.execute(select(MonitoredGroup).order_by(MonitoredGroup.created_at.desc()))
    return result.scalars().all()


@router.post("/groups", response_model=MonitoredGroupResponse, status_code=201)
async def create_group(data: MonitoredGroupCreate, db: AsyncSession = Depends(get_db)):
    """Add a new group to monitor."""
    # Check duplicate
    existing = await db.execute(
        select(MonitoredGroup).where(MonitoredGroup.group_name == data.group_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Group already exists")

    group = MonitoredGroup(group_name=data.group_name, is_active=True)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/groups/{group_id}", response_model=ApiResponse)
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a monitored group."""
    result = await db.execute(select(MonitoredGroup).where(MonitoredGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()
    return ApiResponse(success=True, message="Group deleted")


@router.patch("/groups/{group_id}/toggle", response_model=MonitoredGroupResponse)
async def toggle_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle is_active status of a group."""
    result = await db.execute(select(MonitoredGroup).where(MonitoredGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    group.is_active = not group.is_active
    await db.commit()
    await db.refresh(group)
    return group


# ─── Admins ───────────────────────────────────────────────────────────

@router.get("/admins", response_model=list[AdminResponse])
async def list_admins(db: AsyncSession = Depends(get_db)):
    """List all admins."""
    result = await db.execute(select(Admin).order_by(Admin.created_at.desc()))
    return result.scalars().all()


@router.post("/admins", response_model=AdminResponse, status_code=201)
async def create_admin(data: AdminCreate, db: AsyncSession = Depends(get_db)):
    """Add a new admin."""
    admin = Admin(admin_name=data.admin_name, wechat_id=data.wechat_id, is_active=True)
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


@router.delete("/admins/{admin_id}", response_model=ApiResponse)
async def delete_admin(admin_id: int, db: AsyncSession = Depends(get_db)):
    """Remove an admin."""
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    await db.delete(admin)
    await db.commit()
    return ApiResponse(success=True, message="Admin deleted")


@router.patch("/admins/{admin_id}/toggle", response_model=AdminResponse)
async def toggle_admin(admin_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle is_active status of an admin."""
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    admin.is_active = not admin.is_active
    await db.commit()
    await db.refresh(admin)
    return admin


# ─── Detected Messages ────────────────────────────────────────────────

@router.get("/detected-messages", response_model=DetectedMessageList)
async def list_detected_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group_name: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List detected messages with pagination and filters."""
    query = select(DetectedMessage).order_by(DetectedMessage.detected_at.desc())
    count_query = select(func.count(DetectedMessage.id))

    if group_name:
        query = query.where(DetectedMessage.group_name == group_name)
        count_query = count_query.where(DetectedMessage.group_name == group_name)
    if verdict:
        query = query.where(DetectedMessage.llm_verdict == verdict)
        count_query = count_query.where(DetectedMessage.llm_verdict == verdict)

    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return DetectedMessageList(
        items=[DetectedMessageResponse.model_validate(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ─── WeChat Sessions ──────────────────────────────────────────────────

@router.get("/wechat/sessions", response_model=list[WeChatSessionResponse])
async def list_wechat_sessions():
    """Get current WeChat conversation list."""
    from app.services.wechat_service import WeChatService
    try:
        wechat = WeChatService()
        sessions = wechat.get_session_list()
        # wxauto returns SessionElement objects with .name, .time, .content, etc.
        result = []
        for s in sessions:
            if isinstance(s, str):
                result.append(WeChatSessionResponse(name=s, chat_type=""))
            elif isinstance(s, dict):
                result.append(WeChatSessionResponse(
                    name=s.get("name", s.get("nickname", str(s))),
                    chat_type=s.get("type", ""),
                ))
            elif hasattr(s, "name"):
                result.append(WeChatSessionResponse(name=s.name, chat_type=""))
            else:
                result.append(WeChatSessionResponse(name=str(s), chat_type=""))
        return result
    except Exception as e:
        logger = None
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Failed to get WeChat sessions: %s", e)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=f"WeChat not available: {e}")
