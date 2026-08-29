"""**`data/day_quota.jsonl` は「失敗しか載らない帳面」です**（2026-08-27）。

## この帳面を、成功の記録として読まないこと

`note_day_quota` は **403 のときだけ**書きます。`note_quota_ok` を呼んでいるのは
`videos.update` と `thumbnails.set` の2か所だけで、**`videos.insert` は
1度も書きません** —— 実測: 4,360行 のうち `videos.insert` の行は **0件**。

**2026-08-27 の回は、その 0 を「今日は1本も投稿できなかった」と読みました。**
そのうえで「`videos.insert` が 0 の日は、その日ぶんの投稿が丸ごと消えます」
「`docs/GOAL.md`『投稿が途切れるのが最大の損失』に真っ向から当たります」と書き、
**その回の いちばん大きい発見**として日誌に残しています。

**事実は逆です。** `data/uploaded.jsonl` の `uploaded_at` を数えると、
同じ日（JST 08/27）の投稿は **25本**。しかも枠が尽きた 16:47 JST より**後**に
**3本**（18:05・18:20・18:40）通っています。**0 は「失敗が0件」でした。**

## だから「insert も ok に書けばいい」としないこと ← **この検査が守るのはここ**

**`videos.insert` は、日枠が尽きていても通ります**（`src/auth.py` の
8/17 05:2x の実測。上の 3本 がそのまま3度目の実測です）。
一方 `note_quota_ok` の意味は

    **その 403 より後に通った ＝ あの 403 は日枠ではなかった**（`quota_ok_after_hits`）

です。**尽きていても通るものを、この帳面の `ok` に書いてはいけません** ——
書いた瞬間、`day_quota().open` が **本当に尽きた窓を「開いている」と答えます。**
そこから `queue_lag`・`live_slots`・`refresh_thumbnail`・`batch_build` が
いっせいに撃ち、全部 403 で落ちて、また閉じる。
**この形は 08/27 に `pytest` 経由で1度 起きています**（`upload_cap._write_path`）。

**覆る条件**: `videos.insert` が日枠の 403 で落ちるところを実測したとき。
そのときは insert も他と同じ袋なので、`ok` に書いてよくなります
（**実測を `docs/JOURNAL.md` に残してから**外すこと）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _sources():
    for rel in ("src", "scripts"):
        for path in sorted((ROOT / rel).rglob("*.py")):
            yield path


def test_videos_insert_を_note_quota_ok_に書いていないこと():
    """**尽きていても通るものを、尽きていない証拠にしないこと。**"""
    bad: list[str] = []
    for path in _sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                    # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name != "note_quota_ok":
                continue
            text = ast.unparse(node)
            if "videos.insert" in text:
                bad.append(f"{path.relative_to(ROOT)}:{node.lineno} {text[:80]}")
    assert not bad, (
        "**`videos.insert` を `note_quota_ok` に書いています。**\n  "
        + "\n  ".join(bad)
        + "\n  insert は日枠が尽きていても通ります（実測3回）。`ok` に書くと、"
          "\n  本当に尽きた窓を `day_quota().open` が『開いている』と答えます。"
          "\n  このファイルの冒頭に、理由と覆る条件があります")


def test_この帳面は成功の記録ではないと書いてあること():
    """**次の回が同じ読み違いをしないように**、読む側の入口に残す。

    ここが落ちたら、註が消えています。**消さないこと** ——
    消えていた 08/27 に、その回の いちばん大きい発見が丸ごと逆でした。
    """
    text = (ROOT / "src" / "upload_cap.py").read_text(encoding="utf-8")
    assert "失敗しか載らない" in text, (
        "`src/upload_cap.py` から「この帳面は失敗しか載らない」の註が消えています。"
        "08/27 の回は、その註が無いせいで `videos.insert` 0件 を"
        "「今日は1本も投稿できなかった」と読みました（実際は 25本）")
