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
):
    """
    Notify all active admins about a confirmed malicious message.

    1. ONE group message @mentioning ALL admins at once
    2. Send each admin a private DM with full details (after verifying chat switch)
    """
    admins = await get_active_admins()
    if not admins:
        logger.warning("No active admins configured, skipping notification")
        return

    wechat = WeChatService()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. ONE group message @mentioning ALL admins at once
    admin_names = [name for name, _ in admins]
    try:
        wechat.send_group_message(group_name, "", at=admin_names)
        logger.info("Sent @mention to %d admins in group %s", len(admin_names), group_name)
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
            target = wechat_id if wechat_id else admin_name
            sent = wechat.send_private_message_with_check(target, dm_text)
            if sent:
                logger.info("DM sent to %s", target)
            else:
                logger.error("Failed to send DM to %s: chat switch verification failed", target)
        except Exception as e:
            logger.error("Failed to DM %s: %s", admin_name, e)
