#!/usr/bin/env python3
"""
Slack Daily Reminder Bot
========================
Sendet Donnerstag bis Sonntag um 10:00 Europe/Berlin eine Reminder-Nachricht in
einen Slack-Channel. Sobald jemand auf eine Bot-Nachricht in der laufenden
Woche (seit dem letzten Donnerstag 00:00) mit irgendeinem Emoji reagiert,
pausiert der Bot bis zum nächsten Donnerstag.

Stateless: kein eigener Speicher nötig – der Status wird live aus dem
Slack-Channel rekonstruiert.

ENV-Variablen (in GitHub Actions als Secrets):
    SLACK_BOT_TOKEN   xoxb-... Token aus der Slack App
    SLACK_CHANNEL_ID  Channel-ID, z.B. C09ABCDEF12
    REMINDER_TOPIC    Worum geht's? z.B. "Wochenreport abgeben"
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
TOPIC = os.environ.get("REMINDER_TOPIC", "die offene Aufgabe")

# Marker, an dem wir unsere eigenen Bot-Nachrichten erkennen.
# Bitte nicht in normalen Channel-Nachrichten verwenden, sonst "verwechselt"
# der Bot fremde Nachrichten mit eigenen.
MARKER = "🔔 [Daily-Reminder]"

# Reminder-Texte pro Tag im Zyklus (1=Do, 2=Fr, 3=Sa, 4=So).
# {topic} wird durch REMINDER_TOPIC ersetzt.
MESSAGES: dict[int, str] = {
    1: (
        f"{MARKER}\n"
        "Moin zusammen! Bitte denkt heute an *{topic}*. "
        "Wenn erledigt, einfach mit einem Emoji bestätigen ✅ – "
        "dann meld ich mich erst nächsten Donnerstag wieder."
    ),
    2: (
        f"{MARKER}\n"
        "Freundliche Erinnerung – *{topic}* steht noch aus. "
        "Reaktion = Pause bis nächste Woche 🙏"
    ),
    3: (
        f"{MARKER}\n"
        "Wochenend-Push: bitte heute oder morgen *{topic}* abhaken. "
        "Ein Klick auf irgendein Emoji genügt 😉"
    ),
    4: (
        f"{MARKER}\n"
        "Letzter Aufruf für diese Runde – *{topic}*. "
        "Falls's bis Sonntagabend nicht passiert, "
        "fang ich Donnerstag wieder an zu nerven 🙃"
    ),
}

BERLIN = ZoneInfo("Europe/Berlin")
SLACK_API = "https://slack.com/api"


# ---------------------------------------------------------------------------
# Slack-Helper
# ---------------------------------------------------------------------------


def slack_call(method: str, payload: dict) -> dict:
    """POST an Slack Web API. Wirft Exception bei Fehler."""
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
    """Holt Channel-History seit oldest_ts (mit einfachem Pagination-Handling)."""
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


# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------


def main() -> int:
    now_berlin = datetime.now(BERLIN)
    print(f"[reminder] Aktuelle Berlin-Zeit: {now_berlin:%Y-%m-%d %H:%M %Z}")

    # 1) Wochentag: nur Do (3), Fr (4), Sa (5), So (6) sind Send-Tage.
    weekday = now_berlin.weekday()  # 0=Mo … 6=So
    if weekday not in (3, 4, 5, 6):
        print(f"[reminder] Wochentag {weekday} – kein Send-Tag. Skip.")
        return 0

    # 2) Stunde: GitHub Actions feuert per Cron in UTC; wir feuern zweimal
    #    (8 und 9 UTC), damit DST egal ist. Hier akzeptieren wir nur Berlin=10.
    if now_berlin.hour != 10:
        print(f"[reminder] Berlin-Stunde {now_berlin.hour} ≠ 10. Skip.")
        return 0

    # 3) Letzten Donnerstag 00:00 Berlin-Zeit berechnen.
    days_since_thursday = (weekday - 3) % 7
    last_thursday = now_berlin.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days_since_thursday)
    oldest_ts = last_thursday.timestamp()
    print(
        f"[reminder] Wochenfenster ab {last_thursday:%Y-%m-%d %H:%M %Z} "
        f"(ts={oldest_ts:.0f})"
    )

    # 4) Slack-History seit letztem Donnerstag holen.
    messages = fetch_history(oldest_ts)
    bot_messages = [m for m in messages if MARKER in m.get("text", "")]
    print(
        f"[reminder] {len(messages)} Nachrichten in der Woche, "
        f"davon {len(bot_messages)} eigene."
    )

    # 5) Reaktion auf irgendeiner unserer Wochen-Nachrichten? → Pause.
    has_reaction = any(len(m.get("reactions", [])) > 0 for m in bot_messages)
    if has_reaction:
        print("[reminder] Bestätigung gefunden – heute keine Nachricht.")
        return 0

    # 6) Idempotenz: heute schon gesendet? Cron kann doppelt feuern oder
    #    der Workflow wird manuell erneut getriggert.
    today_start = now_berlin.replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = any(
        datetime.fromtimestamp(float(m["ts"]), BERLIN) >= today_start
        for m in bot_messages
    )
    if sent_today:
        print("[reminder] Heute bereits gesendet. Skip.")
        return 0

    # 7) Tag im Zyklus → passenden Text auswählen.
    day_in_cycle = days_since_thursday + 1  # 1..4
    text = MESSAGES[day_in_cycle].format(topic=TOPIC)

    # 8) Senden.
    slack_call("chat.postMessage", {"channel": CHANNEL_ID, "text": text})
    print(f"[reminder] Tag {day_in_cycle}/4 gesendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
