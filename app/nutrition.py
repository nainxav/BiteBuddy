from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app import config
from app.models import DayLog, FoodEntry, LogBook, Profile, Source, day_key
from app.storage import atomic_write_json, load_json


def load_profile() -> Profile:
    raw = load_json(config.PROFILE_PATH, {})
    if not raw:
        return Profile(
            current_weight_kg=70.0,
            target_weight_kg=68.0,
            daily_calorie_target=2000,
        )
    return Profile.from_dict(raw)


def save_profile(p: Profile) -> None:
    atomic_write_json(config.PROFILE_PATH, p.to_dict())


def load_logbook() -> LogBook:
    raw = load_json(config.LOG_PATH, {})
    if isinstance(raw, dict) and raw:
        return LogBook.from_dict(raw)
    return LogBook()


def save_logbook(book: LogBook) -> None:
    atomic_write_json(config.LOG_PATH, book.to_dict())


def get_day(book: LogBook, d: date) -> DayLog:
    k = day_key(d)
    if k not in book.days:
        book.days[k] = DayLog()
    return book.days[k]


def calories_consumed_on(book: LogBook, d: date) -> int:
    day = get_day(book, d)
    return sum(e.kcal for e in day.entries)


def add_entry(
    book: LogBook,
    description: str,
    kcal: int,
    source: Source,
    when: datetime | None = None,
) -> FoodEntry:
    ts = when or datetime.now()
    d = ts.date()
    entry = FoodEntry(
        description=description,
        kcal=kcal,
        source=source,
        when=ts,
    )
    day = get_day(book, d)
    day.entries.append(entry)
    return entry


@dataclass
class NutritionContext:
    current_weight_kg: float
    target_weight_kg: float
    daily_calorie_target: int
    consumed_today: int
    remaining_today: int
    food_item_kcal: int | None
    food_item_name: str | None


def build_context_for_llm(
    profile: Profile,
    book: LogBook,
    on: date,
    food_name: str | None,
    food_kcal: int | None,
) -> NutritionContext:
    consumed = calories_consumed_on(book, on)
    target = profile.daily_calorie_target
    remaining = max(0, target - consumed)
    return NutritionContext(
        current_weight_kg=profile.current_weight_kg,
        target_weight_kg=profile.target_weight_kg,
        daily_calorie_target=target,
        consumed_today=consumed,
        remaining_today=remaining,
        food_item_kcal=food_kcal,
        food_item_name=food_name,
    )


def format_summary(profile: Profile, book: LogBook, on: date) -> str:
    consumed = calories_consumed_on(book, on)
    target = profile.daily_calorie_target
    remaining = max(0, target - consumed)
    day = get_day(book, on)
    lines = [
        f"Date: {day_key(on)}",
        f"Weight: {profile.current_weight_kg} kg → target {profile.target_weight_kg} kg",
        f"Daily calorie target: {target} kcal",
        f"Consumed today: {consumed} kcal",
        f"Remaining: {remaining} kcal",
        "",
        "Meals logged:",
    ]
    if not day.entries:
        lines.append("  (none)")
    else:
        for e in day.entries:
            lines.append(
                f"  - {e.description} ({e.kcal} kcal, {e.source})"
            )
    return "\n".join(lines)
