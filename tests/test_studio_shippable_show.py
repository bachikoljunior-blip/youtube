"""**在庫の行は、数えた本を全部 名前で出すこと**（`studio/cli.shippable_line`）。

## なぜ（2026-09-19 19:xx・optimizer・Opus 5・ultracode に実物で踏んだ）

見出しは「**出せる 7本**」と数えるのに、並ぶ行は `ok[:6]` で **6本**でした。
落ちるのは名前のいちばん後ろ（`dirs` は名前順）＝ 実物は
`2026-09-21-kuriage-64sai-short`（焼けて・輪も閉じて・まだ上げていない本）が
**見出しの数にだけ在って、行に無い**状態。

**この行は「きょうの 6枠 をどう埋めるか」を決める回がいちばん読む行です。**
ショートが 4本 しか見えなければ、その回は「**2本 は長尺でしか埋まらない**」と読みます
（実物は 5本 で、長尺は 1本 でよい）。**長尺の 1本あたり再生は 中央 2回・ショートは 829回**
（`trend.form_yield`）なので、**この 1行 の食い違いが、その日の再生を丸ごと落とします。**

**覆る条件**: `day_upload_cap()` が 12 を越えたら、`SHIPPABLE_SHOW` も一緒に上げること
（この検査が先に落ちます）。**数の出どころは 1か所にできません** ——
あちらは日枠から、こちらは画面の行数から出るためです。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio import cli  # noqa: E402


def test_行数の上限は_1日に上げられる本数より大きい() -> None:
    """**同じにしないこと** —— 6枠 を決める回が、6本目 の先に在る本を 1本も見られません。"""
    assert cli.SHIPPABLE_SHOW > 6, (
        f"`SHIPPABLE_SHOW`（{cli.SHIPPABLE_SHOW}）が、いまの 1日 6本 と同じか小さい ＝ "
        "枠を決める回が在庫の後ろを見られません"
    )


def test_隠したぶんは_ほかN本_と言う() -> None:
    """**上限は残すが、隠した事実は隠さない。**"""
    src = (ROOT / "studio" / "cli.py").read_text(encoding="utf-8")
    i = src.index("def shippable_line(")
    body = src[i : src.index("\ndef ", i + 10)]
    assert "SHIPPABLE_SHOW" in body, "在庫の行が、また裸の数で切っています"
    assert "…ほか" in body, (
        "上限で切ったのに「…ほか N本」を出していません —— "
        "見出しの数と並ぶ行が、また食い違います"
    )
