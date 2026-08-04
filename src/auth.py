"""YouTube API の OAuth 認証情報。

リフレッシュトークンだけを secrets に置き、実行のたびにアクセストークンを取り直す。
"""
from __future__ import annotations

import re

from google.oauth2.credentials import Credentials

from . import config

TOKEN_URI = "https://oauth2.googleapis.com/token"

# force-ssl は再生リストへの追加とコメント投稿に要る。upload/readonly だけでは
# どちらもできない。スコープは refresh token に焼き込まれるので、後から足すと
# トークンの取り直しになる。最初から入れておく。
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def _clean(value: str) -> str:
    """手入力ゆえの事故を黙って直す。

    スマホで設定欄に貼るとき、前後の空白と「二重ペースト」がよく起きる
    （補完がもう一度発火して同じ値が2つ繋がる）。後者に対して Google が返すのは
    invalid_client — The OAuth client was not found で、クライアントを消したように
    読めて原因に辿り着けない。どちらも直し方が一意なので、落とさずに直す。
    """
    value = (value or "").strip()
    value = re.sub(r"^(\d+-)\1", r"\1", value)
    value = re.sub(r"(\.apps\.googleusercontent\.com)\1$", r"\1", value)
    return value


def credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=_clean(config.env("YT_REFRESH_TOKEN")),
        token_uri=TOKEN_URI,
        client_id=_clean(config.env("YT_CLIENT_ID")),
        client_secret=_clean(config.env("YT_CLIENT_SECRET")),
        scopes=SCOPES,
    )


def explain(error: Exception) -> str:
    """認証エラーに、原因が分かるヒントを足す。"""
    text = str(error)
    if "invalid_grant" in text:
        return (
            f"{text}\n"
            "→ OAuth同意画面が「テスト」のままだと refresh token は7日で失効します。\n"
            "   同意画面を「本番環境に公開」してから、トークンを取り直してください。"
        )
    if "invalid_client" in text:
        return (
            f"{text}\n"
            "→ YT_CLIENT_ID / YT_CLIENT_SECRET の貼り間違いです。値が二重になっていないか確認を。"
        )
    return text
