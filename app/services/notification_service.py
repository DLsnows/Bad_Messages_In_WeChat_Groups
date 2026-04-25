import logging
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

    1. @mention each admin in the group with a short alert
    2. Send each admin a private DM with full details
    """
    admins = await get_active_admins()
    if not admins:
        logger.warning("No active admins configured, skipping notification")
        return

    wechat = WeChatService()
    preview = content[:100]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for admin_name, wechat_id in admins:
        try:
            # 1. @mention in group
            wechat.send_group_message(
                group_name,
                f"@{admin_name} 检测到可疑消息 匹配关键词: [{matched_keyword}]\n"
                f"发送者: {sender}\n内容预览: {preview}",
                at=[admin_name],
            )
            logger.info("Sent @mention to %s in group %s", admin_name, group_name)
        except Exception as e:
            logger.error("Failed to @mention %s in group %s: %s", admin_name, group_name, e)

        try:
            # 2. Private DM with full details
            dm_text = (
                f"[可疑消息提醒]\n"
                f"群聊: {group_name}\n"
                f"发送者: {sender}\n"
                f"匹配关键词: {matched_keyword}\n"
                f"消息内容: {content}\n"
                f"检测时间: {timestamp}"
            )
            # Use wechat_id if available, otherwise fall back to admin_name
            target = wechat_id if wechat_id else admin_name
            wechat.send_private_message(target, dm_text)
            logger.info("Sent DM to %s", target)
        except Exception as e:
            logger.error("Failed to DM %s: %s", admin_name, e)
