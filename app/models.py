from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal


Source = Literal["db", "manual"]


@dataclass
class Profile:
    current_weight_kg: float
    target_weight_kg: float
    daily_calorie_target: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Profile:
        return cls(
            current_weight_kg=float(d["current_weight_kg"]),
            target_weight_kg=float(d["target_weight_kg"]),
            daily_calorie_target=int(d["daily_calorie_target"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_weight_kg": self.current_weight_kg,
            "target_weight_kg": self.target_weight_kg,
            "daily_calorie_target": self.daily_calorie_target,
        }


@dataclass
class FoodEntry:
    description: str
    kcal: int
    source: Source
    when: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "kcal": self.kcal,
            "source": self.source,
            "iso": self.when.isoformat(timespec="seconds"),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FoodEntry:
        when = datetime.fromisoformat(d["iso"]) if "iso" in d else datetime.now()
        return cls(
            description=str(d["description"]),
            kcal=int(d["kcal"]),
            source=d.get("source", "manual"),  # type: ignore[arg-type]
            when=when,
        )


def day_key(d: date) -> str:
    return d.isoformat()


@dataclass
class DayLog:
    entries: list[FoodEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DayLog:
        raw = d.get("entries") or []
        return cls(entries=[FoodEntry.from_dict(x) for x in raw])


@dataclass
class LogBook:
    days: dict[str, DayLog] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in sorted(self.days.items())}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LogBook:
        days: dict[str, DayLog] = {}
        for k, v in d.items():
            if isinstance(v, dict) and "entries" in v:
                days[k] = DayLog.from_dict(v)
        return cls(days=days)
