#!/usr/bin/env python3
"""OAuth の口を取り直す道具（2026-09-14 20:3x・親）。

    python scripts/oauth_link.py            # 認可 URL を印字（client_id は環境の YT_CLIENT_ID）
    python scripts/oauth_link.py --exchange "<code か、code を含む URL>" --out <path>
                                            # code を refresh token に替え、返りの JSON を <path> に書く
                                            # （値は画面に出さない）

redirect は OAuth Playground（`docs/SETUP.md` STEP 3 で許可ずみの URI）。
スコープは STEP 4 の 4つ。`access_type=offline&prompt=consent` で refresh token が必ず返る。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

REDIRECT = "https://developers.google.com/oauthplayground"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def auth_url() -> str:
    q = {
        "client_id": os.environ["YT_CLIENT_ID"],
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)


def code_of(s: str) -> str:
    s = s.strip()
    if "code=" in s:
        qs = urllib.parse.urlparse(s).query or s.split("?", 1)[-1]
        return urllib.parse.parse_qs(qs)["code"][0]
    return s


def exchange(code: str) -> dict:
    d = urllib.parse.urlencode({
        "code": code,
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=d)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:400]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", metavar="CODE_OR_URL")
    ap.add_argument("--out", metavar="PATH")
    a = ap.parse_args()
    if not a.exchange:
        print(auth_url())
        return 0
    res = exchange(code_of(a.exchange))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f)
        print("ok" if "refresh_token" in res else f"NG {res.get('error')} {res.get('body','')[:200]}")
    else:
        print("refresh_token" in res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
