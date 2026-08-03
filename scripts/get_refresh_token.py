#!/usr/bin/env python3
"""リフレッシュトークンを1回だけ取るためのスクリプト（あなたのPCで実行）。

    python scripts/get_refresh_token.py

ブラウザが開くので、投稿したい YouTube チャンネルの Google アカウントで許可する。
最後に表示される YT_REFRESH_TOKEN を GitHub の Repository secrets に登録すれば、
以降は自動投稿が無人で回る。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from src.auth import SCOPES  # noqa: E402


def main() -> int:
    client_id = input("YT_CLIENT_ID: ").strip()
    client_secret = input("YT_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        print("両方とも必須です。")
        return 1

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=SCOPES,
    )

    # prompt="consent" を付けないと2回目以降 refresh_token が返らない
    credentials = flow.run_local_server(
        port=0, access_type="offline", prompt="consent",
        authorization_prompt_message="ブラウザで認証してください: {url}",
    )

    if not credentials.refresh_token:
        print("リフレッシュトークンが返りませんでした。")
        print("https://myaccount.google.com/permissions でこのアプリのアクセスを削除してから再実行してください。")
        return 1

    print("\n" + "=" * 64)
    print("以下を GitHub の Repository secrets に登録してください。")
    print("=" * 64)
    print(f"YT_CLIENT_ID={client_id}")
    print(f"YT_CLIENT_SECRET={client_secret}")
    print(f"YT_REFRESH_TOKEN={credentials.refresh_token}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
