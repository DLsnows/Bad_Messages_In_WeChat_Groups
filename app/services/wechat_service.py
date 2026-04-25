import threading
import time
import logging
from wxauto import WeChat

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
            wx.ChatWith(who=name)

    def _get_chat(self, name: str):
        """Get a Chat sub-window object after ChatWith. Returns None if not found."""
        wx = self._get_wx()
        try:
            chat = wx.GetSubWindow(name)
            return chat
        except Exception:
            return None

    def get_recent_messages(self, group_name: str, count: int = 30) -> list:
        """Get recent messages from a group."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(who=group_name)
            time.sleep(1.0)
            # Verify the chat window actually switched
            chat = self._get_chat(group_name)
            if chat:
                actual_name = chat.who
                logger.info("ChatWith('%s') -> actual chat: '%s'", group_name, actual_name)
                if group_name not in str(actual_name):
                    logger.warning(
                        "ChatWith('%s') may have failed — current chat is '%s'. "
                        "Group name may not match any WeChat conversation.",
                        group_name, actual_name,
                    )
            time.sleep(0.3)
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
            wx.ChatWith(who=group_name)
            time.sleep(0.3)
            return wx.GetAllMessage()

    def send_group_message(self, group_name: str, message: str, at: list[str] = None):
        """Send a message to a group, optionally @mentioning members."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.SendMsg(message, who=group_name, at=at)

    def send_private_message(self, target_name: str, message: str):
        """Send a private message to a contact or WeChat ID."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.SendMsg(message, who=target_name)

    def send_private_message_with_check(self, target_name: str, message: str) -> bool:
        """Send a private message. Uses SendMsg(who=) directly (wxauto handles the
        window switch internally — no unreliable ChatWith/GetSubWindow verification).
        Returns True (exceptions propagate to caller for logging).
        """
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.SendMsg(message, who=target_name)
            logger.info("DM sent to %s", target_name)
            return True

    def is_online(self) -> bool:
        """Check if WeChat is online."""
        self._ensure_com()
        try:
            with self._wx_lock:
                wx = self._get_wx()
                return wx.IsOnline()
        except Exception:
            return False
