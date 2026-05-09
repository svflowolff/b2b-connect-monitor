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


def message_has_reaction(channel: str, ts: str) -> bool:
    """
    Verifiziert Reactions ueber den dedizierten reactions.get-Endpunkt.
    Robuster als das reactions-Feld in conversations.history, das je
    nach Scopes/Caching nicht immer geliefert wird.
    Benoetigt Scope: reactions:read
    """
    try:
        data = slack_call("reactions.get", {"channel": channel, "timestamp": ts})
        reactions = data.get("message", {}).get("reactions", [])
        return sum(r.get("count", 0) for r in reactions) > 0
    except Exception as e:
        print(f"[reminder] reactions.get fehlgeschlagen fuer ts={ts}: {e}")
        return False


def get_own_identity() -> tuple[str, str]:
    """
    Eigene Bot-User-ID + Bot-ID aus auth.test holen.
    Brauchen wir, um eigene Nachrichten in der Channel-History sicher zu
    identifizieren - unabhaengig vom Text/Marker-String.
    """
    data = slack_call("auth.test", {})
    return data.get("user_id", ""), data.get("bot_id", "")


def is_own_message(msg: dict, own_user_id: str, own_bot_id: str) -> bool:
    """
    True wenn die Nachricht von uns selbst stammt. Nutzt user_id und bot_id
    aus auth.test - robust gegen Slack-Emoji/Text-Rendering-Quirks.
    """
    if own_user_id and msg.get("user") == own_user_id:
        return True
    if own_bot_id and msg.get("bot_id") == own_bot_id:
        return True
    return False


def main() -> int:
    now_berlin = datetime.now(BERLIN)
    print(f"[reminder] Aktuelle Berlin-Zeit: {now_berlin:%Y-%m-%d %H:%M %Z}")

    force_run = os.environ.get("FORCE_RUN", "").lower() == "true"
    if force_run:
        print("[reminder] FORCE_RUN=true - Wochentag-Check uebersprungen.")

    weekday = now_berlin.weekday()
    if not force_run and weekday not in (3, 4, 5, 6):
        print(f"[reminder] Wochentag {weekday} - kein Send-Tag. Skip.")
        return 0

    # KEIN hour-Check mehr. GitHub Actions Cron-Jobs verspaeten sich
    # routinemaessig 1-3 Stunden, der alte Stunde-genau-10-Check hat
    # damit fast jeden Lauf gekillt. Idempotenz unten ueber sent_today.

    own_user_id, own_bot_id = get_own_identity()
    print(f"[reminder] Eigene Identitaet: user_id={own_user_id} bot_id={own_bot_id}")

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

    # Eigene Nachrichten ueber user_id / bot_id identifizieren statt ueber
    # einen Marker-String im Text. Das macht den Check immun gegen Slack-API-
    # Quirks (z.B. Emojis, die als Shortcode :bell: zurueckkommen statt als 🔔).
    bot_messages = [m for m in messages if is_own_message(m, own_user_id, own_bot_id)]
    print(
        f"[reminder] {len(messages)} Nachrichten in der Woche, "
        f"davon {len(bot_messages)} eigene."
    )

    # Reaction-Check: erst inline, dann verifiziert via reactions.get
    has_reaction = False
    for m in bot_messages:
        ts = m.get("ts")
        if not ts:
            continue
        inline_count = sum(r.get("count", 0) for r in m.get("reactions", []))
        api_confirms = message_has_reaction(CHANNEL_ID, ts)
        print(
            f"[reminder]   ts={ts}: inline_reactions={inline_count}, "
            f"api_confirms={api_confirms}"
        )
        if inline_count > 0 or api_confirms:
            has_reaction = True

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
