"""Entry point: auto-find port, open browser, start uvicorn."""

import logging
import os
import socket
import sys
import webbrowser
from pathlib import Path

import uvicorn

# Ensure project root is in Python path
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run")


def find_free_port(start: int = 8000, max_attempts: int = 100) -> int:
    """Try ports starting from `start`, return the first available one."""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(
        f"No free port found in range [{start}, {start + max_attempts})"
    )


def check_env() -> bool:
    """Check if .env exists. If not, create from .env.example and warn."""
    env_path = PROJECT_DIR / ".env"
    example_path = PROJECT_DIR / ".env.example"
    if env_path.exists():
        return True
    if example_path.exists():
        logger.warning(".env 文件不存在，正在从 .env.example 创建...")
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        print()
        print("=" * 60)
        print("  [!] 请先编辑 .env 文件，填入你的 LLM API 配置！")
        print(f"      文件路径: {env_path}")
        print("=" * 60)
        print()
        return False
    logger.error(".env.example 也不存在，无法创建 .env 文件")
    return False


def main():
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    logger.info("找到空闲端口: %d", port)
    logger.info("正在启动浏览器: %s", url)

    # Open browser after a short delay so the server is likely ready
    import threading

    def _open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(url)
        logger.info("浏览器已打开: %s", url)

    threading.Thread(target=_open_browser, daemon=True).start()

    logger.info("启动 uvicorn...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
