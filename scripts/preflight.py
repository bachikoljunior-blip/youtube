#!/usr/bin/env python3
"""投稿前の環境チェック。何が足りないかを一覧で出す。

    python scripts/preflight.py
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from src import config  # noqa: E402

OK, NG = "  OK  ", "  NG  "
problems: list[str] = []


def check(label: str, ok: bool, hint: str = "") -> None:
    print(f"[{OK if ok else NG}] {label}")
    if not ok:
        problems.append(f"{label} — {hint}")


def main() -> int:
    print("=== 環境チェック ===\n")

    for name, hint in [
        ("YT_CLIENT_ID", "scripts/get_refresh_token.py の出力を登録"),
        ("YT_CLIENT_SECRET", "同上"),
        ("YT_REFRESH_TOKEN", "同上"),
        ("GOOGLE_TTS_API_KEY", "GCP のAPIキー。Cloud Text-to-Speech API の有効化も必要"),
        ("PEXELS_API_KEY", "https://www.pexels.com/api/new/ で無料発行"),
    ]:
        check(f"環境変数 {name}", bool(os.environ.get(name, "").strip()), hint)

    check("ffmpeg", bool(shutil.which("ffmpeg")), "apt-get install -y ffmpeg")
    check("ffprobe", bool(shutil.which("ffprobe")), "ffmpeg に同梱")
    check(
        "claude CLI",
        bool(shutil.which("claude")),
        "npm install -g @anthropic-ai/claude-code",
    )

    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("[ 注意 ] ANTHROPIC_API_KEY が設定されていますが、実行時に無視します（サブスクを使うため）")

    if shutil.which("claude"):
        # 実際に1往復させて、サブスク認証が通っているかまで見る
        from src.claude_cli import ClaudeCliError, ask
        from pydantic import BaseModel, Field

        class Ping(BaseModel):
            ok: bool = Field(description="常に true")

        try:
            ask(Ping, "疎通確認です。ok を true にした JSON を返してください。",
                model=config.load_channel()["generation"]["model"], max_attempts=1, timeout=180)
            check("Claude Code 認証", True)
        except ClaudeCliError as exc:
            check("Claude Code 認証", False, f"`claude setup-token` を実行 ({str(exc)[:160]})")

    try:
        from src.thumbnail import _font
        _font(40)
        check("日本語フォント", True)
    except Exception as exc:
        check("日本語フォント", False, f"apt-get install -y fonts-noto-cjk ({exc})")

    if os.environ.get("GOOGLE_TTS_API_KEY", "").strip():
        response = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params={"key": os.environ["GOOGLE_TTS_API_KEY"]},
            json={
                "input": {"text": "テスト"},
                "voice": {"languageCode": "ja-JP", "name": "ja-JP-Neural2-D"},
                "audioConfig": {"audioEncoding": "MP3"},
            },
            timeout=45,
        )
        check(
            "Cloud Text-to-Speech API",
            response.status_code == 200,
            f"HTTP {response.status_code}: {response.text[:200]}",
        )

    if os.environ.get("PEXELS_API_KEY", "").strip():
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": os.environ["PEXELS_API_KEY"]},
            params={"query": "office", "per_page": 1},
            timeout=45,
        )
        check("Pexels API", response.status_code == 200, f"HTTP {response.status_code}")

    if all(os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        try:
            from googleapiclient.discovery import build
            from src.auth import credentials

            youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
            channels = youtube.channels().list(part="snippet,status", mine=True).execute()
            items = channels.get("items", [])
            check("YouTube 認証", bool(items), "リフレッシュトークンを取り直してください")
            if items:
                snippet = items[0]["snippet"]
                print(f"        → チャンネル: {snippet['title']} ({items[0]['id']})")
        except Exception as exc:
            check("YouTube 認証", False, str(exc)[:200])

    unused = [t for t in config.load_topics()["topics"] if not t.get("used")]
    check(f"未使用トピック {len(unused)} 件", len(unused) > 0, "config/topics.yaml に追加")

    print()
    if problems:
        print("=== 未解決 ===")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("すべて通りました。投稿できます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
