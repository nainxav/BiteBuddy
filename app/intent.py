from __future__ import annotations

import re


def parse_intent(message: str) -> tuple[str, str]:
    """
    Returns (kind, payload).
    kind: log | ask | summary | chat | empty
    """
    m = message.strip()
    if not m:
        return "empty", ""
    low = m.lower()
    if low.startswith("/log "):
        return "log", m[5:].strip()
    if low.startswith("/ask "):
        return "ask", m[5:].strip()
    if low in ("/summary", "summary"):
        return "summary", ""
    if low.startswith("i ate "):
        return "log", m[6:].strip()
    mo = re.match(r"^(?:can i|should i)\s+eat\s+(.+)$", m.strip(), re.I)
    if mo:
        return "ask", mo.group(1).strip()
    return "chat", m
