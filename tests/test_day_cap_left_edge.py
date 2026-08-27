"""**窓の左端**と、「本数が合っても中身が入れ替わっている日」の守り。

2026-08-27 の実測から起こした検査です。この日は `day_cap` の (A)/(B) を
切り分けるために **05:00〜08:30 JST に 8本**を足した日で、結果は:

    05:00 0  05:30 0  06:00 0  06:30 0  07:00 0  07:30 4  08:00 0  08:30 0
    08:59 313  09:30 106  10:00 84  10:30 367 …… 13:30 71     （16:00 は 0）

**8本とも `public`/`processed`**（`videos.list` で確認済み・投稿の失敗ではない）。

つまり **生きた本数は 10本** で、これは (A) 本数モデルの予測 10本 と**一致します**。
ところが**生きた本が入れ替わっています** —— (A) は「先頭10本」＝ 05:00〜09:30 が
生きると言い、実際に生きたのは 08:59〜13:30 の 10本です。**19本中 16本が逆。**

`window()` は長らく**生きた本数だけ**を2つの予測と比べていたので、
この日から `verdict='count'` を**距離0で断定**しました。**その日の実物が
選んだモデルを丸ごと否定しているのに**です。
"""
import datetime as dt
import json

from src import day_cap

JST = dt.timezone(dt.timedelta(hours=9))


def _log(tmp_path, rows):
    """(公開時刻JST, id, 再生) を `views.jsonl` の形にする（齢は6時間で揃える）。"""
    p = tmp_path / "views.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for when, vid, views in rows:
            pub = dt.datetime.fromisoformat(when).replace(tzinfo=JST)
            at = pub + dt.timedelta(hours=6)
            f.write(json.dumps({
                "id": vid,
                "at": at.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                "hours": 6.0, "views": views}) + "\n")
    return p


def _real_0827():
    """2026-08-27 の実物（19本）。"""
    return [("05:00", 0), ("05:30", 0), ("06:00", 0), ("06:30", 0), ("07:00", 0),
            ("07:30", 4), ("08:00", 0), ("08:30", 0), ("08:59", 313), ("09:30", 106),
            ("10:00", 84), ("10:30", 367), ("11:00", 115), ("11:30", 76),
            ("12:00", 157), ("12:30", 61), ("13:00", 203), ("13:30", 71), ("16:00", 0)]


def _baseline_days():
    """08:59 から30分きざみで 25本・生きるのは先頭10本、という普通の日を2つ。"""
    rows = []
    for d in (20, 21):
        for i in range(25):
            rows.append((f"2026-08-{d}T{9 + i // 2:02d}:{(i % 2) * 30:02d}",
                         f"v{d}_{i}", 800 if i < 10 else 0))
    return rows


def test_本数が合っていても中身が入れ替わっていたら決めない(tmp_path):
    """**この検査がこの回の本体です。**

    生きた本数 10 は本数モデルの予測 10 とぴったり一致します。
    **それでも `count` と断定しないこと** —— 本数モデルが「生きる」と
    名指しした 8本は全部 0再生、「死ぬ」と名指しした 8本は全部生きています。
    """
    rows = _baseline_days()
    rows += [(f"2026-08-27T{t}", f"w{t}", n) for t, n in _real_0827()]
    w = day_cap.window(_log(tmp_path, rows))

    assert w["verdict"] != "count", (
        "生きた本が 19本中 16本 入れ替わっている日から `count` を断定しています。"
        "**本数ではなく、どの本が生きたかで比べること。**")
    assert w["confounded"] is True, "どちらのモデルも合っていない日で切り分け済みにしないこと"
    assert any("2026-08-27" in m for m in w["misfit"]), (
        "説明できなかった日は `misfit` に残すこと（黙って捨てると、"
        "次の回が同じ日をもう一度作ります）")


def test_窓の左端を実測から出す(tmp_path):
    """05:00〜08:30 の 8本が0再生 ＝ **左端は 08:30 より後・08:59 まで**。"""
    rows = _baseline_days()
    rows += [(f"2026-08-27T{t}", f"w{t}", n) for t, n in _real_0827()]
    edge = day_cap.left_edge(_log(tmp_path, rows))

    assert edge is not None, "早い時刻で死んだ本があるのに、左端を測っていません"
    assert edge["after"] == "08:30"
    assert edge["by"] == "08:59"
    assert edge["from"] == "2026-08-27"
    assert edge["from_dead"] == 8


def test_左端より前から枠を数えない(tmp_path):
    """`cap_if_window()` の (B) は **10枠**。18枠（×1.80）は実在しません。

    ここは「切り分けの日に**予約してある**いちばん早い時刻」から数えていて、
    08/27 はそれが 05:00 なので 05:00〜13:30 ＝ 18枠 を返していました。
    **その 05:00 は、同じ日に置いて死ぬのを測った時刻です。**
    """
    rows = _baseline_days()
    rows += [(f"2026-08-27T{t}", f"w{t}", n) for t, n in _real_0827()]
    p = _log(tmp_path, rows)
    edge = day_cap.left_edge(p)
    end = dt.time(13, 30)
    by = dt.datetime.strptime(edge["by"], "%H:%M").time()
    span = (end.hour * 60 + end.minute) - (by.hour * 60 + by.minute)
    枠 = int(span // int(day_cap.MIN_GAP_MIN)) + 1

    assert 枠 == 10, (f"左端 {edge['by']} から {end:%H:%M} までは {枠}枠。"
                      "(A) の 10本 と同じで、(B) の側にも引き代はありません")


def test_ほとんど生きなかった日から決めない(tmp_path):
    """2026-08-04 の形（登録者9人・夕方から7本・生きたのは1本）。

    窓モデルは 13:30 までが1本も無いので「**1本も生きない**」と予測します。
    **何も生きないと言うモデルは、ほとんど何も生きなかった日で必ず勝ちます。**
    """
    rows = _baseline_days()
    rows += [(f"2026-08-04T{18 + i // 2:02d}:{(i % 2) * 30:02d}",
              f"x{i}", 300 if i == 0 else 0) for i in range(7)]
    w = day_cap.window(_log(tmp_path, rows))

    assert w["decided_by"] is None or "2026-08-04" not in w["decided_by"], (
        "上限が効いていない日（生きたのが1本）から切り分けています。"
        "**2026-08-24 に『コインの裏表で断定』として直した所です。**")


def test_窓が本当に真なら今までどおり切り分く(tmp_path):
    """**守りを足しただけで、答えが出る日まで殺していないこと。**

    05:00 から25本・13:30 までの18本が生きた ＝ 窓のほうが真、という世界。
    """
    rows = _baseline_days()
    rows += [(f"2026-08-27T{5 + i // 2:02d}:{(i % 2) * 30:02d}",
              f"w{i}", 800 if i < 18 else 0) for i in range(25)]
    w = day_cap.window(_log(tmp_path, rows))

    assert w["confounded"] is False
    assert w["verdict"] == "window"
