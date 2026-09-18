# -*- coding: utf-8 -*-
"""**面（surface）の行**（`trend.surface_split` / `surface_line`）の検査。

**陽性対照を先に置いてあります** —— 「面が 0回」と「面を測っていない」は、
この repo が 7度 同じ字で出して踏んだ形です:

    (1) `BROWSE_FEATURES` の欄が在る台帳では、その面が `absent` に入らない
    (2) 欄が無い台帳では `absent` に入り、行が **「配られていません」**と言う
    (3) 台帳に行が 1つ も無い／古すぎるときは **「0回ではありません」**と言う

**本体は並びの検査**（`gate_measured_line` → `gate_proof_line` → `surface_line` が
隣り合うこと）です —— 離れた瞬間に、また「中身が悪いから伸びない」の側で読まれます。
"""
import datetime as dt

from studio import trend

# 実物の写し（`data/studio/ledger.jsonl` の `analytics_traffic` 最終行・2026-09-15）。
# **`BROWSE_FEATURES` の欄がありません** ＝ ホームの面は 0回。
REAL_SOURCES = {"SHORTS": 5767, "YT_SEARCH": 163, "SUBSCRIBER": 142, "YT_OTHER_PAGE": 55,
                "YT_CHANNEL": 6, "NO_LINK_OTHER": 3, "SOUND_PAGE": 3, "RELATED_VIDEO": 1,
                "EXT_URL": 1, "PLAYLIST": 1}


def _rows(sources=None, day=None):
    day = day or dt.date.today().isoformat()
    return [{"event": "measured", "id": "a", "views": "1"},
            {"event": "analytics_traffic", "id": day, "start": "2026-09-08",
             "lag_days": 3, "sources": dict(REAL_SOURCES if sources is None else sources)}]


def test_陽性対照_面が在れば_absentに入らない():
    s = trend.surface_split(_rows({**REAL_SOURCES, "BROWSE_FEATURES": 120}))
    assert s["measured"] is True
    assert "BROWSE_FEATURES" not in s["absent"]
    assert "配られていません" not in trend.surface_line(_rows({**REAL_SOURCES, "BROWSE_FEATURES": 120,
                                                              "RELATED_VIDEO": 40}))


def test_実物の写しでは_ホームが0回だと名指しする():
    s = trend.surface_split(_rows())
    assert s["measured"] is True
    assert "BROWSE_FEATURES" in s["absent"]
    assert s["sources"]["RELATED_VIDEO"] == 1
    line = trend.surface_line(_rows())
    assert "BROWSE_FEATURES" in line
    assert "配られていません" in line
    # **ショートの面が主で在ることも、同じ行に出ること**（どちらか片方だけ読ませない）
    assert "SHORTS" in line


def test_測っていない台帳は_0回と同じ字にならない():
    line = trend.surface_line([{"event": "measured", "id": "a"}])
    assert "測っていません" in line and "0回" in line and "ではありません" in line
    assert "配られていません" not in line


def test_古すぎる引きは_0を0と読ませない():
    old = (dt.date.today() - dt.timedelta(days=20)).isoformat()
    line = trend.surface_line(_rows(day=old))
    assert "古すぎて" in line
    assert "配られていません" not in line


def test_扉の3行が隣り合って出る():
    """**`lines()` の中で、3つ の `append` のあいだに別の `append` が挟まらないこと。**

    実物の台帳を通さずに **並びそのもの**を見ます —— `lines()` は台帳の形に
    ほとんど全部 依存するので、作り物の行で呼ぶと並び以外の理由で落ち、
    **「並びが壊れた」と同じ字になります**（この検査が押さえたい当のもの）。
    """
    import inspect
    import re as _re
    src = inspect.getsource(trend.lines)
    calls = _re.findall(r"out\.append\(\s*(?:_gp\.)?([a-zA-Z_]+)\(", src)
    i = calls.index("gate_measured_line")
    assert calls[i + 1] == "gate_proof_line", f"扉の 2行目 が離れています: {calls[i:i + 3]}"
    assert calls[i + 2] == "surface_line", f"扉の 3行目 が離れています: {calls[i:i + 3]}"


def test_公開ページの行が_登録の目盛りから落ちない():
    """**日枠が尽きた周に倒した先の行を、読む側の絞りが捨てないこと。**

    `pubcheck.channel_public` は登録しか持たないので `views` の欄を書きません
    （`None` を 0 と読ませないため）。`_channel_rows` は `views` を要求するので、
    **口を開けた手が読む側で無効になる**形を、ここで押さえます。
    """
    rows = [
        {"event": "channel", "id": "UCa", "subs": 35, "views": 91000,
         "at": "2026-09-18T17:30:07+09:00"},
        # 日枠が尽きた周（公開ページ・**`views` の欄が無い**）
        {"event": "channel", "id": "UCa", "subs": 39, "src": "public_page",
         "at": "2026-09-19T03:37:59+09:00"},
    ]
    assert len(trend._channel_rows(rows)) == 1          # `views` を見る側は 1行 のまま
    assert len(trend._channel_rows_subs(rows)) == 2     # 登録だけ見る側は 2行 とも読む
    assert [r["subs"] for r in trend._channel_rows_subs(rows)] == [35, 39]


def test_改名の窓が_公開ページの行で伸びる():
    base = [
        {"event": "channel_renamed", "id": "-", "at": "2026-09-18T20:31:53+09:00",
         "bound_from": "2026-09-18T17:30:07+09:00", "bound_to": "2026-09-18T20:31:53+09:00"},
        {"event": "channel", "id": "UCa", "subs": 34, "views": 90900,
         "at": "2026-09-18T11:14:23+09:00"},
        {"event": "channel", "id": "UCa", "subs": 35, "views": 91000,
         "at": "2026-09-18T17:30:07+09:00"},
        {"event": "channel", "id": "UCa", "subs": 37, "views": 91200,
         "at": "2026-09-18T20:31:53+09:00"},
    ]
    now = dt.datetime.fromisoformat("2026-09-19T03:40:00+09:00")
    short = trend.rename_effect(base, now=now)
    longer = trend.rename_effect(
        base + [{"event": "channel", "id": "UCa", "subs": 39, "src": "public_page",
                 "at": "2026-09-19T03:37:59+09:00"}], now=now)
    assert short["marked"] and longer["marked"]
    # **公開ページの行が入ると、後ろの窓が伸びること**（門は 72時間）
    assert longer["after_h"] > short["after_h"]
    assert longer["subs_after"] > short["subs_after"]


def test_長尺の面の一覧にショートのフィードが入っていない():
    # 扉(b)（4,000時間）へ入るのは長尺の視聴だけ ＝ SHORTS を入れたら判定が壊れる
    assert "SHORTS" not in trend.LONG_SURFACES
    assert set(trend.SURFACE_ABSENT_WATCH) <= set(trend.LONG_SURFACES)
