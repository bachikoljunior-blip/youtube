"""`trend.views_at_age` / `script_features` / `feature_cohorts` / `feature_line`
—— **§3 の 7-b（板 `board`）／7-c（札「しくみ」）の「N本 の 48h」を数える口**。

2026-09-12 22:2x JST・optimizer・Opus。**族の 7例目・8例目**
（`late_run` 04:3x／`blind_run` 16:0x／`reporting_empty_run` 18:4x／`outside_runs` 20:0x／
`views_streak` 20:3x／`rev7_run` 21:2x と同じ ——「N本 続いたら」と覆る条件に書きながら、
**N を数える物が無い**）。§16 の覆る条件 (1) は「次の1本で 3本 そろう」と書いており、
**そろったかを数える手が、書いた回の頭の中にしかありませんでした。**

**この口の値打ちは「挟み」の側に在ります** —— 実物 7本 のうち 齢 48.0h ちょうどの点を持つ本は
**0本** で、点を 1つ 選ぶ形にすると 3本目 は **536 と 613 のどちらにもできます**（1.14倍）。
＝ 中位も挟みのまま比べ、**重なったら「分けられない」**を返します（言い切らない）。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**）。この回に動かして確かめた
（`.pyc` を毎回 消してから ＝ 11つ目）:
  * 挟みを畳んで `lo` だけで比べる（`views_at_age` の `hi` を `lo` にする）
      → **3件**（`test_48hちょうどの点が無い本は挟みで返る`・`test_48hに着いていない本は数えない`・
        `test_挟みが重なったら分けられない` ＝ **挟みを畳むと「下回りました」と言い切ります**）
  * `reached` を「h 以下の点が在るか」にする（＝ まだ 48h に着いていない本を数える）
      → **2件**（`test_48hに着いていない本は数えない`・`test_48hに着く前の本は連に数えない`）。
      **1度目の対照は 1件 しか落ちませんでした** —— 検査のデータに
      「**点は在るが 48h に着いていない型の本**」が 1本も無く（未公開の本は点そのものが無い）、
      **緑だったのは道具ではなく検査のデータ**でした（§5 教訓の形 3つ目・4つ目）。
      その形（`test_48hに着く前の本は連に数えない`）を足してから落ちました。
  * 比べる相手を「全部の本」にする（直近 3本 に切らない）
      → **1件**（`test_比べる相手は持たない直近3本`）
  * 2つ の型を 1つ にまとめる（`FEATURES` から しくみ を外す）
      → **3件**（`test_台本から型を引く`・`test_型ごとに別の連`・`test_行に門と残りが出る`）
  * `trend` の並びから外す → **1件**（`test_trendの並びに出る`）
**ファイル単独でも撃ちました**（§5 教訓の形 11つ目）。

**きょうの状態を不変条件として書いていません**（§5 教訓の形 6つ目）——
齢も本数も検査の中で作っています（実物の台帳は 1度も読みません）。
"""
import json

from studio import trend


def _series(pairs: list[tuple[float, int]]) -> list[dict]:
    return [{"age_h": a, "views": v} for a, v in pairs]


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


def _script(tmp_path, sid: str, *, board: bool = False, shikumi: bool = False):
    segs = [{"say": "あ", "show": "あ", "sub": "", "tag": "決まり", "board": []},
            {"say": "い", "show": "い", "sub": "", "tag": "計算", "board": []}]
    if board:
        segs[0]["board"] = ["たとえば"]
    if shikumi:
        segs[1]["tag"] = "しくみ"
    (tmp_path / f"{sid}.json").write_text(
        json.dumps({"id": sid, "segments": segs}, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- views_at_age

def test_48hちょうどの点が無い本は挟みで返る():
    pts = _series([(47.6, 536), (48.3, 613), (60.0, 700)])
    got = trend.views_at_age(pts, trend.envelope(pts))
    assert got["reached"] is True
    assert (got["lo"], got["hi"]) == (536, 613)
    assert got["exact"] is False


def test_48hちょうどの点が在れば挟みは閉じる():
    pts = _series([(47.0, 500), (48.0, 600), (49.0, 600)])
    got = trend.views_at_age(pts, trend.envelope(pts))
    assert (got["lo"], got["hi"]) == (600, 600)
    assert got["exact"] is True


def test_48hに着いていない本は数えない():
    pts = _series([(10.0, 100), (20.0, 200)])
    got = trend.views_at_age(pts, trend.envelope(pts))
    assert got["reached"] is False
    # **下端は在ります**（読める数が無いのではなく、比べられないだけ）。
    assert got["lo"] == 200 and got["hi"] is None


# ------------------------------------------------------------- script_features

def test_台本から型を引く(tmp_path):
    _script(tmp_path, "2026-09-11-a", board=True)
    _script(tmp_path, "2026-09-12-b", board=True, shikumi=True)
    _script(tmp_path, "2026-09-10-c")
    got = trend.script_features(tmp_path)
    assert got["2026-09-10-c"] == {"板": False, "しくみ": False}
    assert got["2026-09-11-a"] == {"板": True, "しくみ": False}
    assert got["2026-09-12-b"] == {"板": True, "しくみ": True}


def test_壊れた台本は落とす(tmp_path):
    _script(tmp_path, "2026-09-10-c")
    (tmp_path / "こわれ.json").write_text("{", encoding="utf-8")
    assert set(trend.script_features(tmp_path)) == {"2026-09-10-c"}


# ----------------------------------------------------------- feature_cohorts

def _three_plain(tmp_path):
    """型を持たない 48h 済みの 3本（比べる相手）。"""
    for sid, vid, v in (("2026-09-07-x", "VX", 100), ("2026-09-08-y", "VY", 200),
                        ("2026-09-09-z", "VZ", 300)):
        _script(tmp_path, sid)
        yield sid, vid, [(47.0, v), (49.0, v)]


def test_門に届くまではまだ(tmp_path):
    books = list(_three_plain(tmp_path))
    _script(tmp_path, "2026-09-10-b1", board=True)
    books.append(("2026-09-10-b1", "VB1", [(47.0, 900), (49.0, 900)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["n"] == 1 and got["板"]["n_ready"] == 1
    assert got["板"]["short"] == 2
    assert got["板"]["verdict"] == "まだ"


def test_48hに着く前の本は連に数えない(tmp_path):
    """**3本 そろっていても、48h に着いていなければ門は引けません**（実物 09/11・09/12 がその形）。"""
    books = list(_three_plain(tmp_path))
    for i, (age, v) in enumerate(((49.0, 10), (49.0, 20), (30.0, 900))):
        sid = f"2026-09-1{i}-b"
        _script(tmp_path, sid, board=True)
        books.append((sid, f"VB{i}", [(20.0, v), (age, v)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["n"] == 3 and got["板"]["n_ready"] == 2
    assert got["板"]["short"] == 1
    assert got["板"]["verdict"] == "まだ"


def test_未公開の台本はまだ(tmp_path):
    books = list(_three_plain(tmp_path))
    _script(tmp_path, "2026-09-10-b1", board=True)
    # **台帳に `scheduled` が無い ＝ まだ上げていない本**（1本 として数えるが、48h は持たない）。
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["n"] == 1 and got["板"]["n_ready"] == 0
    assert got["板"]["books"][0]["published"] is False


def test_比べる相手は持たない直近3本(tmp_path):
    books = list(_three_plain(tmp_path))
    _script(tmp_path, "2026-09-06-w")
    books.insert(0, ("2026-09-06-w", "VW", [(47.0, 999), (49.0, 999)]))
    _script(tmp_path, "2026-09-10-b1", board=True)
    books.append(("2026-09-10-b1", "VB1", [(47.0, 900), (49.0, 900)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert [b["sid"] for b in got["板"]["base"]] == \
        ["2026-09-07-x", "2026-09-08-y", "2026-09-09-z"]


def test_中位が下回ったら名指しする(tmp_path):
    books = list(_three_plain(tmp_path))          # 100 / 200 / 300 → 中位 200
    for i, v in enumerate((10, 20, 30)):
        sid = f"2026-09-1{i}-b"
        _script(tmp_path, sid, board=True)
        books.append((sid, f"VB{i}", [(47.0, v), (49.0, v)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["verdict"] == "下回りました"
    assert got["板"]["mid"]["lo"] == 20 and got["板"]["base_mid"]["lo"] == 200


def test_中位が上回ったら下回りません(tmp_path):
    books = list(_three_plain(tmp_path))
    for i, v in enumerate((1000, 2000, 3000)):
        sid = f"2026-09-1{i}-b"
        _script(tmp_path, sid, board=True)
        books.append((sid, f"VB{i}", [(47.0, v), (49.0, v)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["verdict"] == "下回りません"


def test_挟みが重なったら分けられない(tmp_path):
    """**この検査がこの口の値打ちそのもの** —— 点を 1つ 選ぶ形なら、ここで判定が出てしまう。"""
    books = list(_three_plain(tmp_path))          # 中位 200（挟みは閉じている）
    for i in range(3):
        sid = f"2026-09-1{i}-b"
        _script(tmp_path, sid, board=True)
        # 47.0h で 50回・49.0h で 400回 ＝ 48h は **50〜400** で、相手の 200 を跨ぐ。
        books.append((sid, f"VB{i}", [(47.0, 50), (49.0, 400)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["verdict"] == "分けられない"


def test_0回の本も1本として数える(tmp_path):
    books = list(_three_plain(tmp_path))
    for i, v in enumerate((0, 10, 20)):
        sid = f"2026-09-1{i}-b"
        _script(tmp_path, sid, board=True)
        books.append((sid, f"VB{i}", [(47.0, v), (49.0, v)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["n_ready"] == 3
    assert got["板"]["mid"]["lo"] == 10          # 0 / 10 / 20 の中位


def test_型ごとに別の連(tmp_path):
    books = list(_three_plain(tmp_path))
    _script(tmp_path, "2026-09-10-b", board=True)
    books.append(("2026-09-10-b", "VB", [(47.0, 500), (49.0, 500)]))
    _script(tmp_path, "2026-09-11-s", board=True, shikumi=True)
    books.append(("2026-09-11-s", "VS", [(47.0, 500), (49.0, 500)]))
    got = {c["name"]: c for c in trend.feature_cohorts(_rows(books), tmp_path)}
    assert got["板"]["n"] == 2
    assert got["しくみ"]["n"] == 1


# ------------------------------------------------------------------ 印字

def test_行に門と残りが出る(tmp_path):
    books = list(_three_plain(tmp_path))
    _script(tmp_path, "2026-09-10-b1", board=True)
    books.append(("2026-09-10-b1", "VB1", [(47.0, 900), (49.0, 900)]))
    line = trend.feature_line(_rows(books), tmp_path)
    assert "§3 7-b" in line and "§3 7-c" in line
    assert "まだ引けません" in line
    assert "挟み" in line


def test_trendの並びに出る():
    """**印字して捨てない**（§6 `cli.py` の「毎周 印字する数は `ledger()` を通すこと」と同じ向き）。"""
    src = (trend.__file__)
    body = open(src, encoding="utf-8").read()
    assert "out.append(feature_line(rows))" in body
