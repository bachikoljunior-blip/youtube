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

from src import config  # noqa: E402

OK, NG, WARN = "  OK  ", "  NG  ", " 任意 "
problems: list[str] = []


def check(label: str, ok: bool, hint: str = "", required: bool = True) -> None:
    print(f"[{OK if ok else (NG if required else WARN)}] {label}")
    if not ok and required:
        problems.append(f"{label} — {hint}")
    elif not ok:
        print(f"        → {hint}")


def check_script_names() -> None:
    """scripts/ に標準ライブラリと同じ名前のファイルを置いていないか。

    `python scripts/upload_only.py` は scripts/ を sys.path の先頭に置く。
    そこに標準ライブラリと同名のファイルがあると、そのディレクトリから起動した
    **全部のスクリプト**が黙って壊れる。実際に scripts/inspect.py を足した直後、
    投稿が `module 'inspect' has no attribute 'signature'` で落ちた。

    壊れ方が原因から遠いので、気づくのに時間がかかる。機械に見せておく。
    """
    shadowed = sorted(
        p.stem for p in Path(__file__).resolve().parent.glob("*.py")
        if p.stem in sys.stdlib_module_names
    )
    check(
        "scripts/ の名前が標準ライブラリと衝突していない",
        not shadowed,
        f"{', '.join(f'scripts/{s}.py' for s in shadowed)} の名前を変えてください",
    )


def main() -> int:
    print("=== 環境チェック ===\n")
    check_script_names()

    for name, hint in [
        ("CLAUDE_CODE_OAUTH_TOKEN", "手元で `claude setup-token`"),
        ("YT_CLIENT_ID", "OAuth 2.0 Playground で取得（docs/SETUP.md）"),
        ("YT_CLIENT_SECRET", "同上"),
        ("YT_REFRESH_TOKEN", "同上"),
    ]:
        check(f"環境変数 {name}", bool(os.environ.get(name, "").strip()), hint)

    has_google_tts = bool(os.environ.get("GOOGLE_TTS_API_KEY", "").strip())
    check(
        "環境変数 GOOGLE_TTS_API_KEY",
        has_google_tts,
        "未設定なら open-jtalk（無料）を使います。声の自然さは落ちます",
        required=False,
    )

    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("[ 注意 ] ANTHROPIC_API_KEY は実行時に無視します（サブスクを使うため）")

    check("ffmpeg", bool(shutil.which("ffmpeg")), "apt-get install -y ffmpeg")
    check("ffprobe", bool(shutil.which("ffprobe")), "ffmpeg に同梱")
    check("claude CLI", bool(shutil.which("claude")), "npm install -g @anthropic-ai/claude-code")

    tts_cfg = config.load_channel()["generation"]["tts"]
    from src.tts import choose_engine

    engine = choose_engine(tts_cfg)
    if engine == "open-jtalk":
        check(
            "open_jtalk",
            bool(shutil.which("open_jtalk")),
            "apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic "
            "hts-voice-nitech-jp-atr503-m001",
        )

    try:
        from src.thumbnail import _font

        _font(40)
        check("日本語フォント", True)
    except Exception as exc:
        check("日本語フォント", False, f"apt-get install -y fonts-noto-cjk ({exc})")

    # 図解の描画。ここが通れば映像素材は自前で全部まかなえる。
    try:
        from src import visuals

        out = visuals.render(
            [{"kind": "stat", "headline": "疎通確認", "stat": "OK", "note": "テスト"}],
            config.BUILD_DIR / "_preflight",
        )
        size = out[0].stat().st_size
        check("図解の描画 (Playwright)", size > 5000, f"PNG が {size} バイトしかありません")
    except Exception as exc:
        check("図解の描画 (Playwright)", False,
              f"python -m playwright install --with-deps chromium ({str(exc)[:160]})")

    if shutil.which("claude"):
        from pydantic import BaseModel, Field

        from src.claude_cli import ClaudeCliError, ask

        class Ping(BaseModel):
            ok: bool = Field(description="常に true")

        try:
            ask(Ping, "疎通確認です。ok を true にした JSON を返してください。",
                model=config.load_channel()["generation"]["model"], max_attempts=1, timeout=180)
            check("Claude Code 認証", True)
        except ClaudeCliError as exc:
            check("Claude Code 認証", False, f"`claude setup-token` を実行 ({str(exc)[:160]})")

    if all(os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        try:
            from googleapiclient.discovery import build

            from src.auth import credentials, explain

            youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
            items = youtube.channels().list(part="snippet,statistics", mine=True).execute().get("items", [])
            check("YouTube 認証", bool(items), "リフレッシュトークンを取り直してください")
            if items:
                snippet, stats = items[0]["snippet"], items[0]["statistics"]
                print(f"        → {snippet['title']}｜登録者 {stats.get('subscriberCount', '?')}人"
                      f"／動画 {stats.get('videoCount', '?')}本")
        except Exception as exc:
            check("YouTube 認証", False, explain(exc)[:300])

    # 在庫は「全テーマ − 投稿済み」でしか出せない。投稿済みはチャンネルから引く。
    # ここを `if not problems` で飛ばしていたので、**他の項目が1つでも落ちていると
    # posted が空になり、在庫が「全件」に化けていました**（2026-08-15 に実測で発覚。
    # CLAUDE_CODE_OAUTH_TOKEN がコンテナに無いだけで毎回そうなり、
    # 真の12件が **40件** と出ていた）。在庫切れは M14 の律速そのもの
    # （`docs/MEANS.md`「着手して分かった律速 —— 手段ではなく在庫でした」）なので、
    # **多いほうに間違える計器は、いちばん見たいときに黙る。**
    #
    # 直し: 引けたときだけ数える。**引けなかったら数を出さない。**
    # 「分からない」を「たくさんある」と書かないこと。
    total = len(config.load_topics()["topics"])
    try:
        from src.history import posted_topic_ids

        posted = posted_topic_ids()
    except Exception as exc:
        check(f"未投稿テーマ ?件 / 全{total}件 — 投稿済みを引けませんでした",
              False, f"チャンネルに繋がりません（{str(exc)[:120]}）。在庫は判定できていません")
    else:
        unused = [t for t in config.load_topics()["topics"] if t["id"] not in posted]
        check(f"未投稿テーマ {len(unused)} 件 / 全{total}件",
              len(unused) > 0, "config/topics.yaml に追加")

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
