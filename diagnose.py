#!/usr/bin/env python3
"""
Slack Diagnose-Skript
=====================
Hilft dabei, channel_not_found / missing_scope / invalid_auth Fehler zu finden.
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
    banner("1) auth.test  - Welche App / welcher Workspace nutzt dieses Token?")
    auth = call("auth.test", body={})
    print(json.dumps(auth, indent=2))
    if not auth.get("ok"):
        print("\n>> Token ist ungueltig oder abgelaufen.")
        return 1
    print(f"\n>> Workspace: {auth.get('team')}  (team_id={auth.get('team_id')})")
    print(f">> Bot-User:  @{auth.get('user')}    (user_id={auth.get('user_id')})")
    print(f">> Enterprise: {auth.get('enterprise_id') or 'nein'}")

    banner(f"2) conversations.info  - Sieht das Token den Channel {CHANNEL_ID}?")
    info = call("conversations.info", params={"channel": CHANNEL_ID})
    print(json.dumps(info, indent=2))
    if info.get("ok"):
        ch = info["channel"]
        print(f"\n>> Channel-Name:    #{ch.get('name')}")
        print(f">> ist_privat:      {ch.get('is_private')}")
        print(f">> ist_member:      {ch.get('is_member')}")
        print(f">> ist_shared:      {ch.get('is_shared')}")
        print(f">> ist_ext_shared:  {ch.get('is_ext_shared')}")
        print(f">> ist_org_shared:  {ch.get('is_org_shared')}")
    else:
        err = info.get("error", "unknown")
        print(f"\n>> Fehler: {err}")

    banner("3) conversations.list (nur public_channel)  - Welche Public-Channels sieht das Token?")
    listed = call(
        "conversations.list",
        params={"types": "public_channel", "exclude_archived": "true", "limit": 1000},
    )
    if listed.get("ok"):
        channels = listed.get("channels", [])
        print(f"Token sieht {len(channels)} public Channel(s) im Workspace.\n")
        member_chans = [c for c in channels if c.get("is_member")]
        print(f"-- Davon ist der Bot Member in {len(member_chans)} Channel(s):")
        for ch in member_chans:
            marker = "  <-- ZIEL!" if ch["id"] == CHANNEL_ID else ""
            print(f"   #{ch['name']:30s}  id={ch['id']}{marker}")
        match = next((c for c in channels if c["id"] == CHANNEL_ID), None)
        if match:
            print(f"\n>> Channel-ID {CHANNEL_ID} ist in der Public-Liste:")
            print(f"   name={match['name']}, is_member={match.get('is_member')}, "
                  f"is_shared={match.get('is_shared')}, is_ext_shared={match.get('is_ext_shared')}, "
                  f"is_org_shared={match.get('is_org_shared')}")
        else:
            print(f"\n>> Channel-ID {CHANNEL_ID} ist NICHT in der Public-Liste.")
            print(">> Bedeutet: Token sieht den Channel im Workspace nicht.")
    else:
        print(json.dumps(listed, indent=2))
        print(f"\n>> conversations.list scheiterte: {listed.get('error')}")

    banner(f"4) conversations.members  - Wer ist Member im Channel {CHANNEL_ID}?")
    mem = call("conversations.members", params={"channel": CHANNEL_ID, "limit": 200})
    print(json.dumps(mem, indent=2)[:1500])
    if mem.get("ok"):
        members = mem.get("members", [])
        bot_user_id = auth.get("user_id")
        print(f"\n>> Channel hat {len(members)} Member.")
        if bot_user_id in members:
            print(f">> Bot ({bot_user_id}) ist als Member gelistet.")
        else:
            print(f">> Bot ({bot_user_id}) ist NICHT in der Member-Liste.")
            print(">> Loesung: in Slack im Channel '/invite @b2b_connect_monitor' ausfuehren.")

    banner("Fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
