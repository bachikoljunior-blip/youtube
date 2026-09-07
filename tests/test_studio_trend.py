"""`studio.trend` —— 台帳から「齢 → 再生」の並びを出す（§7 の判定を1点で下さないため）。

実測 2026-09-07 18:3x JST（optimizer・Opus）: §7 が 2回 続けて、平らな区間の中で見た1点から
「止まった」と書いていた（1本目 9.6h〜28.4h が平ら → 32.6h で 139・2本目 4.4h〜6.6h が平ら → 8.6h で 68）。
ここで止めるのは「並びのうち最後の点だけを見せる」形に戻ること。
"""
import datetime as dt

from studio import trend
from studio.common import JST

NOW = dt.datetime(2026, 9, 7, 18, 30, tzinfo=JST)


def _m(vid, at, age_h, views):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h, "views": views, "likes": 0, "title": vid}


ROWS = [
    {"event": "scheduled", "id": "2026-09-07-x", "at": "2026-09-07T02:00:00+09:00", "video_id": "NEW1"},
    _m("NEW1", "2026-09-07T16:30:00+09:00", 6.5, 28),
    _m("NEW1", "2026-09-07T18:30:00+09:00", 8.5, 68),
    _m("OLD1", "2026-09-07T16:30:00+09:00", 7.5, 73),
    _m("OLD1", "2026-09-07T18:30:00+09:00", 9.5, 73),
]


def test_1本の並びが全部出る():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "6.5h 28 → 8.5h 68" in out, out  # 最後の点だけにしない
    assert "7.5h 73 → 9.5h 73" in out, out


def test_直近の伸びが出る():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "[直近 +40回 / 2.0h]" in out, out
    assert "[直近 +0回 / 2.0h]" in out, out


def test_こちらの作りと旧作りを分ける():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "新 NEW1" in out and "旧 OLD1" in out, out


def test_同じ日の本は同じ束に並ぶ():
    out = trend.lines(ROWS, now=NOW)
    assert out[0] == "09/07（2本）", out


def test_古い本は落ちる():
    old = ROWS + [_m("ANCIENT", "2026-09-07T18:30:00+09:00", 24 * 9, 500)]
    out = "\n".join(trend.lines(old, now=NOW, within_h=24 * 3))
    assert "ANCIENT" not in out, out


def test_公開の刻は齢から戻す():
    pub = trend.published_at(trend.series(ROWS)["NEW1"])
    assert pub.strftime("%m/%d %H:%M") == "09/07 10:00", pub


def test_平らは止まりではないと必ず書く():
    # この一文を消すのは、平らを「止まった」と読んでよいと決めたとき（trend.py の覆る条件）。
    assert "平らは「止まった」ではない" in trend.lines(ROWS, now=NOW)[-1]


# ---- 伸びたことのない帯（2026-09-08 04:4x・optimizer・Opus） -------------------
#
# §7 は 10:2x・14:2x・16:3x・00:5x と、平らな点から「止まった／絞られている」を4回 引いた。
# `_growth()` は直近2点を出すが、**その2点がどの刻に落ちたか**は見えない。台帳の実測:
# 02:00〜10:00 JST に2点目が落ちた組は **0/178 しか伸びていない**（それ以外は 15/371）。
# ＝ この帯の回は、何を見ても平ら。だから「止まった」と書けない。

DEAD_NOW = dt.datetime(2026, 9, 8, 4, 45, tzinfo=JST)
LIVE_NOW = dt.datetime(2026, 9, 7, 18, 45, tzinfo=JST)

FLAT_IN_BAND = [_m("A1", "2026-09-08T02:40:00+09:00", 16.0, 100),
                _m("A1", "2026-09-08T04:40:00+09:00", 18.0, 100)]
GREW_OUT_OF_BAND = [_m("B1", "2026-09-07T16:40:00+09:00", 6.0, 10),
                    _m("B1", "2026-09-07T18:40:00+09:00", 8.0, 68)]


def test_帯の中と外を数え分ける():
    """`dead_window` は measured の連続2点を、2点目の刻で分けて（伸びた, 全体）を返す。"""
    nm, nt, om, ot = trend.dead_window(FLAT_IN_BAND + GREW_OUT_OF_BAND)
    assert (nm, nt) == (0, 1)
    assert (om, ot) == (1, 1)


def test_帯の中で回すと読めないと言う():
    """**04:4x のこの回が、そう出た**（15本 全部 +0）。帯の中の「平ら」を判定に使わせないための1行。"""
    got = "\n".join(trend.lines(FLAT_IN_BAND, now=DEAD_NOW))
    assert "伸びたことのない帯" in got and "読めません" in got


def test_帯の外なら黙る():
    """帯の外の回には出さない —— 毎回 出る警告は読み飛ばされる。"""
    got = "\n".join(trend.lines(GREW_OUT_OF_BAND, now=LIVE_NOW))
    assert "伸びたことのない帯" not in got


def test_交絡を黙って隠さない():
    """**刻と齢は、この台帳では分けられない**（公開が 10:00 JST に揃っており、
    この帯は「齢 16〜19h／40〜43h」と完全に重なる）。それを書かずに
    「この帯では伸びない」とだけ出すのは、§7 が 3回 踏んだ形そのもの。"""
    got = "\n".join(trend.lines(FLAT_IN_BAND, now=DEAD_NOW))
    assert "交絡" in got and "齢" in got


def test_数は写しではなく台帳から数える():
    """註の 178/178 が古くなっても印字は追随すること（写しを持たない）。"""
    grew_in_band = [_m("C1", "2026-09-08T02:40:00+09:00", 16.0, 100),
                    _m("C1", "2026-09-08T04:40:00+09:00", 18.0, 105)]
    assert trend.dead_window(grew_in_band)[:2] == (1, 1)
    assert "1/1" in "\n".join(trend.lines(grew_in_band, now=DEAD_NOW))
