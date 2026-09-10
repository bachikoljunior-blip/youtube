"""`trend.channel_line_short` の検査（2026-09-10 23:2x・optimizer・Opus）。

**なぜ足したか**: `channel_line`（実測 **1,035字**）を `cmd_status` と `trend.report` が
**同じ周に、1字も違わずに 2度** 印字していた（`optimizer` は毎周 両方を撃つ）。
22:5x が足した `scripts/output_growth.py` は `trend` の側**だけ**を測るので、
この重なりは**伸びとしても重なりとしても数えられていなかった**。

**陽性対照つき** —— 下の `test_positive_control_*` は、この回の直しを外すと落ちる形で書いてある。
"""
from __future__ import annotations

import re
from pathlib import Path

from studio import trend

CLI = Path(__file__).resolve().parents[1] / "studio" / "cli.py"


def _row(at: str, subs: int, views: int, videos: int = 269) -> dict:
    return {"at": at, "id": "UCxxx", "event": "channel",
            "subs": subs, "views": views, "videos": videos}


def _m(at: str, vid: str, views: int, age_h: float) -> dict:
    return {"at": at, "id": vid, "event": "measured", "views": views, "age_h": age_h}


def _flat_over_rows() -> list[dict]:
    """実物の形（21:2x に (m) の覆る条件 (1) が初めて引かれた並び）。"""
    return [_row("2026-09-10T15:24:00+09:00", 27, 84781),
            _row("2026-09-10T16:41:00+09:00", 27, 84781),
            _row("2026-09-10T18:00:00+09:00", 27, 84781),
            _row("2026-09-10T19:14:00+09:00", 27, 84781),
            _m("2026-09-10T15:24:00+09:00", "lQHX9LJ80Sg", 685, 53.3),
            _m("2026-09-10T18:38:00+09:00", "lQHX9LJ80Sg", 685, 56.6),
            _m("2026-09-10T19:14:00+09:00", "lQHX9LJ80Sg", 687, 57.3)]


def _growing_rows() -> list[dict]:
    return [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 28, 84100),
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 160, 16.0)]


def test_短い行は_full_の3分の1より短い():
    """**陽性対照**: `channel_line_short` が `channel_line` を返す形に戻すと落ちる。"""
    rows = _flat_over_rows()
    full, short = trend.channel_line(rows), trend.channel_line_short(rows)
    assert len(short) * 3 < len(full), (len(short), len(full))


def test_短い行と_full_は同じ判定を言う():
    """覆る条件 (2) —— 2つが別々に数えていないこと（同じ `channel_growth` の返りから作る）。"""
    for rows in (_flat_over_rows(), _growing_rows()):
        g = trend.channel_growth(rows)
        short = trend.channel_line_short(rows)
        if g["over"]:
            assert "覆る条件 (1) が引かれています" in short
            assert "「チャンネルが止まった」と読まないこと" in short
            assert f"{g['over_streak']}/{trend.CHANNEL_FLAT_LAPS} 塊" in short
        else:
            assert "覆る条件 (1) が引かれています" not in short


def test_引かれていない窓では_0回_を読む前に見る行が出る():
    short = trend.channel_line_short(_growing_rows())
    assert "本ごとの 0回 を読む前に見ること" in short
    assert "その本の配りの側" in short


def test_数は落とさない():
    """短くしてよいのは derivation だけ —— 決めと**数**は残すこと。"""
    rows = _flat_over_rows()
    g = trend.channel_growth(rows)
    short = trend.channel_line_short(rows)
    for n in (f"登録 {g['subs']}", f"総再生 {g['views']}",
              f"{g['laps']}周", f"{g['vid_sum']:+d}回", f"{g['vid_confirmed']:+d}回"):
        assert n in short, n


def test_総再生が動かない窓で登録だけ動いたら短い行も言う():
    rows = [_row("2026-09-10T15:24:00+09:00", 27, 84781),
            _row("2026-09-10T18:38:00+09:00", 28, 84781),
            _row("2026-09-10T20:27:00+09:00", 28, 84781)]
    assert "応答が丸ごと古いのではない" in trend.channel_line_short(rows)


def test_登録も総再生も動かない窓では言わない():
    rows = [_row("2026-09-10T15:24:00+09:00", 28, 84781),
            _row("2026-09-10T18:38:00+09:00", 28, 84781),
            _row("2026-09-10T20:27:00+09:00", 28, 84781)]
    assert "同じ窓で登録は" not in trend.channel_line_short(rows)


def test_点が足りない窓は短い側でもそう言う():
    assert "2点" in trend.channel_line_short([])
    rows = [_row("2026-09-10T15:00:00+09:00", 27, 84781),
            _row("2026-09-10T15:05:00+09:00", 27, 84781)]
    assert "まだ読まないこと" in trend.channel_line_short(rows)


def test_status_は短い側を撃つ():
    """**陽性対照つき**: `cmd_status` が `trend.channel_line(` へ戻ると落ちる。

    **これがこの回の直しの本体**（重なりは関数の側ではなく、呼ぶ側に在った）。
    """
    src = CLI.read_text(encoding="utf-8")
    body = src[src.index("def cmd_status("):]
    body = body[:body.index("\ndef ")]
    assert "trend.channel_line_short(" in body
    assert not re.search(r"trend\.channel_line\(", body)


def test_trend_の側は_full_のまま():
    """**測れる側**（`output_growth` が測るのは `trend` の出力）に derivation を残すこと。

    `trend` から消して `status` に残すと、同じ字が**測れない側へ移る**だけになる。
    """
    rows = _flat_over_rows()
    out = "\n".join(trend.lines(rows))
    assert trend.channel_line(rows) in out
    assert trend.channel_line_short(rows) not in out


# ---- 平らの「読める／読めない」は full と短い行で同じ口から出ること（2026-09-11 04:0x・optimizer・Opus）
# **踏んだ形**: 包絡で読むようにしたら `flat_laps` が 3周 に届き、短い行が
# 「門が引かれました ＝ チャンネルの側を外すこと」と言い出した。**その 3周 は約 1.2時間**で、
# 実測の刻みの手前の平ら（10.2時間）より桁で短い ＝ その平らからは何も読めない。

def _short_flat_rows() -> list[dict]:
    """刻み（+1,625）のあと、包絡が 3周 続けて同じ ＝ **周では門が引ける／時間では読めない**並び。"""
    return [_row("2026-09-10T15:24:00+09:00", 28, 84781),
            _row("2026-09-10T20:00:00+09:00", 28, 84781),
            _row("2026-09-11T02:12:00+09:00", 28, 86406),   # 刻み（手前の平ら 10.8時間）
            _row("2026-09-11T02:48:00+09:00", 28, 86406),
            _row("2026-09-11T03:24:00+09:00", 28, 84781)]   # 遅れた複製 ＝ 包絡は 86,406 のまま


def test_a_flat_shorter_than_the_step_is_not_read_as_stopped():
    g = trend.channel_growth(_short_flat_rows())
    assert g["flat_laps"] >= trend.CHANNEL_FLAT_LAPS      # 周では門に届く
    assert g["flat_readable"] is False                    # 時間では読めない
    short = trend.channel_line_short(_short_flat_rows())
    assert "とは読めません" in short and "チャンネルの側を外すこと" not in short


def test_positive_control_the_guard_is_load_bearing():
    """**陽性対照**: 門（平らの時間）を無効にすると、短い行が「外すこと」に戻ること。"""
    g = dict(trend.channel_growth(_short_flat_rows()))
    assert g["step_flat_h"] is not None and g["flat_h"] < g["step_flat_h"]
    # 刻みが 1つ も無い並び（＝ 比べる相手が無い）なら、門は当たらず周の側で読む
    rows = [_row("2026-09-10T15:24:00+09:00", 28, 84781),
            _row("2026-09-10T20:00:00+09:00", 28, 84781),
            _row("2026-09-11T02:12:00+09:00", 28, 84781)]
    g2 = trend.channel_growth(rows)
    assert g2["step_flat_h"] is None and g2["flat_readable"] is True
    assert "チャンネルの側を外すこと" in trend.channel_line_short(rows)


def test_full_and_short_agree_on_the_flat_verdict():
    """full と短い行が**違う verdict** を言わないこと（`channel_line_short` の覆る条件 (2)）。"""
    rows = _short_flat_rows()
    assert "とは読めません" in trend.channel_line(rows)
    assert "とは読めません" in trend.channel_line_short(rows)
