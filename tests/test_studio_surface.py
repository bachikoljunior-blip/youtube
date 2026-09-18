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
    assert calls[i + 3] == "surface_detail_line", (
        f"面の内訳の行（4行目）が離れています: {calls[i:i + 4]}")


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


def test_公開ページの行は_口が開いた印にならない():
    """**公開ページの `channel` 行で、停止の確認（`stall.mouth_gap`）を黙らせないこと。**

    あの行が言うのは「ページが読めた」だけで、**口（Data API）が開いたことは言いません。**
    混ぜると、口が閉じている周に `channel` 行が出続け、(A) は永久に鳴りません
    （オーナー `6df66dd7` の「停止を確認」そのものが黙ります）。
    """
    from studio import stall

    now = dt.datetime.fromisoformat("2026-09-19T05:00:00+09:00")
    api_row = {"event": "channel", "id": "UCa", "subs": 39, "views": 91336,
               "at": "2026-09-19T02:08:52+09:00"}
    pub_row = {"event": "channel", "id": "UCa", "subs": 39, "src": "public_page",
               "at": "2026-09-19T04:59:00+09:00"}

    def gap(rows):
        got = [s for s in stall.signs(rows=rows, rounds=[], now=now)
               if s.get("code") == "mouth_gap"]
        return got[0] if got else None

    # API の行だけ ＝ 2.9時間 空いている ＝ 鳴る
    a = gap([api_row])
    assert a is not None
    # 公開ページの行を足しても、**鳴り続けること**（1分 前の行で黙らない）
    b = gap([api_row, pub_row])
    assert b is not None, "公開ページの行が、口が開いた印として数えられています"


def test_長尺の面の一覧にショートのフィードが入っていない():
    # 扉(b)（4,000時間）へ入るのは長尺の視聴だけ ＝ SHORTS を入れたら判定が壊れる
    assert "SHORTS" not in trend.LONG_SURFACES
    assert set(trend.SURFACE_ABSENT_WATCH) <= set(trend.LONG_SURFACES)


# ---------------------------------------------------------------------------
# **面の内訳**（2026-09-19 04:5x に足した口・`trend.surface_detail`）
# ---------------------------------------------------------------------------

def _detail_rows(details, day="2026-09-16", extra=None):
    rows = [{"event": "analytics_traffic_detail", "id": day, "start": "2026-08-29",
             "details": details}]
    return (extra or []) + rows


def test_内訳が無い台帳は_測っていないと言う_0回とは言わない():
    """**この repo が 7度 踏んだ形** ＝ 行が無いことを「0回」と読ませない。"""
    d = trend.surface_detail([{"event": "channel", "id": "UCa"}])
    assert d["measured"] is False
    assert "0回" not in d["why"]


def test_関連の相手が_うちとよそに分かれる():
    """関連に並んでいるのが**うちの本**か**よそ**かは、同じ数の中で分かれていること。

    ＝ 「2本目 へ渡る道が在るか」を読む唯一の数（`related_ours`）。
    """
    rows = _detail_rows(
        {"RELATED_VIDEO": [{"detail": "AAAAAAAAAAA", "views": 5, "minutes": 3},
                           {"detail": "BBBBBBBBBBB", "views": 2, "minutes": 1}]},
        extra=[{"event": "scheduled", "id": "x", "video_id": "AAAAAAAAAAA"}])
    d = trend.surface_detail(rows)
    assert d["related_ours"] == 5
    assert d["related_others"] == 2


def test_ホームの再生は_登録者の面から数える():
    """`what-to-watch` ＝ ホーム。**`BROWSE_FEATURES` 0回 を「ホームに出ていない」と読ませない。**"""
    rows = _detail_rows({"SUBSCRIBER": [{"detail": "what-to-watch", "views": 140, "minutes": 26},
                                        {"detail": "/my_subscriptions", "views": 3, "minutes": 0}]})
    d = trend.surface_detail(rows)
    assert d["home_views"] == 140
    line = trend.surface_detail_line(rows)
    assert "ホーム" in line and "登録者" in line


def test_検索の語は_1回あたりの秒も返す():
    """語ごとの `sec_per_view` ＝ **どの語が長く見られているか**（扉(b) の通貨に近い側）。

    **再生 0回 の行で割らないこと**（`None` を返す）。
    """
    rows = _detail_rows({"YT_SEARCH": [{"detail": "加給年金", "views": 3, "minutes": 3},
                                       {"detail": "からの語", "views": 0, "minutes": 0}]})
    d = trend.surface_detail(rows)
    assert d["search_top"][0]["sec_per_view"] == 60.0
    assert d["search_top"][1]["sec_per_view"] is None


def test_内訳の口は_上位25件で頭打ちだと言っている():
    """**`maxResults` は 25 が上限**（26 以上は 500 で落ちる・撃って踏んだ）。

    この数が定数から消えたら、読む側は「この語では来ていない」と**尾を 0 と読み**ます。
    """
    from studio import analytics
    assert analytics.DETAIL_MAX == 25
    assert "SHORTS" not in analytics.DETAIL_SOURCES      # 400 を返す面（うちの再生の 96%）
    assert "BROWSE_FEATURES" not in analytics.DETAIL_SOURCES
    assert "上位" in trend.surface_detail_line(_detail_rows({"YT_SEARCH": []}))
