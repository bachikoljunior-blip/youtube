"""**次の1本の形を決める根拠の数を、べた書きにしないこと。**

## なぜ要るか（2026-09-05 04:0x に踏んだ）

`daily_pick.draft_length_lines()` の2行目は、まるごとべた書きの散文でした:

    外の長尺 **365本** を齢で割った実測: 20〜25分 **n=37 823回/日** 対
    25〜30分 **n=34 3,507回/日**（**×4.3**）

09/04 23:5x の回が数えて、その回が文字列に焼き付けたものです。
**同じ帳面（`data/niche_corpus.jsonl`）を 09/05 04:0x に数え直したら、1つも合いませんでした**:

    べた書き   365本   20〜25分 n=37 823回/日   25〜30分 n=34 3,507回/日   ×4.3
    実測       334本   20〜25分 n=33 792回/日   25〜30分 n=24 2,094回/日   ×2.6

帳面は毎周 引き直されるので、**べた書きは必ず古くなります。** そしてこの行は
**次の1本の形を決める根拠**として `[きょうの1本]` に印字されています。

この repo は同じ形を2回 踏んでいます —— `eta.py` の「`per_video` の標本は
2026-08-18 で止まっています」と、`slot_cost` の「1,049回 は 18日前の帯の高さ」。
**どちらも、数えた回が数を写した所で腐りました。**

この検査が見るのは2つだけです。

1. 帯の数が**帳面から数えられている**こと（帳面を差し替えれば数も動く）。
2. 印字にべた書きの数（365 / 823 / 3,507 / ×4.3）が**残っていない**こと。

**切れ目そのもの（25分・`OUTSIDE_LONG_KNEE_SEC`）は定数のままです。**
動かしたのは「その両側がいくつか」だけ ——
切れ目は「どこで割るか」の決めで、帯の数は観測です。

## 覆る条件

前提「外の作り方を写した長尺」が外れたら `draft_length_lines` ごと消えるので、
この file も一緒に消すこと。帯の順が入れ替わったら（下の帯のほうが速くなったら）、
`OUTSIDE_LONG_KNEE_SEC` と `script_writer.OUTSIDE_LONG_RULE` の尺の節を
両方 書き直すこと —— **この検査は順を見ていません**（観測に向きを決めさせない）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import daily_pick as dp  # noqa: E402


def _row(secs: int, views: int, days: int) -> dict:
    import datetime as dt
    at = dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc)
    pub = at - dt.timedelta(days=days)
    return {"at": at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "id": f"v{secs}{views}{days}", "views": views, "secs": secs,
            "form": "long", "channel": "c", "title": "t",
            "published": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "q": "q"}


def test_the_band_is_counted_from_the_ledger(tmp_path):
    """帳面を差し替えたら、数も動くこと（＝ べた書きではないこと）。"""
    p = tmp_path / "niche_corpus.jsonl"
    rows = (
        # 20〜25分 の帯: 100回/日 が3本
        [_row(1300, 1000, 10), _row(1350, 1000, 10), _row(1400, 1000, 10)]
        # 25〜30分 の帯: 400回/日 が2本
        + [_row(1600, 4000, 10), _row(1700, 4000, 10)]
    )
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    got = dp.outside_long_length_band(path=p)
    assert got is not None
    assert got["n"] == 5
    assert got["lo"] == (3, 100.0), got["lo"]
    assert got["hi"] == (2, 400.0), got["hi"]
    assert abs(got["x"] - 4.0) < 1e-9


def test_the_band_is_split_at_the_knee_constant():
    """割る所は `OUTSIDE_LONG_KNEE_SEC`。**帯の数のほうに切れ目を決めさせないこと。**"""
    assert dp._LEN_BANDS[0][1] == dp.OUTSIDE_LONG_KNEE_SEC
    assert dp._LEN_BANDS[1][0] == dp.OUTSIDE_LONG_KNEE_SEC


def test_the_printed_line_has_no_frozen_numbers():
    """印字に 09/04 23:5x のべた書き（365 / 823 / 3,507 / ×4.3）が残っていないこと。"""
    src = (ROOT / "src" / "daily_pick.py").read_text(encoding="utf-8")
    body = src.split("def draft_length_lines", 1)[1].split("\ndef ", 1)[0]
    # **註のコメントは残してよい** —— 何がどう古かったかは、次に来た側の根拠です。
    # 見るのは「印字される側」だけ。
    body = "\n".join(ln for ln in body.splitlines() if not ln.strip().startswith("#"))
    for frozen in ("365本", "823回/日", "3,507回/日", "×4.3"):
        assert frozen not in body, (
            f"`draft_length_lines` に写した数が残っています: {frozen}"
            "（帳面から数えること。写した数は必ず古くなります）")


def test_the_line_says_it_counted_this_round():
    """読み手が「いつの数か」を見分けられること —— 数え直した行と、1回きりの行を分ける。"""
    lines = dp.draft_length_lines("GFvAcxvDmYM")
    if not lines:
        return                     # 控えも `duration_s` も無い repo では見ない
    joined = "\n".join(lines)
    assert "この周に数えた" in joined, "数え直した行が、そう名乗っていません"
    assert "この周は数え直していません" in joined, (
        "1回きりの数（符号検定）が、そう名乗っていません")
