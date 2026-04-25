import threading
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
                    cls._instance._wx_lock = threading.Lock()
        return cls._instance

    def _ensure_com(self):
        """Initialize COM for the current thread (needed when called from thread-pool threads)."""
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

    def _get_wx(self):
        """Lazy-init WeChat instance."""
        if self._wx is None:
            with self._wx_lock:
                if self._wx is None:
                    self._ensure_com()
                    try:
                        self._wx = WeChat()
                        logger.info("WeChat instance created")
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
        """Get recent messages from a group (scrolls up to fetch history)."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(group_name)
            return wx.GetHistoryMessage(count)

    def get_all_messages(self, group_name: str) -> list:
        """Get all currently visible messages in the chat window."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(group_name)
            return wx.GetAllMessage()

    def send_group_message(self, group_name: str, message: str, at: list[str] = None):
        """Send a message to a group, optionally @mentioning members."""
        self._ensure_com()
        with self._wx_lock:
            wx = self._get_wx()
            wx.ChatWith(group_name)
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
            wx.SendMsg(message)

    def is_online(self) -> bool:
        """Check if WeChat is online."""
        self._ensure_com()
        try:
            with self._wx_lock:
                wx = self._get_wx()
                return wx.IsOnline()
        except Exception:
            return False
