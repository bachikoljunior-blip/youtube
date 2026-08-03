"""YouTube API の OAuth 認証情報。

リフレッシュトークンだけを secrets に置き、実行のたびにアクセストークンを取り直す。
"""
from __future__ import annotations

from google.oauth2.credentials import Credentials

from . import config

TOKEN_URI = "https://oauth2.googleapis.com/token"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    # 収益額の取得用。YPP 承認前でも同意だけは通るので最初から入れておく
    # （後から足すとリフレッシュトークンを取り直す羽目になる）
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
]


def credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=config.env("YT_REFRESH_TOKEN"),
        token_uri=TOKEN_URI,
        client_id=config.env("YT_CLIENT_ID"),
        client_secret=config.env("YT_CLIENT_SECRET"),
        scopes=SCOPES,
    )
