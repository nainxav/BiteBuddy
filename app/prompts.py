from __future__ import annotations

from app.nutrition import NutritionContext


SYSTEM = """You are a concise nutrition coach for a single user.
Rules:
- Never invent calorie numbers. Only use the numeric facts provided in the CONTEXT block.
- If CONTEXT lacks a number, say you do not have it instead of guessing.
- Keep answers short unless the user asks for detail."""


def context_block(ctx: NutritionContext) -> str:
    lines = [
        "CONTEXT (authoritative numbers from the app — do not contradict):",
        f"- Current weight (kg): {ctx.current_weight_kg}",
        f"- Target weight (kg): {ctx.target_weight_kg}",
        f"- Daily calorie target: {ctx.daily_calorie_target}",
        f"- Consumed today (kcal): {ctx.consumed_today}",
        f"- Remaining today (kcal): {ctx.remaining_today}",
    ]
    if ctx.food_item_name and ctx.food_item_kcal is not None:
        lines.append(
            f"- Food in question: {ctx.food_item_name} — {ctx.food_item_kcal} kcal "
            "(portion estimate from local database)"
        )
    else:
        lines.append("- Food in question: (not specified)")
    return "\n".join(lines)


def ask_user_message(ctx: NutritionContext, question: str) -> str:
    return f"{context_block(ctx)}\n\nUser question: {question}"


def chat_user_message(ctx: NutritionContext, user_message: str) -> str:
    return f"{context_block(ctx)}\n\nUser message: {user_message}"


def log_ack_message(item: str, kcal: int, consumed_after: int, target: int) -> str:
    return (
        f"The user logged food: {item} ({kcal} kcal). "
        f"They have now consumed {consumed_after} kcal today "
        f"(target {target}). Reply in one short friendly sentence."
    )
