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
    if is_upload_cap(error):
        return (
            f"{text}\n"
            "→ **1日に投稿できる本数の枠です**（Data API の10,000単位とは別の枠）。\n"
            "   2026-08-17 の実測で、**92本目までは通り、93本目でここに当たりました。**\n"
            "   戻るのは太平洋時間の0時＝**JST 16:00 ごろ**。\n"
            "   **この回でこれ以上は投稿できません。**作った本は build/ に残るので、\n"
            "   枠の戻った回に `scripts/upload_only.py <ID> \"\" <日付>@<時>` で打ち直せます。"
        )
    return text


# **投稿の本数枠（Video Uploads per day）に当たったか。**
#
# 2026-08-17 10:5x にこの環境で初めて踏みました。**Data API の日枠とは別物です。**
#
#     Data API の日枠   10,000単位   **403 quotaExceeded**    読み・thumbnails.set が落ちる
#     投稿の本数枠      1日92本      **429 rateLimitExceeded** **videos.insert そのものが落ちる**
#
# `docs/trigger_main.md` §5 は 03:5x の実測から
# 「**日枠が切れていても `upload` は選べます**」と書いていました。
# **その回は正しかった** —— あの時点で、この日の投稿はまだ62本でした。
# **1つの枠を測って、もう1つの枠が無いことにしていた**だけです。
#
# 見分けが要るのは、**当たったら残り全部が必ず落ちる**からです。
# この回は最初の1本が通ったあと6本を撃ち、**6本とも同じ429**で捨てました。
def is_upload_cap(error: Exception) -> bool:
    """**1日の投稿本数の枠**に当たったか（HTTP 429・Video Uploads）。

    枠が戻るまで、**この回のこれ以降の投稿はすべて落ちます。**
    呼ぶ側は、次の1本を撃つのではなく**止まること。**
    """
    text = str(error)
    if "rateLimitExceeded" not in text and "429" not in text:
        return False
    return "Video Uploads" in text or "uploadLimitExceeded" in text


# **Data API の単位枠（10,000単位）に当たったか。**
#
# `is_upload_cap`（上・429）と**対**です。2つは**別々に閉じます**
# （8/17 05:2x の実測 —— `insert`(1600) が通るのに `update`(50) が 403。
# **安いほうが先に閉じます**）。
#
# 見分けが要る理由は上と同じで、**当たったらこの窓の残り全部が落ちる**からです。
# ただし**止め方は逆**です —— 429 は投稿そのものを止めますが、403 は
# **読みと `thumbnails.set` / `videos.update` だけ**を止めるので、
# **投稿は続けること**（`docs/trigger_main.md` §5）。
def is_day_quota(error: Exception) -> bool:
    """**Data API の単位枠**に当たったか（HTTP 403・quotaExceeded）。

    当たったら `src.upload_cap.note_quota_hit()` に残すこと。**残さないと、
    次の回は時計で推測するしかありません**（それが 15回鳴って当たり2回の
    `missing_thumbnail` でした）。
    """
    text = str(error)
    if "403" not in text:
        return False
    low = text.lower()
    return "quotaexceeded" in low or ("quota" in low and "exceeded" in low)


# **見分けるだけでは、次の回に何も残りません**（2026-08-19 に実測して足した）。
#
# `is_day_quota` の docstring は「当たったら `note_quota_hit()` に残すこと」と
# **約束の形**で書いてありました。**約束は破れます** —— 実際に残していたのは
# `thumbnails.set` の2か所だけで、`history` 4件・`uploader` 4件・
# `reschedule` 1件・`status` 1件は**1行も残していませんでした**。
#
# **`src/analytics.py` はここに数えません。** あちらは **YouTube Analytics（別枠）**で、
# その 403 をこの帳面に書くと、**尽きていない日枠を「尽きた」と言わせます**
# （外す向きが逆で、そちらのほうが高い）。**混ぜないこと。**
#
# 実害は測れます。2026-08-19 03:5x（窓は 08/18 07:00Z→08/19 07:00Z）の実測:
#
#     status.py が channels.list / videos.list で **403 を4回**受けた
#     前の回の `videos.update` も **403**（受け取り帳 556dd42d）
#     それでも `data/day_quota.jsonl` の**この窓の行は 0件**
#     → `upload_cap.day_quota()` は **open=True**（＝「まだ押してよい」）と答える
#
# つまり **`retro.py` と `status.py` が読む「単位が残っているか」が、
# 事実と逆を向いていました。** この repo が通算10回踏んでいる「片方だけ」の11件目です。
#
# **だから、見分ける所と残す所を1つにします。** 呼ぶ側は `is_day_quota` ではなく
# こちらを呼ぶこと（`tests/test_day_quota_recorded.py` が、忘れた呼び出し側を
# AST で名指しします —— **約束ではなく検査で持たせる**）。
def note_day_quota(error: Exception, detail: str = "") -> bool:
    """日枠（単位）の 403 か。**そうなら、その場で帳面に残してから True を返す。**

    `is_day_quota` は**純粋な述語のまま**にしてあります（検査や表示から
    呼ばれる所で、副作用に帳面が汚れると、窓を「閉じている」と誤らせます）。
    **残す責任はこちらが持ちます。**

    帳面に書けなくても、**判定は返します** —— 書けないことを理由に
    呼ぶ側の分岐を変えないこと（`upload_cap.state()` と同じ考え方）。
    """
    if not is_day_quota(error):
        return False
    try:
        from . import upload_cap

        upload_cap.note_quota_hit(detail=(detail or str(error))[:200])
    except Exception:                                          # noqa: BLE001
        pass
    return True
