from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query, Request
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
    target_weight_kg: float = Field(..., gt=0, le=500)
    daily_calorie_target: int = Field(..., gt=0, le=20000)


class WeightIn(BaseModel):
    date: date
    weight_kg: float = Field(..., gt=0, le=500)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "chat.html")


@app.get("/api/profile")
async def get_profile() -> JSONResponse:
    p = nutrition.load_profile()
    wb = nutrition.load_weight_book()
    latest = nutrition.latest_weight_entry(wb)
    cw = nutrition.current_weight_kg_from_log(wb)
    return JSONResponse(
        {
            "target_weight_kg": p.target_weight_kg,
            "daily_calorie_target": p.daily_calorie_target,
            "current_weight_kg": cw,
            "current_weight_date": latest[0] if latest else None,
        }
    )


@app.post("/api/profile")
async def post_profile(body: ProfileIn) -> JSONResponse:
    p = nutrition.Profile(
        target_weight_kg=body.target_weight_kg,
        daily_calorie_target=body.daily_calorie_target,
    )
    nutrition.save_profile(p)
    return JSONResponse({"ok": True, "profile": p.to_dict()})


@app.get("/api/weights")
async def get_weights(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> JSONResponse:
    wb = nutrition.load_weight_book()
    return JSONResponse(
        {"weights": nutrition.weights_in_month(wb, year, month)}
    )


@app.put("/api/weights")
async def put_weight(body: WeightIn) -> JSONResponse:
    wb = nutrition.load_weight_book()
    key = body.date.isoformat()
    wb.by_day[key] = body.weight_kg
    nutrition.save_weight_book(wb)
    return JSONResponse(
        {
            "ok": True,
            "date": key,
            "weight_kg": body.weight_kg,
        }
    )


@app.delete("/api/weights")
async def delete_weight(
    for_date: date = Query(..., alias="date"),
) -> JSONResponse:
    wb = nutrition.load_weight_book()
    key = for_date.isoformat()
    if key in wb.by_day:
        del wb.by_day[key]
        nutrition.save_weight_book(wb)
    return JSONResponse({"ok": True})


def _snapshot(
    profile: nutrition.Profile,
    book: nutrition.LogBook,
    today: date,
    wb: nutrition.WeightBook,
) -> dict:
    ctx = nutrition.build_context_for_llm(
        profile, book, today, None, None, wb
    )
    latest = nutrition.latest_weight_entry(wb)
    return {
        "consumed_today": ctx.consumed_today,
        "remaining_today": ctx.remaining_today,
        "daily_calorie_target": ctx.daily_calorie_target,
        "current_weight_kg": ctx.current_weight_kg,
        "current_weight_date": latest[0] if latest else None,
        "target_weight_kg": ctx.target_weight_kg,
    }


@app.post("/api/chat")
async def chat(body: ChatIn) -> JSONResponse:
    profile = nutrition.load_profile()
    book = nutrition.load_logbook()
    wb = nutrition.load_weight_book()
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
                "data": _snapshot(profile, book, today, wb),
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
                        "data": _snapshot(profile, book, today, wb),
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
                    **_snapshot(profile, book, today, wb),
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
            profile, book, today, name, fk, wb
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
                    "data": _snapshot(profile, book, today, wb),
                }
            )
        q = f"Should I eat this now? ({name}, {fk} kcal)"
        reply = await llm.ask_about_food(nctx, q)
        return JSONResponse(
            {
                "kind": "ask",
                "reply": reply,
                "data": {
                    **_snapshot(profile, book, today, wb),
                    "food_kcal": fk,
                    "food_name": name,
                },
            }
        )

    nctx = nutrition.build_context_for_llm(
        profile, book, today, None, None, wb
    )
    reply = await llm.general_chat(nctx, payload)
    return JSONResponse(
        {
            "kind": "chat",
            "reply": reply,
            "data": _snapshot(profile, book, today, wb),
        }
    )
