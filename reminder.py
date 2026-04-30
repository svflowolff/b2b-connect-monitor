#!/usr/bin/env python3
"""
Slack Daily Reminder Bot
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
TOPIC = os.environ.get("REMINDER_TOPIC", "next week's B2B Connect Brand campaign")

MARKER = "🔔 [Daily-Reminder]"

MESSAGES: dict[int, str] = {
    1: (
        f"{MARKER}\n"
        "Morning team! Quick check: is *{topic}* planned and ready? "
        "Drop any emoji on this message to confirm – "
        "I'll then go quiet until next Thursday."
    ),
    2: (
        f"{MARKER}\n"
        "Friendly nudge – is *{topic}* sorted yet? "
        "One emoji on this message and I'm off your back until next week 🙏"
    ),
    3: (
        f"{MARKER}\n"
        "Weekend nudge: please lock in *{topic}* today or tomorrow. "
        "Any emoji on this message works as confirmation 😉"
    ),
    4: (
        f"{MARKER}\n"
        "Last call for this cycle – *{topic}*. "
        "If we don't hear back by tonight, "
        "I'll start nudging again on Thursday 🙃"
    ),
}

BERLIN = ZoneInfo("Europe/Berlin")
SLACK_API = "https://slack.com/api"


def slack_call(method: str, payload: dict) -> dict:
    resp = requests.post(
        f"{SLACK_API}/{method}",
        headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack {method} failed: {data}")
    return data


def fetch_history(oldest_ts: float) -> list[dict]:
    messages: list[dict] = []
    cursor: str | None = None
    while True:
        payload: dict = {
            "channel": CHANNEL_ID,
            "oldest": f"{oldest_ts:.6f}",
            "limit": 200,
        }
        if cursor:
            payload["cursor"] = cursor
        data = slack_call("conversations.history", payload)
        messages.extend(data.get("messages", []))
        cursor = data.get("response_metadata", {}).get("next_cursor") or None
        if not cursor:
            break
    return messages


def main() -> int:
    now_berlin = datetime.now(BERLIN)
    print(f"[reminder] Aktuelle Berlin-Zeit: {now_berlin:%Y-%m-%d %H:%M %Z}")

    force_run = os.environ.get("FORCE_RUN", "").lower() == "true"
    if force_run:
        print("[reminder] FORCE_RUN=true - Wochentag/Stunden-Check uebersprungen.")

    weekday = now_berlin.weekday()
    if not force_run and weekday not in (3, 4, 5, 6):
        print(f"[reminder] Wochentag {weekday} - kein Send-Tag. Skip.")
        return 0

    if not force_run and now_berlin.hour != 10:
        print(f"[reminder] Berlin-Stunde {now_berlin.hour} != 10. Skip.")
        return 0

    days_since_thursday = (weekday - 3) % 7
    last_thursday = now_berlin.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days_since_thursday)
    oldest_ts = last_thursday.timestamp()
    print(
        f"[reminder] Wochenfenster ab {last_thursday:%Y-%m-%d %H:%M %Z} "
        f"(ts={oldest_ts:.0f})"
    )

    messages = fetch_history(oldest_ts)
    bot_messages = [m for m in messages if MARKER in m.get("text", "")]
    print(
        f"[reminder] {len(messages)} Nachrichten in der Woche, "
        f"davon {len(bot_messages)} eigene."
    )

    has_reaction = any(len(m.get("reactions", [])) > 0 for m in bot_messages)
    if has_reaction:
        print("[reminder] Bestaetigung gefunden - heute keine Nachricht.")
        return 0

    today_start = now_berlin.replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = any(
        datetime.fromtimestamp(float(m["ts"]), BERLIN) >= today_start
        for m in bot_messages
    )
    if sent_today:
        print("[reminder] Heute bereits gesendet. Skip.")
        return 0

    day_in_cycle = days_since_thursday + 1
    if day_in_cycle not in MESSAGES:
        print(f"[reminder] Tag {day_in_cycle} ausserhalb 1..4 - nehme Tag 1 als Fallback.")
        day_in_cycle = 1
    text = MESSAGES[day_in_cycle].format(topic=TOPIC)

    slack_call("chat.postMessage", {"channel": CHANNEL_ID, "text": text})
    print(f"[reminder] Tag {day_in_cycle}/4 gesendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
