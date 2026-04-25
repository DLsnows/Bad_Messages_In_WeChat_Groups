import logging
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

REVIEW_PROMPT = (
    "You are monitoring a WeChat group chat for inappropriate content.\n"
    "Group: {group_name}\n"
    "Sender: {sender}\n"
    "Message content: {content}\n\n"
    "Determine if this message is malicious or benign. Malicious includes: "
    "spam, phishing, fraud, scams, NSFW content, harassment, illegal content, "
    "excessive advertising, or malicious links.\n\n"
    "Reply with exactly one word: \"malicious\" or \"benign\"."
)


async def review_message(
    group_name: str, sender: str, content: str, config: dict, session: aiohttp.ClientSession = None
) -> str | None:
    """
    Send message to LLM for review.

    Returns:
        "malicious" - message is harmful
        "benign" - message is safe
        None - error occurred (API unreachable, timeout, etc.)
    """
    base_url = config.get("llm_base_url", "").rstrip("/")
    api_key = config.get("llm_api_key", "")
    model = config.get("llm_model", "gpt-4o-mini")

    if not base_url or not api_key:
        logger.warning("LLM base_url or api_key not configured, skipping review")
        return None

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        prompt = REVIEW_PROMPT.format(group_name=group_name, sender=sender, content=content[:2000])

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": int(config.get("llm_max_tokens", 10)),
            "temperature": float(config.get("llm_temperature", 0.0)),
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with session.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error("LLM API error %d: %s", resp.status, text[:200])
                return None
            data = await resp.json()
            result = data["choices"][0]["message"]["content"].strip().lower()
            # Only return "malicious" if the model clearly says malicious
            # AND does NOT also mention "benign" (avoid false positives)
            if "malicious" in result and "benign" not in result:
                return "malicious"
            return "benign"

    except asyncio.TimeoutError:
        logger.error("LLM API timeout for group=%s", group_name)
        return None
    except Exception as e:
        logger.error("LLM API error for group=%s: %s", group_name, e)
        return None
    finally:
        if close_session:
            await session.close()
