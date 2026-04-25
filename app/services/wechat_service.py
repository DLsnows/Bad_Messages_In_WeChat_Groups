import threading
import time
import logging
from wxauto4 import WeChat

logger = logging.getLogger(__name__)


class WeChatService:
    """Thread-safe singleton wrapper around wxauto WeChat."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._wx = None
                    cls._instance._wx_lock = threading.RLock()
                    cls._instance._wx_owner_thread = None
        return cls._instance

    def _ensure_com(self):
        """Initialize COM for the current thread (needed when called from thread-pool threads)."""
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

    def _get_wx(self):
        """Lazy-init WeChat instance. Must only be used from the thread that created it (COM thread affinity)."""
        current_thread = threading.current_thread().ident
        if self._wx is not None and self._wx_owner_thread != current_thread:
            logger.warning(
                "WeChat accessed from thread %d but owned by thread %d — COM calls may fail!",
                current_thread, self._wx_owner_thread,
            )
        if self._wx is None:
            with self._wx_lock:
                if self._wx is None:
                    self._ensure_com()
                    try:
                        self._wx = WeChat()
                        self._wx_owner_thread = threading.current_thread().ident
                        logger.info("WeChat instance created on thread %d", self._wx_owner_thread)
                    except Exception as e:
                        logger.error("Failed to create WeChat instance: %s", e)
                        raise
        return self._wx

    def get_session_list(self) -> list:
        """Get list of current WeChat sessions (conversations)."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            return wx.GetSession()

    def chat_with(self, name: str):
        """Open a chat window with a contact or group."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(name)

    def get_recent_messages(self, group_name: str, count: int = 30) -> list:
        """Get recent messages from a group."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(group_name)
            time.sleep(0.3)
            # Verify the chat window actually switched
            info = wx.ChatInfo()
            actual_name = info.get("chat_name", "") if isinstance(info, dict) else str(info)
            logger.info("ChatWith('%s') -> actual chat: '%s'", group_name, actual_name)
            if group_name not in str(actual_name):
                logger.warning(
                    "ChatWith('%s') may have failed — current chat is '%s'. "
                    "Group name may not match any WeChat conversation.",
                    group_name, actual_name,
                )
            time.sleep(0.3)
            # GetAllMessage is the documented API (GetHistoryMessage does not exist)
            try:
                msgs = wx.GetAllMessage()
            except Exception as e:
                logger.error("GetAllMessage failed for group '%s': %s", group_name, e)
                return []
            logger.info("Group '%s': GetAllMessage returned %d messages", group_name, len(msgs))
            return msgs[-count:] if len(msgs) > count else msgs

    def get_all_messages(self, group_name: str) -> list:
        """Get all currently visible messages in the chat window."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(group_name)
            time.sleep(0.3)
            return wx.GetAllMessage()

    def send_group_message(self, group_name: str, message: str, at: list[str] = None):
        """Send a message to a group, optionally @mentioning members."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(group_name)
            time.sleep(0.3)
            if at:
                wx.SendMsg(message, at=at)
            else:
                wx.SendMsg(message)

    def send_private_message(self, target_name: str, message: str):
        """Send a private message to a contact or WeChat ID."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(target_name)
            time.sleep(0.3)
            wx.SendMsg(message)

    def send_private_message_with_check(self, target_name: str, message: str) -> bool:
        """Send a private message with chat-switch verification (retry up to 3 times).
        Only sends the message if ChatWith actually switched to the target's private chat.
        Returns True if sent, False if all retries failed.
        """
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            for attempt in range(1, 4):
                wx.ChatWith(target_name)
                time.sleep(0.3)
                info = wx.ChatInfo()
                actual_name = info.get("chat_name", "") if isinstance(info, dict) else str(info)
                if target_name in str(actual_name) or str(actual_name) in target_name:
                    wx.SendMsg(message)
                    logger.info("DM sent to %s (verified chat='%s')", target_name, actual_name)
                    return True
                logger.warning(
                    "DM attempt %d/3: ChatWith('%s') switched to '%s', retrying...",
                    attempt, target_name, actual_name,
                )
                time.sleep(0.3)
            logger.error(
                "Cannot DM: ChatWith('%s') failed after 3 attempts — message NOT sent",
                target_name,
            )
            return False

    def is_online(self) -> bool:
        """Check if WeChat is online."""
        self._ensure_com()
        try:
            with self._wx_lock:
                wx = self._get_wx()
                return wx.IsOnline()
        except Exception:
            return False
