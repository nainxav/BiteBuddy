from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app import food_db, intent, llm, nutrition

ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))

app = FastAPI(title="BiteBuddy")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1)


class ProfileIn(BaseModel):
    current_weight_kg: float = Field(..., gt=0, le=500)
    target_weight_kg: float = Field(..., gt=0, le=500)
    daily_calorie_target: int = Field(..., gt=0, le=20000)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "chat.html")


@app.get("/api/profile")
async def get_profile() -> JSONResponse:
    p = nutrition.load_profile()
    return JSONResponse(p.to_dict())


@app.post("/api/profile")
async def post_profile(body: ProfileIn) -> JSONResponse:
    p = nutrition.Profile(
        current_weight_kg=body.current_weight_kg,
        target_weight_kg=body.target_weight_kg,
        daily_calorie_target=body.daily_calorie_target,
    )
    nutrition.save_profile(p)
    return JSONResponse({"ok": True, "profile": p.to_dict()})


def _snapshot(
    profile: nutrition.Profile, book: nutrition.LogBook, today: date
) -> dict:
    ctx = nutrition.build_context_for_llm(profile, book, today, None, None)
    return {
        "consumed_today": ctx.consumed_today,
        "remaining_today": ctx.remaining_today,
        "daily_calorie_target": ctx.daily_calorie_target,
        "current_weight_kg": ctx.current_weight_kg,
        "target_weight_kg": ctx.target_weight_kg,
    }


@app.post("/api/chat")
async def chat(body: ChatIn) -> JSONResponse:
    profile = nutrition.load_profile()
    book = nutrition.load_logbook()
    today = date.today()
    kind, payload = intent.parse_intent(body.message)

    if kind == "empty":
        return JSONResponse(
            {"kind": "error", "reply": "Message was empty.", "data": {}}
        )

    if kind == "summary":
        text = nutrition.format_summary(profile, book, today)
        return JSONResponse(
            {
                "kind": "summary",
                "reply": text,
                "data": _snapshot(profile, book, today),
            }
        )

    if kind == "log":
        manual = food_db.parse_manual_kcal(payload)
        if manual:
            desc, kcal = manual
            source = "manual"
        else:
            _key, kcal = food_db.resolve_food(payload)
            if kcal is None:
                return JSONResponse(
                    {
                        "kind": "error",
                        "reply": (
                            f'Unknown food "{payload}". '
                            "Add it to data/foods.json or use: /log name|kcal "
                            "(example: /log pizza|450)."
                        ),
                        "data": _snapshot(profile, book, today),
                    }
                )
            desc = payload.strip()
            source = "db"
        nutrition.add_entry(book, desc, kcal, source)
        nutrition.save_logbook(book)
        consumed = nutrition.calories_consumed_on(book, today)
        reply = await llm.acknowledge_log(
            desc,
            kcal,
            consumed,
            profile.daily_calorie_target,
        )
        return JSONResponse(
            {
                "kind": "log",
                "reply": reply,
                "data": {
                    **_snapshot(profile, book, today),
                    "last_logged_kcal": kcal,
                },
            }
        )

    if kind == "ask":
        manual = food_db.parse_manual_kcal(payload)
        if manual:
            name, fk = manual
        else:
            name, fk = food_db.resolve_food(payload)
            if fk is None:
                name = payload.strip()
                fk = None
        nctx = nutrition.build_context_for_llm(
            profile, book, today, name, fk
        )
        if fk is None:
            reply = (
                f'No calorie entry for "{name}". '
                "Add it to data/foods.json or ask with: /ask name|kcal "
                "(example: /ask burger|550)."
            )
            return JSONResponse(
                {
                    "kind": "ask",
                    "reply": reply,
                    "data": _snapshot(profile, book, today),
                }
            )
        q = f"Should I eat this now? ({name}, {fk} kcal)"
        reply = await llm.ask_about_food(nctx, q)
        return JSONResponse(
            {
                "kind": "ask",
                "reply": reply,
                "data": {
                    **_snapshot(profile, book, today),
                    "food_kcal": fk,
                    "food_name": name,
                },
            }
        )

    nctx = nutrition.build_context_for_llm(profile, book, today, None, None)
    reply = await llm.general_chat(nctx, payload)
    return JSONResponse(
        {
            "kind": "chat",
            "reply": reply,
            "data": _snapshot(profile, book, today),
        }
    )
