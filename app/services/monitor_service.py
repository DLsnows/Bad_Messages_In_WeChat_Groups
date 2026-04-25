import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from sqlalchemy import select

from app.database import async_session_maker
from app.models import MonitoredGroup, DetectedMessage, make_content_hash, BotConfig
from app.config import get_keywords
from app.services.wechat_service import WeChatService
from app.services.llm_service import review_message
from app.services.notification_service import notify_admins

logger = logging.getLogger(__name__)


class MonitorService:
    """Background monitoring loop in a dedicated thread."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_running = False
        self._last_check_time: str | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def last_check_time(self) -> str | None:
        return self._last_check_time

    def start(self):
        """Start the monitoring thread."""
        if self._is_running:
            logger.warning("Monitor is already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="monitor")
        self._thread.start()
        self._is_running = True
        logger.info("")
        logger.info("========================================")
        logger.info("  Monitor started - checking groups...  ")
        logger.info("========================================")
        logger.info("")

    def stop(self):
        """Signal the monitoring thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._is_running = False
        logger.info("Monitor thread stopped")

    def _run_loop(self):
        """Main loop — runs in its own thread with a dedicated asyncio event loop."""
        # COM initialization for UI automation on Windows
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Force WeChat instance creation on this thread (COM thread affinity).
        # WeChatService is a singleton, but COM objects must be used from
        # the thread that created them. We create it here once and never
        # dispatch wxauto calls to other threads via asyncio.to_thread.
        wechat = WeChatService()
        try:
            online = wechat.is_online()
            logger.info("WeChat instance ready on monitor thread %d (online=%s)",
                        threading.current_thread().ident, online)
        except Exception as e:
            logger.error("Failed to initialize WeChat on monitor thread: %s", e)

        try:
            while not self._stop_event.is_set():
                try:
                    loop.run_until_complete(
                        asyncio.wait_for(self._check_once(), timeout=120)
                    )
                except asyncio.TimeoutError:
                    logger.error("Monitor check cycle timed out (120s), will retry")
                except Exception as e:
                    logger.error("Monitor check error: %s", e, exc_info=True)
                finally:
                    # Always update last check time so frontend shows activity
                    self._last_check_time = time.strftime("%Y-%m-%d %H:%M:%S")

                # Get interval from DB config, sleep in small chunks for responsive stop
                try:
                    interval = loop.run_until_complete(self._get_interval())
                except Exception:
                    interval = 10

                for _ in range(interval):
                    if self._stop_event.wait(1):
                        break
        finally:
            loop.close()
            try:
                import comtypes
                comtypes.CoUninitialize()
            except Exception:
                pass

    async def _get_interval(self) -> int:
        """Read monitoring interval from DB config."""
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(BotConfig).where(BotConfig.key == "monitoring_interval")
                )
                row = result.scalar_one_or_none()
                if row and row.value:
                    return max(5, int(row.value))
        except Exception:
            pass
        return 10

    async def _get_history_count(self) -> int:
        """Read history message count from DB config."""
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(BotConfig).where(BotConfig.key == "history_message_count")
                )
                row = result.scalar_one_or_none()
                if row and row.value:
                    return max(5, int(row.value))
        except Exception:
            pass
        return 30

    async def _get_llm_config(self) -> dict:
        """Build LLM config dict from DB and env."""
        from app.config import get_env_config, get_db_config, build_config_dict

        env_config = get_env_config()
        async with async_session_maker() as session:
            db_config = await get_db_config(session)
        return build_config_dict(db_config, env_config)

    async def _check_once(self):
        """One full monitoring cycle: check all active groups."""
        logger.info("[Monitor] ====== Checking cycle started =====")

        keywords = get_keywords()
        if not keywords:
            logger.warning("[Monitor] No keywords configured, skipping check")
            return

        async with async_session_maker() as session:
            result = await session.execute(
                select(MonitoredGroup).where(MonitoredGroup.is_active == True)
            )
            groups = result.scalars().all()

        if not groups:
            logger.warning("[Monitor] No active groups to monitor")
            return

        logger.info("[Monitor] Checking %d groups with %d keywords", len(groups), len(keywords))

        llm_config = await self._get_llm_config()
        wechat = WeChatService()
        history_count = await self._get_history_count()

        for group in groups:
            if self._stop_event.is_set():
                break
            try:
                await self._check_group(
                    group.group_name, keywords, llm_config, wechat, history_count
                )
            except Exception as e:
                logger.error("Error checking group '%s': %s", group.group_name, e)
            time.sleep(0.3)

    async def _check_group(
        self,
        group_name: str,
        keywords: list[str],
        llm_config: dict,
        wechat: WeChatService,
        history_count: int,
    ):
        """Check messages in a single group."""
        # Sync wxauto call — must run on the monitor thread (COM thread affinity), NOT via asyncio.to_thread
        messages = wechat.get_recent_messages(group_name, history_count)

        if not messages:
            logger.warning("[DEBUG] Group '%s': GetAllMessage returned empty list", group_name)
            return

        logger.info("[DEBUG] Group '%s': fetched %d messages, scanning with %d keywords",
                     group_name, len(messages), len(keywords))

        for idx, msg in enumerate(messages):
            if self._stop_event.is_set():
                break

            try:
                all_attrs = dir(msg)
                content = getattr(msg, "content", "") or ""
                sender = getattr(msg, "sender", "") or ""
                msg_attr = getattr(msg, "attr", "")   # source: self/friend/system/time
                msg_type = getattr(msg, "type", "")   # content: text/image/video/...
                msg_id_raw = getattr(msg, "id", None)
                # wxauto may return non-numeric ids for UI dividers like "2条未读"
                msg_id = str(msg_id_raw) if msg_id_raw is not None else None
            except Exception as e:
                logger.debug("[DEBUG] msg#%d: failed to read attributes: %s", idx, e)
                continue

            # Log first 3 messages' debug info to help diagnose issues
            if idx < 3:
                logger.info(
                    "[DEBUG] msg#%d attr=%s type=%s sender='%s' content_preview='%s' id=%s",
                    idx, msg_attr, msg_type, sender, content[:60], msg_id,
                )

            # Skip system messages, self-sent messages, and empty content
            if msg_attr == "self" or msg_attr == "system" or not content:
                if idx < 3:
                    logger.info("[DEBUG] msg#%d skipped: attr=%s has_content=%s", idx, msg_attr, bool(content))
                continue

            # Keyword matching (case-insensitive)
            matched_keyword = None
            content_lower = content.lower()
            for kw in keywords:
                if kw.lower() in content_lower:
                    matched_keyword = kw
                    break

            if not matched_keyword:
                continue

            # === KEYWORD MATCHED ===
            logger.warning(
                "!!!!!!!!!! [KEYWORD HIT] Group=%s Sender=%s Keyword=[%s] Content=[%s]",
                group_name, sender, matched_keyword, content[:120],
            )

            # Dedup: check if this message has been processed before
            content_hash = make_content_hash(group_name, content)
            async with async_session_maker() as session:
                existing = await session.execute(
                    select(DetectedMessage).where(
                        DetectedMessage.content_hash == content_hash,
                        DetectedMessage.group_name == group_name,
                    )
                )
                if existing.scalar_one_or_none():
                    logger.debug("Duplicate message skipped in %s: %s", group_name, content[:50])
                    continue

                # Insert preliminary record
                detected = DetectedMessage(
                    group_name=group_name,
                    sender=sender,
                    content=content,
                    content_hash=content_hash,
                    matched_keyword=matched_keyword,
                    llm_verdict=None,
                    is_notified=False,
                    detected_at=datetime.now(timezone.utc),
                )
                session.add(detected)
                await session.commit()

            # LLM review
            YELLOW = "\033[33m"
            RED = "\033[31m"
            RESET = "\033[0m"

            logger.warning(
                "%s[LLM REVIEW] Sending message to LLM for review...%s Group=%s Sender=%s Keyword=[%s] Content=[%s]",
                YELLOW, RESET, group_name, sender, matched_keyword, content[:120],
            )
            verdict = await review_message(group_name, sender, content, llm_config)

            # Update record with verdict
            async with async_session_maker() as session:
                result = await session.execute(
                    select(DetectedMessage).where(
                        DetectedMessage.content_hash == content_hash,
                        DetectedMessage.group_name == group_name,
                    )
                )
                detected = result.scalar_one()
                detected.llm_verdict = verdict
                await session.commit()

            # Notify if malicious
            if verdict == "malicious":
                logger.warning(
                    "%s[LLM VERDICT] MALICIOUS — notifying admins%s Group=%s Sender=%s Content=[%s]",
                    RED, RESET, group_name, sender, content[:100],
                )
                # PAUSE: scanning suspended while sending notifications (avoid UI conflicts)
                notified = await notify_admins(group_name, sender, content, matched_keyword)

                if notified:
                    async with async_session_maker() as session:
                        result = await session.execute(
                            select(DetectedMessage).where(
                                DetectedMessage.content_hash == content_hash,
                                DetectedMessage.group_name == group_name,
                            )
                        )
                        detected = result.scalar_one()
                        detected.is_notified = True
                        await session.commit()
                    logger.info(
                        "%s[NOTIFY DONE] Notifications sent, resuming scanning%s",
                        YELLOW, RESET,
                    )
                else:
                    logger.error(
                        "%s[NOTIFY FAILED] could not send notifications — message NOT marked as notified%s",
                        RED, RESET,
                    )
                # Extra pause after notifications so wxauto UI settles
                time.sleep(1.0)
            else:
                logger.warning(
                    "%s[LLM VERDICT] %s — no action taken%s Group=%s Sender=%s",
                    YELLOW, (verdict or "unreviewable").upper(), RESET, group_name, sender,
                )

            # Brief pause between messages to avoid UI hammering
            time.sleep(0.3)
