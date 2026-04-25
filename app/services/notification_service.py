import logging
import time
from datetime import datetime
from sqlalchemy import select
from app.database import async_session_maker
from app.models import Admin
from app.services.wechat_service import WeChatService

logger = logging.getLogger(__name__)


async def get_active_admins() -> list[tuple[str, str]]:
    """Fetch active admins from DB. Returns list of (admin_name, wechat_id)."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Admin).where(Admin.is_active == True)
        )
        admins = result.scalars().all()
        return [(a.admin_name, a.wechat_id) for a in admins]


async def notify_admins(
    group_name: str,
    sender: str,
    content: str,
    matched_keyword: str,
) -> bool:
    """
    Notify all active admins about a confirmed malicious message.

    1. ONE group message @mentioning ALL admins at once
    2. Send each admin a private DM with full details (after verifying chat switch)

    Returns True if at least the group @mention was sent.
    """
    admins = await get_active_admins()
    if not admins:
        logger.warning("No active admins configured, skipping notification")
        return False

    wechat = WeChatService()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overall_success = False

    # 1. ONE group message @mentioning ALL admins at once
    admin_names = [name for name, _ in admins]
    try:
        wechat.send_group_message(group_name, "", at=admin_names)
        logger.info("Sent @mention to %d admins in group %s", len(admin_names), group_name)
        overall_success = True
    except Exception as e:
        logger.error("Failed to @mention admins in group %s: %s", group_name, e)

    time.sleep(0.3)

    # 2. Private DM to each admin with full details (verify chat switched first)
    dm_text = (
        f"[可疑消息提醒]\n"
        f"群聊: {group_name}\n"
        f"发送者: {sender}\n"
        f"匹配关键词: {matched_keyword}\n"
        f"消息内容: {content}\n"
        f"检测时间: {timestamp}"
    )

    for admin_name, wechat_id in admins:
        try:
            sent = wechat.send_private_message_with_check(wechat_id, dm_text)
            if sent:
                logger.info("DM sent to %s", wechat_id)
            else:
                logger.error("Failed to send DM to %s: chat switch verification failed", wechat_id)
        except Exception as e:
            logger.error("Failed to DM %s: %s", admin_name, e)

    return overall_success
