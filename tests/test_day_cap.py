"""`src/day_cap.py` —— **1日に何本まで再生が付くか**を、崩れた日から読む道具。

**先に固定するのは「この道具が正しければ、必ず当てるはずの1件」**です
（`docs/trigger_main.md` §4）。それは実測の 2026-08-20:

    25本 公開して、**#11から先の15本が 0〜3再生**。#10 は 1,111再生。

そして**外してはいけない1件**が、同じ実測の中にあります:

    08/16 の 14時 = #4 → 1,361再生 ／ 08/20 の 14時 = #12 → 0再生

**時刻では割れていない**ことが、この道具の存在理由です。

**そして 2026-08-24 に軸を測り直しました（通し番号 → 本数）。** 08/21 の32本は
:00/:30 の10本が生き、あいだの :15/:45 が死んでいます。番号で数えると「#17まで
生きた」＝ 17本 ですが、**再生が付いた本数は 10本**でした（08/20・08/22 も 10本）。
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from src import day_cap


def _log(tmp_path, rows):
    """rows: [(公開JST文字列, id, 再生)] → `data/views.jsonl` と同じ形の一時ファイル。"""
    p = tmp_path / "views.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for pub, vid, views in rows:
            t = dt.datetime.fromisoformat(pub).replace(tzinfo=day_cap.JST)
            at = (t + dt.timedelta(hours=12)).astimezone(dt.timezone.utc)
            fh.write(json.dumps({"at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "id": vid, "hours": 12.0, "views": views}) + "\n")
    return p


def test_崩れた日から上限を読む(tmp_path):
    """**既知の当たり**: 10本まで生きて11本目から死ぬ日を置けば、上限は 10。"""
    rows = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"v{i}",
             800 if i < 10 else 0) for i in range(25)]
    m = day_cap.measure(_log(tmp_path, rows))
    assert m["measured"] is True
    assert m["cap"] == 10
    assert m["collapse"] == 11


def test_同じ時刻でも通し番号で割れる(tmp_path):
    """**外してはいけない1件。** 14時の本が、#4 なら生き #12 なら死ぬ。

    時刻で切る道具なら「14時は死ぬ」と読み、**上限は 14時より前の本数**に
    化けます。ここが落ちたら、軸が通し番号から時刻へずれています。
    """
    early = [(f"2026-08-16T{8 + i:02d}:00", f"a{i}", 1300) for i in range(5)]   # #4 は 14時
    late = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"b{i}",
             800 if i < 10 else 0) for i in range(25)]                          # #12 は 14時
    m = day_cap.measure(_log(tmp_path, early + late))
    assert m["cap"] == 10, "14時そのものを死んだ時刻と読んでいます"
    assert m["floor"] == 10


def test_一本ごとの不発を上限と読まない(tmp_path):
    """**別の日に #10 が生きているなら、#3 から先が0の日は「上限3」ではありません。**

    これは実データで一度踏んでいます（2026-08-04 の7本で `cap=2` と出た）。
    上限だと言えるのは `floor` より後ろで崩れたときだけ。
    """
    good = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"g{i}", 900) for i in range(10)]
    flop = [("2026-08-04T09:00", "f0", 600), ("2026-08-04T10:00", "f1", 500),
            ("2026-08-04T11:00", "f2", 0), ("2026-08-04T12:00", "f3", 0)]
    m = day_cap.measure(_log(tmp_path, good + flop))
    assert m["measured"] is False, "1本ごとの不発を『上限』と読んでいます"
    assert m["floor"] == 10
    assert m["cap"] >= 10


def test_面に載っていない日は上限の証拠にしない(tmp_path):
    """その日の上位3本ごと 0〜数再生なら、上限ではなく**まだ誰にも届いていない**日。"""
    dead = [(f"2026-08-05T{9 + i:02d}:00", f"d{i}", 2 if i < 2 else 0) for i in range(6)]
    m = day_cap.measure(_log(tmp_path, dead))
    assert m["measured"] is False
    assert m["cap"] == day_cap.FALLBACK


def test_上限を超えたぶんは0として数える(tmp_path):
    rows = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"v{i}",
             800 if i < 10 else 0) for i in range(25)]
    p = _log(tmp_path, rows)
    assert day_cap.effective(25, p) == 10
    assert day_cap.effective(4, p) == 4


def test_実データで上限が10と出る():
    """**手元の `data/views.jsonl` そのもの。**（2026-08-21 時点で 10本）

    ここが動いたら、それは**壊れではなく測り直し**です。動いたことを
    `docs/JOURNAL.md` に書いて、この数を更新すること —— 上限が上がるのは
    「上限より多く出した日に、後ろの本が再生を取った」ときで、**それは前進です。**
    """
    m = day_cap.measure()
    if not m["measured"]:
        pytest.skip("崩れをまだ観測していない（読みが足りない）")
    assert 3 <= m["cap"] <= 92
    assert m["cap"] == m["floor"]


def test_挟まれて死んだ本を上限に数えない(tmp_path):
    """**2026-08-24 に測り直した1件。** 生きた本が :00/:30 に、死んだ本が :15/:45 に
    交互で並ぶ日（実測 08/21・32本）。**番号で数えると 17本、本数で数えると 10本。**

    公開の順番と YouTube が配信する順番は同じではないので、**軸は「その日に
    再生が付いた本数」**です。ここが落ちたら、番号の数え方へ戻っています。
    """
    rows = []
    for i in range(10):                                     # :00 と :30 → 生きる
        rows.append((f"2026-08-21T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"a{i}", 900))
    for i in range(7):                                      # :15 と :45 → 死ぬ
        rows.append((f"2026-08-21T{9 + i // 2:02d}:{15 + (i % 2) * 30:02d}", f"b{i}", 1))
    for i in range(15):                                     # 14時以降 → 死ぬ
        rows.append((f"2026-08-21T{14 + i // 2:02d}:{(i % 2) * 30:02d}", f"c{i}", 0))
    m = day_cap.measure(_log(tmp_path, rows))
    assert m["measured"] is True
    assert m["cap"] == 10, f"番号で数えています（cap={m['cap']}）"
    assert m["collapse"] == 11


# --- **「本数」と「時刻の窓」の切り分け**（2026-08-24 に足した） ----------------
#
# 上の検査は、**同じ生データが2通りに読める**ことを見ていませんでした。実測の
# 08/20〜08/22 は3日とも 09:00 JST から30分きざみで始めており、生きた本の最後が
# 13:30・そこから後は全滅です。**09:00 から30分きざみだと 13:30 がちょうど10本目**
# なので、「1日10本の予算」と「13:30 で閉じる窓」は**まったく同じ数を出します。**
#
# 断定して印字すると `eta.py` の `density` の腕がそこで頭打ちになるので、
# **切り分けられていないことを、道具のほうが言うこと。**


def test_09時から始めた日だけでは切り分けられない(tmp_path):
    """3日とも同じ始まりなら、2つのモデルは同じ数を出す ＝ `confounded`。"""
    rows = []
    for d in (20, 21, 22):
        for i in range(25):
            rows.append((f"2026-08-{d}T{9 + i // 2:02d}:{(i % 2) * 30:02d}",
                         f"v{d}_{i}", 800 if i < 10 else 0))
    p = _log(tmp_path, rows)
    w = day_cap.window(p)
    assert w["confounded"] is True
    assert w["verdict"] is None
    assert (w["C"], w["T"]) == (10, "13:30")
    assert "切り分けられていません" in "\n".join(day_cap.lines(p))


def test_早い日を1日置けば切り分く(tmp_path):
    """**05:00 から出した日**を足すと、2つの予測が割れて決まります。

    この検査が落ちるのは、切り分けの実験（2026-08-27 の 05〜08時）が
    実データに入って**別の答え**を出したときです。そのときは
    検査ではなく、`density` の腕の天井のほうを引き直すこと。
    """
    rows = []
    for d in (20, 21):
        for i in range(25):
            rows.append((f"2026-08-{d}T{9 + i // 2:02d}:{(i % 2) * 30:02d}",
                         f"v{d}_{i}", 800 if i < 10 else 0))
    # 05:00 から 30分きざみ 25本。**13:30 までの18本が生きた** ＝ 窓のほう
    for i in range(25):
        rows.append((f"2026-08-27T{5 + i // 2:02d}:{(i % 2) * 30:02d}",
                     f"w{i}", 800 if i < 18 else 0))
    p = _log(tmp_path, rows)
    w = day_cap.window(p)
    assert w["confounded"] is False
    assert w["verdict"] == "window"
    assert day_cap.measure(p)["cap"] == 18      # floor が上へ追う
    assert "時刻の窓のほうが上限" in "\n".join(day_cap.lines(p))


def test_早く出しても増えなければ本数のほうだと言う(tmp_path):
    """05:00 から出しても 10本しか生きなければ、**予算のほう**で決まる。"""
    rows = []
    for d in (20, 21):
        for i in range(25):
            rows.append((f"2026-08-{d}T{9 + i // 2:02d}:{(i % 2) * 30:02d}",
                         f"v{d}_{i}", 800 if i < 10 else 0))
    for i in range(25):
        rows.append((f"2026-08-27T{5 + i // 2:02d}:{(i % 2) * 30:02d}",
                     f"w{i}", 800 if i < 10 else 0))
    w = day_cap.window(_log(tmp_path, rows))
    assert w["confounded"] is False
    assert w["verdict"] == "count"


def test_どちらのモデルにも乗っていない日で決めない(tmp_path):
    """**2026-08-04 の実物**（18:29 から7本・生きた2本）で断定しないこと。

    本数なら4・窓なら0 で、実測の2は**両方から等距離**です。ここを通していた
    ので、この道具はコインの裏表で「窓のほうが上限」と印字していました。
    """
    rows = []
    for d in (20, 21, 22):
        for i in range(25):
            rows.append((f"2026-08-{d}T{9 + i // 2:02d}:{(i % 2) * 30:02d}",
                         f"v{d}_{i}", 800 if i < 10 else 0))
    for i in range(7):
        rows.append((f"2026-08-04T{18 + i // 2:02d}:{29 if i % 2 == 0 else 59}",
                     f"x{i}", 400 if i < 2 else 0))
    w = day_cap.window(_log(tmp_path, rows))
    assert w["confounded"] is True
    assert w["verdict"] is None


def test_間隔で死んだ本を窓のせいにしない(tmp_path):
    """**08/21 の :15/:45**（15分後に出した7本）は、上限ではなく間隔で死んでいる。"""
    times = ["08:59", "09:15", "09:30", "09:44", "10:00", "10:15", "10:30",
             "11:00", "11:14", "11:30", "11:45", "11:59", "12:14", "12:30",
             "12:45", "13:00", "13:30"]
    alive = {"08:59", "09:30", "10:00", "10:30", "11:00", "11:30", "11:59",
             "12:30", "13:00", "13:30"}
    rows = [(f"2026-08-21T{t}", f"v{i}", 800 if t in alive else 0)
            for i, t in enumerate(times)]
    rows += [(f"2026-08-21T{14 + i // 2:02d}:{(i % 2) * 30:02d}", f"z{i}", 0)
             for i in range(15)]
    p = _log(tmp_path, rows)
    # 間隔で落としたあと 13:30 までに残るのは10本 ＝ 本数のモデルと同じ数
    kept = day_cap._spaced([dt.datetime.fromisoformat(f"2026-08-21T{t}")
                            .replace(tzinfo=day_cap.JST) for t in times])
    assert len(kept) == 10
    assert day_cap.window(p)["confounded"] is True
