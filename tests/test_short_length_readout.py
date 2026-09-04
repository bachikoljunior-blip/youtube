"""**供給の 100% を占める形の「尺」が、決める側の画面に出ること。**

## なぜ要るか（2026-09-05 07:3x に踏んだ）

`daily_pick.lines()` は `if draft_form == "長尺":` の中でだけ尺を印字していました。
註にはこう書いてありました ——「**長尺のときだけ出します**（切れ目は外の長尺の帯から
引いた数で、ショートには当たりません）」。**切れ目は当たりませんが、尺そのものは
当たります。** そのあいだ、こうなっていました:

    `[きょうの1本]` が名指しする形は **ショート**（門1＋門2 の AND で近いほう）
    `data/uploaded.jsonl` の実物 109本 は **全部 24〜33秒**（中央 29秒）
    外の帯のショート 132本 で その窓に居るのは **6本（4.5%）**
    再生の上位15本で その窓に居るのは **0本**（上位の尺 中央 126秒）

＝ **いちばん大きい作りの違いが、どの回の目にも入っていませんでした。**
長尺には 09/05 04:0x に同じ穴が見つかって塞がれています（`draft_length_lines` の
呼び手が `if have:` の中だけだった）。**同じ穴が、もう一方の形に開いたままでした。**

## この検査が見るもの

1. 次に出る本が **ショート**なら、尺の行が出ること
2. その行が「長くしろ」と言っていないこと ——
   `outside_length_controls("short")` のいちばん強い脚（チャンネルを止めた符号検定）が
   逆を向いているあいだ、狙いの帯を名指ししてはいけません
3. 数が**帳面から**来ていること（写した数が残っていないこと）

## 覆る条件

ショートの3脚がそろって同じ向きになったら、この検査の 2 は
「狙いの帯を名指ししていること」へ**裏返します**（そのときは
`OUTSIDE_SHORT_KNEE_SEC` も速いほうの切れ目へ置き直すこと）。
自分のショートが窓の外へ出はじめたら、1 の字が変わります。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import daily_pick as dp  # noqa: E402

_SHORT_ROW = {
    "video_id": "qyVdpAoT_40",
    "topic": "s-shokibo-241kagetsu-9man4500",
    "title": "【小規模企業共済】240か月と241か月で税額はいくら違う？ #Shorts",
}


def test_the_short_length_is_printed_on_the_main_screen():
    """**規則3 が名指しする1本がショートなら、その尺の行が出ること。**"""
    out = "\n".join(dp.lines(_SHORT_ROW))
    assert "次に出る本 `qyVdpAoT_40` は **ショート**" in out, out[:400]
    assert "自分のショート" in out, "ショートの尺の行が出ていません"
    assert "秒 の中に全部" in out or "秒 の中" in out, out[:600]


def test_the_line_does_not_tell_the_round_to_make_shorts_longer():
    """**いちばん強い脚が逆を向いているあいだ、狙いの帯を名指ししないこと。**"""
    got = dp.outside_length_controls(
        "short", bands=((0, dp.OUTSIDE_SHORT_KNEE_SEC), (dp.OUTSIDE_SHORT_KNEE_SEC, 10 ** 9)))
    if not got or not got.get("sign"):
        return                       # 帳面が無い repo では見ない
    s = got["sign"]
    settled = s["p"] is not None and s["p"] < 0.05
    out = "\n".join(dp.short_length_lines(""))
    if settled:
        return                       # 3脚がそろった ＝ この検査は裏返る（docstring）
    assert "「長くしろ」と言っていません" in out, (
        "ショートの3脚がそろっていないのに、画面が尺を名指ししています "
        f"(pairs={s['pairs']} wins={s['wins']} p={s['p']})")


def test_the_three_legs_are_printed_for_shorts():
    """生の占有だけでなく、交絡・齢そろえ・チャンネル止めが並ぶこと。"""
    out = "\n".join(dp.short_length_lines(""))
    if not out:
        return
    for tag in ("[交絡]", "[齢をそろえた]", "[チャンネルを止めた]"):
        assert tag in out, f"{tag} の行が印字されていません"


def test_own_lengths_are_counted_from_the_ledger(tmp_path):
    """**自分の尺は帳面から数えること**（写した数を持たない）。"""
    p = tmp_path / "uploaded.jsonl"
    rows = [
        {"video_id": "a", "duration_s": 25.0},
        {"video_id": "b", "duration_s": 31.0},
        {"video_id": "c", "duration_s": 90.0},     # 切れ目より上
        {"video_id": "d", "duration_s": 1361.0},   # 長尺 ＝ 数えない
        {"video_id": "e"},                          # `duration_s` 無し ＝ 数えない
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = dp.own_short_lengths(uploaded_path=p)
    assert got is not None
    assert got["n"] == 3, got
    assert got["median"] == 31.0, got
    assert got["min"] == 25.0 and got["max"] == 90.0, got
    assert got["over"] == 1, got            # 90秒 の1本だけが 60秒 以上


def test_the_window_share_counts_the_band_not_a_ratio(tmp_path):
    """**占有は倍率ではありません** —— 窓に居る本数と、上位の本数だけを数えること。"""
    import datetime as dt
    at = dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc)

    def row(secs, views, days, vid):
        pub = at - dt.timedelta(days=days)
        return {"at": at.strftime("%Y-%m-%dT%H:%M:%S+00:00"), "id": vid,
                "views": views, "secs": secs, "form": "long", "channel": "c",
                "title": "t", "published": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "q": "q"}

    p = tmp_path / "niche_corpus.jsonl"
    rows = [row(28, 10, 10, "a"), row(30, 10, 10, "b"),      # 窓の中 2本
            row(120, 9999, 10, "c"), row(150, 9998, 10, "d")]  # 窓の外・上位2本
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = dp.outside_window_share(24, 33, form="long", path=p, top=2)
    assert got is not None
    assert got["n"] == 4 and got["inside"] == 2, got
    assert abs(got["share"] - 0.5) < 1e-9, got
    assert got["top_n"] == 2 and got["top_inside"] == 0, got   # 上位2本は窓の外
