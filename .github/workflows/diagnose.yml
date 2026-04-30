#!/usr/bin/env python3
"""
Slack Diagnose-Skript
=====================
Hilft dabei, channel_not_found / missing_scope / invalid_auth Fehler zu finden.

Macht drei Slack-API-Calls und gibt strukturiert aus, was Slack zurückgibt:

  1. auth.test            – Wer bin ich (Token-Identität)?
  2. conversations.info   – Sieht der Bot den Channel?
  3. conversations.list   – Welche Channels sieht der Bot überhaupt?

Liest dieselben ENV-Variablen wie reminder.py:
    SLACK_BOT_TOKEN
    SLACK_CHANNEL_ID
"""
from __future__ import annotations

import json
import os
import sys

import requests

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
SLACK_API = "https://slack.com/api"


def call(method: str, params: dict | None = None, body: dict | None = None) -> dict:
    """Macht einen Slack-Call und gibt das JSON zurück (auch bei Slack-Fehlern)."""
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        resp = requests.post(f"{SLACK_API}/{method}", headers=headers, json=body, timeout=20)
    else:
        resp = requests.get(f"{SLACK_API}/{method}", headers=headers, params=params or {}, timeout=20)
    return resp.json()


def banner(label: str) -> None:
    print()
    print("=" * 70)
    print(f"  {label}")
    print("=" * 70)


def main() -> int:
    banner("1) auth.test  – Welche App / welcher Workspace nutzt dieses Token?")
    auth = call("auth.test", body={})
    print(json.dumps(auth, indent=2))
    if not auth.get("ok"):
        print("\n>> Token ist ungültig oder abgelaufen. SLACK_BOT_TOKEN aktualisieren.")
        return 1
    print(f"\n>> Workspace: {auth.get('team')}  (team_id={auth.get('team_id')})")
    print(f">> Bot-User:  @{auth.get('user')}    (bot_id={auth.get('bot_id')})")
    print(f">> Enterprise: {auth.get('enterprise_id') or 'nein (Standard-Workspace)'}")

    banner(f"2) conversations.info  – Sieht das Token den Channel {CHANNEL_ID}?")
    info = call("conversations.info", params={"channel": CHANNEL_ID})
    print(json.dumps(info, indent=2))
    if info.get("ok"):
        ch = info["channel"]
        print(f"\n>> Channel-Name:    #{ch.get('name')}")
        print(f">> ist_privat:      {ch.get('is_private')}")
        print(f">> ist_member:      {ch.get('is_member')}  (False = Bot ist NICHT im Channel)")
        print(f">> ist_shared:      {ch.get('is_shared')}")
        print(f">> ist_org_shared:  {ch.get('is_org_shared')}")
    else:
        err = info.get("error", "unknown")
        print(f"\n>> Fehler: {err}")
        if err == "channel_not_found":
            print(">> Höchstwahrscheinlich: Channel existiert in einem anderen Workspace,")
            print(">> oder ist ein Org-wide-Channel und die App ist nicht org-weit installiert.")
        elif err == "not_in_channel":
            print(">> Bot muss in den Channel eingeladen werden: /invite @<bot-name>")
        elif err == "missing_scope":
            print(">> Scope fehlt. needed:", info.get("needed"), "provided:", info.get("provided"))

    banner("3) conversations.list  – Welche Channels sieht das Token überhaupt?")
    listed = call(
        "conversations.list",
        params={"types": "public_channel,private_channel", "limit": 1000},
    )
    if listed.get("ok"):
        channels = listed.get("channels", [])
        print(f"Token sieht {len(channels)} Channel(s):\n")
        for ch in channels[:50]:
            marker = " <-- DAS IST DER GESUCHTE" if ch["id"] == CHANNEL_ID else ""
            privacy = "🔒" if ch.get("is_private") else "#"
            member = "✓" if ch.get("is_member") else "✗"
            print(f"  {privacy} {ch['id']}  member={member}  name={ch['name']}{marker}")
        if len(channels) > 50:
            print(f"  ... ({len(channels) - 50} weitere abgeschnitten)")
        if not any(ch["id"] == CHANNEL_ID for ch in channels):
            print(f"\n>> ⚠️  Die gesuchte Channel-ID {CHANNEL_ID} ist NICHT in dieser Liste.")
            print(">> Mögliche Gründe: falsche ID, anderer Workspace, oder Org-wide-Channel.")
    else:
        print(json.dumps(listed, indent=2))
        print(f"\n>> conversations.list scheiterte: {listed.get('error')}")

    banner("Fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
