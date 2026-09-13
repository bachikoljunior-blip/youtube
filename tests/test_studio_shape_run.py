"""`trend.studio_books` / `shape_run` / `shape_line`
—— **§7 末尾の「形」の「7本 の 48h の中央値」を数える口**。

2026-09-13 10:1x JST・optimizer・Opus。**族の 9例目**
（`late_run` 04:3x／`blind_run` 16:0x／`reporting_empty_run` 18:4x／`outside_runs` 20:0x／
`views_streak` 20:3x／`rev7_run` 21:2x／`feature_cohorts` 22:2x と同じ ——
「N本 で判定する」と覆る条件に書きながら、**N を数える物が無い**）。

**この回に、手で運んだ数が実際に古くなっていました**: §7「形」の行は 09/12 10:1x（`hourly`）に
「**いま 5/7 本・中央値 140回 ＝ 旧作りの帯 60〜191回 の中へ戻りました**」と書かれ、
**24時間 後（6本目 の 48h ＝ 09/13 10:00 JST）に 6/7 本・中央値 338〜377回 ＝ 帯の上 へ反転**しました。
同じ行の 決め (5) が「**1本で判定が反転する**」と書いていた当のものが、
**書いた側の数のほうで起きた**形です。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**）。この回に動かして確かめた
（`.pyc` を毎回 消してから ＝ 11つ目）:
  * 挟みを畳んで `lo` だけで比べる（`_median_bracket` の `hi` を `lo` にする）
      → **2件**（`test_中位は挟みのまま返る`・`test_挟みが帯と重なったら分けられない`）
  * 門（7本）を待たずに verdict を出す（`len(ready) >= SHAPE_GATE` を外す）
      → **2件**（`test_門に届くまではまだ`・`test_門に届くまでも中位は出す`）
  * 0回 の本を落とす（`ready` から `hi == 0` を外す）
      → **1件**（`test_0回の本も1本として数える`）
  * (1-a) の並びを「全部の本」に広げる（`SHAPE_N1_RANGE` を無視）
      → **1件**（`test_1aは5から7本目だけ数える`）
  * `trend` の並びから外す → **1件**（`test_trendの並びに出る`）
**ファイル単独でも撃ちました**（§5 教訓の形 11つ目）。

**きょうの状態を不変条件として書いていません**（§5 教訓の形 6つ目）——
本数も齢も検査の中で作っています（実物の台帳は 1度も読みません）。
"""
import json

from studio import trend


def _rows(books: list[tuple[str, str, list[tuple[float, int]]]]) -> list[dict]:
    """(台本の id, video_id, [(齢, 再生)]) から台帳の行を作る。"""
    out: list[dict] = []
    for sid, vid, pts in books:
        out.append({"event": "scheduled", "id": sid, "video_id": vid,
                    "at": "2026-09-01T10:00:00+09:00"})
        for i, (age, views) in enumerate(pts):
            out.append({"event": "measured", "id": vid, "age_h": age, "views": views,
                        "at": f"2026-09-0{1 + i % 9}T{10 + i % 12:02d}:00:00+09:00"})
    return out


def _script(tmp_path, sid: str):
    (tmp_path / f"{sid}.json").write_text(
        json.dumps({"id": sid, "segments": [{"say": "あ", "show": "あ", "sub": ""}]},
                   ensure_ascii=False), encoding="utf-8")


def _n_books(tmp_path, views: list[int], *, reached: bool = True, start: int = 1):
    """`views` のぶんだけ本を作る（`reached` が偽なら 48h に着いていない本）。

    `start` は **何本目から**（同じ tmp_path に足すときに id をぶつけないため）。
    """
    books = []
    for i, v in enumerate(views, start=start):
        sid = f"2026-09-{5 + i:02d}-b{i}"
        _script(tmp_path, sid)
        pts = [(47.0, v), (49.0, v)] if reached else [(20.0, v)]
        books.append((sid, f"V{i}", pts))
    return books


# ------------------------------------------------------------- studio_books

def test_何本目かが付く(tmp_path):
    books = _n_books(tmp_path, [10, 20, 30])
    got = trend.studio_books(_rows(books), tmp_path)
    assert [b["idx"] for b in got] == [1, 2, 3]
    assert [b["sid"][:10] for b in got] == ["2026-09-06", "2026-09-07", "2026-09-08"]


def test_未公開の台本も1本として並ぶ(tmp_path):
    books = _n_books(tmp_path, [10])
    _script(tmp_path, "2026-09-20-mada")       # 台帳に `scheduled` が無い
    got = trend.studio_books(_rows(books), tmp_path)
    assert len(got) == 2
    assert got[1]["published"] is False
    assert got[1]["at48"]["reached"] is False


# ---------------------------------------------------------------- shape_run

def test_門に届くまではまだ(tmp_path):
    got = trend.shape_run(_rows(_n_books(tmp_path, [1000] * 6)), tmp_path)
    assert got["n_ready"] == 6 and got["short"] == 1
    assert got["verdict"] == "まだ"


def test_門に届くまでも中位は出す(tmp_path):
    """**手で運ばせない**のがこの口の値打ち —— 途中でも中位は毎周 出ます。"""
    got = trend.shape_run(_rows(_n_books(tmp_path, [0, 66, 140, 600, 943, 970])), tmp_path)
    assert got["verdict"] == "まだ"
    assert (got["mid"]["lo"], got["mid"]["hi"]) == (370, 370)   # 140 と 600 の中位


def test_門に届いて帯の上(tmp_path):
    got = trend.shape_run(_rows(_n_books(tmp_path, [0, 66, 140, 600, 943, 970, 800])), tmp_path)
    assert got["n_ready"] == 7
    assert got["verdict"] == "帯の上"


def test_門に届いて帯の中(tmp_path):
    got = trend.shape_run(_rows(_n_books(tmp_path, [60, 70, 80, 100, 120, 150, 190])), tmp_path)
    assert got["verdict"] == "帯の中"


def test_門に届いて帯の下(tmp_path):
    got = trend.shape_run(_rows(_n_books(tmp_path, [0, 1, 2, 3, 4, 5, 6])), tmp_path)
    assert got["verdict"] == "帯の下"


def test_中位は挟みのまま返る(tmp_path):
    """齢 48.0h ちょうどの点は実物 0本 ＝ **中位も挟みのまま**（点を選ぶと判定が動く）。"""
    books = []
    for i in range(7):
        sid = f"2026-09-{6 + i:02d}-b{i}"
        _script(tmp_path, sid)
        books.append((sid, f"V{i}", [(47.0, 100), (49.0, 900)]))
    got = trend.shape_run(_rows(books), tmp_path)
    assert (got["mid"]["lo"], got["mid"]["hi"]) == (100, 900)


def test_挟みが帯と重なったら分けられない(tmp_path):
    """**この検査がこの口の値打ちそのもの** —— 挟みを畳めば、ここで判定が出てしまう。"""
    books = []
    for i in range(7):
        sid = f"2026-09-{6 + i:02d}-b{i}"
        _script(tmp_path, sid)
        # 48h は 100〜900 ＝ 旧作りの帯 60〜191回 を跨ぐ。
        books.append((sid, f"V{i}", [(47.0, 100), (49.0, 900)]))
    got = trend.shape_run(_rows(books), tmp_path)
    assert got["verdict"] == "分けられない"


def test_0回の本も1本として数える(tmp_path):
    """§7「形」の 決め (5) —— 外す口が道具に無いのに外すと、読む側が都合で選べます。"""
    got = trend.shape_run(_rows(_n_books(tmp_path, [0, 10, 20, 30, 40, 50, 60])), tmp_path)
    assert got["n_ready"] == 7
    assert got["mid"]["lo"] == 30           # 0 を入れた 7本 の中位


def test_48hに着いていない本は中位に入れない(tmp_path):
    books = _n_books(tmp_path, [100, 200])
    books += _n_books(tmp_path, [9999], reached=False, start=3)
    got = trend.shape_run(_rows(books), tmp_path)
    assert got["n"] == 3 and got["n_ready"] == 2
    assert got["mid"]["lo"] == 150


# --------------------------------------------------------------- (1-a) の連

def test_1aは5から7本目だけ数える(tmp_path):
    """1〜4本目 が 437回 を下回っていても、(1-a) は 5〜7本目 だけを数えます。"""
    got = trend.shape_run(_rows(_n_books(tmp_path, [1, 2, 3, 4, 5, 1000, 1000])), tmp_path)
    assert [b["idx"] for b in got["n1_below"]] == [5]
    assert got["n1_gate"] == 2


def test_1aは挟みの上端で下回りを見る(tmp_path):
    """挟みが 437 を跨ぐ本は「下回った」に数えません（言い切らない側）。"""
    books = []
    for i, pts in enumerate(([(47.0, 400), (49.0, 500)], [(47.0, 10), (49.0, 20)],
                             [(47.0, 10), (49.0, 20)]), start=5):
        sid = f"2026-09-{6 + i:02d}-b{i}"
        _script(tmp_path, sid)
        books.append((sid, f"V{i}", pts))
    books = _n_books(tmp_path, [1, 2, 3, 4]) + books
    got = trend.shape_run(_rows(books), tmp_path)
    assert [b["idx"] for b in got["n1_below"]] == [6, 7]


def test_まだ着いていない5から7本目は待ちに入る(tmp_path):
    books = _n_books(tmp_path, [1, 2, 3, 4, 5])
    books += _n_books(tmp_path, [9999], reached=False, start=6)
    got = trend.shape_run(_rows(books), tmp_path)
    assert [b["idx"] for b in got["n1_wait"]] == [6]


# ------------------------------------------------------------------ 印字

def test_行に門と残りと1aが出る(tmp_path):
    line = trend.shape_line(_rows(_n_books(tmp_path, [100, 200, 300])), tmp_path)
    assert "門 7本" in line
    assert "まだ引けません" in line
    assert "(1-a)" in line and "門 2本" in line
    assert "挟み" in line
    assert "判定は" not in line or "hourly" in line


def test_行は門に届いたら判定の宛先を言う(tmp_path):
    line = trend.shape_line(
        _rows(_n_books(tmp_path, [0, 66, 140, 600, 943, 970, 800])), tmp_path)
    assert "門に届きました" in line
    assert "帯の上" in line
    assert "`hourly`" in line


def test_trendの並びに出る():
    """**印字して捨てない**（§6 `cli.py` の「毎周 印字する数は `ledger()` を通すこと」と同じ向き）。

    **`in body` では見張れません**（2026-09-13 10:2x に陽性対照で踏んだ）——
    `pass  # out.append(...)` と畳んでも、字は本文に残るので通ります。
    **行そのものが、註ではなく撃つ側に在ること**を見ます。
    """
    body = open(trend.__file__, encoding="utf-8").read()
    assert [l for l in body.splitlines() if l.strip() == "out.append(shape_line(rows))"], \
        "trend の並びに `shape_line` が無い（註の中の写しは数えない）"
