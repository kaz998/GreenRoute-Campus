"""Real cloud AI integration for GreenRoute.

Uses the OpenAI Responses API when OPENAI_API_KEY is configured.
The API key is deliberately read from the server environment/.env and is
never sent to the browser.
"""
import json
import os
import re

import requests


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


def configured():
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _extract_text(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        chunks = []
        for item in payload.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in ("output_text", "text") and isinstance(content.get("text"), str):
                    chunks.append(content["text"])
        if chunks:
            return "\n".join(chunks)
    return ""


def _clean_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def recommend(user_message, distance_km, departure_hour, weather, candidates, history=None):
    """Ask the cloud model to choose among real, server-computed candidates.

    The model may decide the user's intent and recommendation, but it cannot
    invent prices/times/CO2 values: those values are supplied by GreenRoute and
    are copied back from the selected candidate after validation.
    """
    if not configured():
        raise RuntimeError("OPENAI_API_KEY is not configured")

    compact_candidates = [
        {
            "code": x["code"],
            "name": x["name"],
            "time_min": round(x["time"], 1),
            "cost_inr": round(x["cost"], 2),
            "co2_kg": round(x["co2"], 3),
            "calories": round(x["calories"], 1),
            "feasible": bool(x["feasible"]),
            "notes": x.get("notes", []),
        }
        for x in candidates
    ]

    instructions = """You are GreenRoute Campus AI, a mobility decision assistant.
Use the user's natural-language request to choose the most suitable transport
mode from the supplied candidate list. This is a campus sustainability app.

Rules:
- You MUST choose exactly one candidate code from the supplied list.
- Never invent a transport mode or numerical metric.
- Treat an explicit request such as 'take the bus' as a strong constraint unless
  that candidate is infeasible.
- Consider the user's stated priorities, budget, time limit, emissions, health,
  distance, departure time, weather and air quality.
- Do not blindly choose bicycle or any single mode. Different requests should
  produce different recommendations when the supplied data supports that.
- Be concise but genuinely reason about trade-offs.
- Return ONLY valid JSON with this exact shape:
  {"mode":"candidate code","confidence":0-100,"priority":"short label","explanation":"2-4 sentences","tips":["tip 1","tip 2"]}
"""

    history = history or []
    user_context = {
        "request": user_message,
        "conversation_history": history[-6:],
        "distance_km": distance_km,
        "departure_hour": departure_hour,
        "weather": weather,
        "candidates": compact_candidates,
    }

    body = {
        "model": DEFAULT_MODEL,
        "instructions": instructions,
        "input": json.dumps(user_context, ensure_ascii=False),
        "max_output_tokens": 500,
    }
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text[:300])
        except Exception:
            detail = response.text[:300]
        raise RuntimeError(f"OpenAI API error ({response.status_code}): {detail}")

    data = response.json()
    result = _clean_json(_extract_text(data))
    mode = str(result.get("mode", "")).strip().lower()
    allowed = {x["code"] for x in candidates if x["feasible"]}
    if mode not in allowed:
        raise RuntimeError("AI returned an invalid or infeasible transport mode")

    confidence = max(0, min(100, int(float(result.get("confidence", 70)))))
    priority = str(result.get("priority", "balanced")).strip()[:80] or "balanced"
    explanation = str(result.get("explanation", "The AI compared the available options against your request." )).strip()
    tips = result.get("tips", [])
    if not isinstance(tips, list):
        tips = []
    tips = [str(x).strip() for x in tips[:3] if str(x).strip()]

    return {
        "mode": mode,
        "confidence": confidence,
        "priority": priority,
        "explanation": explanation,
        "tips": tips,
        "model": DEFAULT_MODEL,
    }
