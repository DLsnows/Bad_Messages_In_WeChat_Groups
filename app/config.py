import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import select
from app.models import BotConfig

PROJECT_DIR = Path(__file__).resolve().parent.parent
KEYWORDS_PATH = PROJECT_DIR / "keywords.txt"
ENV_PATH = PROJECT_DIR / ".env"

# Config key constants
KEY_MONITORING_INTERVAL = "monitoring_interval"
KEY_HISTORY_MESSAGE_COUNT = "history_message_count"
KEY_LLM_BASE_URL = "llm_base_url"
KEY_LLM_API_KEY = "llm_api_key"
KEY_LLM_MODEL = "llm_model"
KEY_LLM_MAX_TOKENS = "llm_max_tokens"
KEY_LLM_TEMPERATURE = "llm_temperature"


def get_env_config() -> dict:
    """Load LLM credentials from .env file (if present)."""
    load_dotenv(ENV_PATH)
    config = {}
    if base_url := os.getenv("LLM_BASE_URL"):
        config["llm_base_url"] = base_url
    if api_key := os.getenv("LLM_API_KEY"):
        config["llm_api_key"] = api_key
    if model := os.getenv("LLM_MODEL"):
        config["llm_model"] = model
    return config


def get_keywords() -> list[str]:
    """Read keywords from keywords.txt, one per line."""
    if not KEYWORDS_PATH.exists():
        KEYWORDS_PATH.write_text("# One keyword per line.\n", encoding="utf-8")
        return []
    lines = KEYWORDS_PATH.read_text(encoding="utf-8").splitlines()
    keywords = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            keywords.append(stripped)
    return keywords


def save_keywords(keywords: list[str]) -> None:
    """Write keywords to keywords.txt, one per line."""
    lines = ["# One keyword per line. Lines starting with # are comments.\n"]
    for kw in keywords:
        lines.append(kw.strip() + "\n")
    KEYWORDS_PATH.write_text("".join(lines), encoding="utf-8")


async def get_db_config(session) -> dict:
    """Read all BotConfig records from DB into a dict."""
    result = await session.execute(select(BotConfig))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows if row.value is not None}


def apply_env_overrides(merged: dict, env_config: dict) -> dict:
    """Apply .env values on top of DB values (env takes precedence)."""
    for key in ("llm_base_url", "llm_api_key", "llm_model"):
        if key in env_config:
            merged[key] = env_config[key]
    # Ensure defaults for missing keys
    merged.setdefault("llm_base_url", "")
    merged.setdefault("llm_api_key", "")
    merged.setdefault("llm_model", "gpt-4o-mini")
    merged.setdefault("llm_max_tokens", "512")
    merged.setdefault("llm_temperature", "0.0")
    merged.setdefault("monitoring_interval", "10")
    merged.setdefault("history_message_count", "30")
    return merged


def build_config_dict(db_config: dict, env_config: dict) -> dict:
    """Merge DB config with env overrides and coerce types."""
    merged = dict(db_config)
    merged.update(env_config)  # env takes precedence

    # Apply defaults for anything missing
    merged.setdefault("llm_base_url", "")
    merged.setdefault("llm_api_key", "")
    merged.setdefault("llm_model", "gpt-4o-mini")
    merged.setdefault("llm_max_tokens", "512")
    merged.setdefault("llm_temperature", "0.0")
    merged.setdefault("monitoring_interval", "10")
    merged.setdefault("history_message_count", "30")

    # Type coercion
    if isinstance(merged.get("monitoring_interval"), str):
        merged["monitoring_interval"] = int(merged["monitoring_interval"])
    if isinstance(merged.get("history_message_count"), str):
        merged["history_message_count"] = int(merged["history_message_count"])
    if isinstance(merged.get("llm_max_tokens"), str):
        merged["llm_max_tokens"] = int(merged["llm_max_tokens"])
    if isinstance(merged.get("llm_temperature"), str):
        merged["llm_temperature"] = float(merged["llm_temperature"])

    return merged
