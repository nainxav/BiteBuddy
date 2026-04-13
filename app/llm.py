from __future__ import annotations

import httpx

from app import config
from app.nutrition import NutritionContext
from app import prompts


async def complete_chat(
    system: str,
    user: str,
    temperature: float = 0.4,
) -> str:
    if not config.OPENROUTER_API_KEY:
        return (
            "OpenRouter is not configured. Set OPENROUTER_API_KEY in your environment "
            "or .env file."
        )
    url = f"{config.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.OPENROUTER_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return "No response from model."
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    return (content or "").strip() or "(empty reply)"


async def ask_about_food(ctx: NutritionContext, question: str) -> str:
    user = prompts.ask_user_message(ctx, question)
    return await complete_chat(prompts.SYSTEM, user, temperature=0.35)


async def general_chat(ctx: NutritionContext, user_message: str) -> str:
    user = prompts.chat_user_message(ctx, user_message)
    return await complete_chat(prompts.SYSTEM, user, temperature=0.5)


async def acknowledge_log(
    item: str, kcal: int, consumed_after: int, target: int
) -> str:
    user = prompts.log_ack_message(item, kcal, consumed_after, target)
    return await complete_chat(prompts.SYSTEM, user, temperature=0.6)
