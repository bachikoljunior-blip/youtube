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
    """**印字される数は、全部この周に数えたものであること。**

    ## 2026-09-05 07:1x —— この検査は、べた書きを1つ**守って**いました

    ここは 09/05 04:0x まで、こう書いてありました:

        assert "この周は数え直していません" in joined   # 符号検定の行

    ＝ **「べた書きが在ること」を検査が要求していました。** 守られていたのは
    09/04 23:5x の回が焼き付けた「12件中 9件・中央 ×2.89・片側 p=0.073」で、
    **同じ帳面をこの回に数え直したら 7組中 6組・×2.01・p=0.062** ——
    組の数も倍率も p も合っていません。

    しかもその行は、すぐ上の `outside_long_length_band` の docstring が
    「**べた書きは必ず古くなります**」と書いた**真下**に在りました。
    **言っている所と、している所が別** —— この repo でいちばん多い壊れ方です。

    いまは符号検定も `length_control_lines()` が毎周 数えるので、
    **「この周は数え直していません」と名乗る行は、1つも在ってはいけません。**
    """
    lines = dp.draft_length_lines("GFvAcxvDmYM")
    if not lines:
        return                     # 控えも `duration_s` も無い repo では見ない
    joined = "\n".join(lines)
    assert "この周に数えた" in joined, "数え直した行が、そう名乗っていません"
    assert "この周は数え直していません" not in joined, (
        "べた書きの行が戻っています（この行の数は毎周 数え直すこと）")
    for frozen in ("12件中 9件", "×2.89", "p=0.073"):
        assert frozen not in joined, (
            f"09/04 23:5x の符号検定を写した数が戻っています: {frozen}")


def _short_row(secs: int, views: int, days: int, ch: str, at, dt):
    pub = at - dt.timedelta(days=days)
    return {"at": at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "id": f"s{secs}{views}{days}{ch}", "views": views, "secs": secs,
            "form": "long", "channel": ch, "title": "t",
            "published": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "q": "q"}


def test_the_controls_can_reverse_the_raw_ratio(tmp_path):
    """**齢を止めると向きが変わる帳面で、生の倍率とは違う数が出ること。**

    ## なぜ要るか（2026-09-05 07:1x に実測して足した）

    `outside_long_length_band()` は**齢で割って**いますが、それは交絡を抜きません ——
    1日あたりの再生は齢とともに落ちるので、**片方の帯が新しいだけで速く見えます。**
    実物の帳面がまさにそうでした: spearman(secs, age) = **-0.344**
    （長尺 n=334・長い本ほど新しい）。

    ここでは、それを**極端にした帳面**を作ります —— 長い帯を全部 新しく、
    短い帯を全部 古くすると、**1日あたりの生の中央は長いほうが勝ちますが、
    同じチャンネルの中で比べると短いほうが勝ちます。**
    `sign` がその向きを拾えなければ、この計器は交絡を抜いていません。
    """
    import datetime as dt
    at = dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc)
    rows = []
    # 3チャンネルとも、**同じチャンネルの中では 20〜25分 のほうが速い**
    for ch in ("a", "b", "c"):
        rows.append(_short_row(1300, 2000, 20, ch, at, dt))    # 100回/日
        rows.append(_short_row(1600, 6000, 200, ch, at, dt))   #  30回/日
    p = tmp_path / "niche_corpus.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    got = dp.outside_length_controls("long", path=p)
    assert got is not None
    # 交絡が在ること（長い本ほど新しい…ではなく、ここでは長い本ほど**古い**）
    assert got["rho"] is not None and got["rho"] > 0, got["rho"]
    # チャンネルを止めたら、25〜30分 は1組も勝っていない
    assert got["sign"] is not None
    assert got["sign"]["pairs"] == 3, got["sign"]
    assert got["sign"]["wins"] == 0, got["sign"]
    assert got["sign"]["x"] < 1.0, got["sign"]


def test_the_controls_are_printed_next_to_the_raw_ratio():
    """**生の倍率だけを印字しないこと。**3つの脚が並ぶこと。"""
    lines = dp.draft_length_lines("GFvAcxvDmYM")
    if not lines:
        return
    joined = "\n".join(lines)
    for tag in ("[交絡]", "[齢をそろえた]", "[チャンネルを止めた]"):
        assert tag in joined, f"{tag} の行が印字されていません"


def test_small_medians_do_not_print_as_zero():
    """ショートの帯（0.18 対 0.90回/日）が「0回/日 対 1回/日」にならないこと。"""
    assert dp._vpd(0.18) == "0.18"
    assert dp._vpd(0.9) == "0.90"
    assert dp._vpd(2094.0) == "2,094"


def test_the_next_book_length_is_printed_on_the_main_screen():
    """**規則3 が名指しする1本の尺が、`[きょうの1本]` に出ること。**

    ## なぜ要るか（2026-09-05 04:0x に踏んだ）

    `draft_length_lines()` は 09/04 23:5x から在ったのに、**この画面には1度も
    出ていませんでした。** 呼び手は `outside_long_lines()` の `if have:` の中だけで、
    `have` は**まだどの日にも決まっていない池の下書き**です。外の型の下書きが
    全部ほかの日に決まった時点（実測 09/05: 7本すべて）で `have` は空になり、
    **規則3 が名指ししている当の1本の尺は、どの回にも見えなくなりました。**

    ＝ 毎周の画面はこの本について「焼き直して得られる脚は 0本」だけを刷り、
    帯でいちばん大きく効いている軸（×2.6）が**決める側の目に1度も入っていなかった。**

    **この repo でいちばん多い壊れ方（言っている所と、している所が別）**の、
    印字の側です。`script_writer.OUTSIDE_RULE_LEGS` の尺の節は
    「**狙いの帯に居るかは `daily_pick.draft_length_lines()` が毎周 印字する**」と
    書いてありました —— **書いてあって、印字されていませんでした。**

    **覆る条件**: 次に出る本が 長尺 でなくなったら、この行は出ません（切れ目は
    外の長尺の帯から引いた数で、ショートには当たらない）。そのときはこの検査も黙ります。
    """
    src = (ROOT / "src" / "daily_pick.py").read_text(encoding="utf-8")
    head = src.split('次に出る本 `{next_row.get(', 1)[1][:4000]
    assert "draft_length_lines" in head, (
        "`[きょうの1本]` の「次に出る本」の直後で尺を印字していません"
        "（池の下書きにしか出ない形へ戻っています）")


def test_the_screen_only_prints_the_length_for_long_form():
    """切れ目は**外の長尺の帯**から引いた数 —— ショートに当てないこと。"""
    src = (ROOT / "src" / "daily_pick.py").read_text(encoding="utf-8")
    head = src.split('次に出る本 `{next_row.get(', 1)[1][:4000]
    # **註のコメントにも関数名が出ます** —— 見るのは「呼んでいる所」の手前だけ。
    guard = head.split("out.extend(draft_length_lines", 1)[0]
    assert 'draft_form == "長尺"' in guard, (
        "尺の行が、形で守られていません（ショートにも出ます）")
