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


# ---------------------------------------------------------------------------
# **同じ分の組（衝突）を、上限の証拠に使わない**（2026-08-25 に足した）
#
# 08/27 は「1日10本の上限」と「13:30 JST で閉じる窓」を切り分けるために組んだ日
# です。その日に**5組10本が同じ分**にいました（`src/collisions.py`）。
# 同分の2本がどう死ぬかは**一度も測っていない**ので、そこで死んだ本を
# 「上限で死んだ」と数えると、答えが**逆に出ます。**
# ---------------------------------------------------------------------------

def _day(date, times, alive, *, prefix="v"):
    """(公開JST, id, 再生) を組み立てる。`alive` に入っている時刻だけ生かす。"""
    return [(f"{date}T{t}", f"{prefix}{date[-2:]}{i}", 900 if t in alive else 1)
            for i, t in enumerate(times)]


_HIST = ["09:00", "09:30", "10:00", "10:30", "11:00",
         "11:30", "12:00", "12:30", "13:00", "13:30"]
_LATE = ["14:00", "14:30", "15:00", "15:30", "16:00"]


def _history():
    """08/20〜08/22: 09:00 から出して 10本 生き、14:00 以降が死ぬ日を3日。"""
    rows = []
    for d in ("2026-08-20", "2026-08-21", "2026-08-22"):
        rows += _day(d, _HIST + _LATE, set(_HIST))
    return rows


def test_同分の組がある日は上限の証拠にしない(tmp_path):
    """**逆に出る形を固定する。**

    窓が真（13:30 までは全部生きる）で、同分の組が**両方死ぬ**とき、
    その日の生きた本数は **9本** になります。これは**本数モデルの予測（10本）に
    着地する**ので、守りが無いと `verdict="count"` を確信つきで印字しました。
    """
    ties = ["09:00", "09:30", "10:00", "10:30", "11:00"]      # ここに2本目を重ねる
    early = ["05:00", "06:00", "07:00", "08:00"]
    rows = _history()
    # 08/27: 早い4本 + 09:00〜13:30 の10本（うち5つは同分の2本目つき）
    rows += _day("2026-08-27", early + _HIST, set(early + _HIST), prefix="a")
    rows += _day("2026-08-27", ties, set(), prefix="b")       # 組の2本目は死んだ側
    w = day_cap.window(_log(tmp_path, rows))

    assert w["verdict"] is None, "同分の組がある日から断定してはいけない"
    assert [str(d) for d, _g, _n in w["blocked"]] == ["2026-08-27"]
    assert w["blocked"][0][1] == 5, "5組"
    assert w["blocked"][0][2] == 10, "巻き込まれたのは10本"


def test_同分の日は当てはめにも使わない(tmp_path):
    """`C`/`T`/`floor` を、割り当てられない日から取らないこと。

    決めるときだけ外して当てはめに残すと、**汚れた日が C を決めます。**
    さらに `floor` に入れると、まともな日が全部 `a >= floor` から落ちて
    **証拠が空**になります（どちらも 2026-08-25 に踏んだ）。
    """
    rows = _history()
    # 同分の組を10組（20本）置いて、全部生かす ＝ 何もしなければ C が 20 に化ける
    rows += _day("2026-08-27", _HIST + _LATE, set(_HIST + _LATE), prefix="a")
    rows += _day("2026-08-27", _HIST + _LATE, set(_HIST + _LATE), prefix="b")
    w = day_cap.window(_log(tmp_path, rows))

    assert w["C"] == 10, "汚れた日から C を取っていない"
    assert w["days"] >= 1, "まともな日が floor に押し出されて空になっていない"


def test_散らしてあれば決まる(tmp_path):
    """**守りが強すぎないこと。** 同分を散らした 08/27 は、ちゃんと判定に入る。"""
    early = ["05:00", "06:00", "07:00", "08:00"]
    rows = _history()
    # 本数が真: 間隔で残った先頭10本だけ生きる（05:00〜11:30）
    alive = set(early + ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"])
    rows += _day("2026-08-27", early + _HIST, alive, prefix="a")
    w = day_cap.window(_log(tmp_path, rows))

    assert w["blocked"] == []
    assert w["verdict"] == "count"
    assert "2026-08-27" in w["decided_by"]


def test_試す日そのものが天井を決めない(tmp_path):
    """**本数モデルが、覆すために作った日で覆らない**形を固定する。

    `C` を「証拠の日の生きた本数の最大」で置くと、窓が真のとき 08/27 の
    生きた 14本 がそのまま `C=14` になり、`本数なら 14・窓なら 14` で
    **予測が一致して捨てられます。** 当てはめは前の日からやること。
    """
    early = ["05:00", "06:00", "07:00", "08:00"]
    rows = _history()
    rows += _day("2026-08-27", early + _HIST + _LATE,
                 set(early + _HIST), prefix="a")     # 窓が真: 13:30 までの14本が生きる
    w = day_cap.window(_log(tmp_path, rows))

    # **どの日で決めたかは問いません**（当てはめを持ち回った先で決まる）。
    # 問うのは「本数モデルが覆せたか」——覆せなければ、この実験は無意味です。
    assert w["verdict"] == "window", f"窓と出るはず: {w}"
    assert w["blocked"] == []


# --- **切り分けの日が、もう予約されていないか**（2026-08-25 に足した） ---
#
# `window_lines()` は「**08:59 より前から公開する日を1日作れ**」で終わっていました。
# ところが**このファイルの冒頭の註には「2026-08-27 に 05/06/07/08時 の4本を
# 置いてあります」と既に書いてあり**、実測でも 08/27 は19本が予約済みでした。
# **道具が知っているのに黙っている**形（`scripts/eta.py` の `blocking` と同じ）で、
# 放っておくと次の回が**もう1日**作ります —— 日が増えるほど交絡が増えます。

def _up(tmp_path, rows):
    import json
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


# **2026-08-27 に、選び方そのものを直しました**（下の `split_power` の節）。
# `c` / `t_min` は当てはめ済みの2つのモデルの値です。**検査では必ず渡すこと** ——
# 渡さないと `window()` が本物の `data/views.jsonl` を読み、
# **その日の実測でこの検査の結果が変わります。**
_FIT = {"c": 2, "t_min": 13 * 60 + 30}


def _booked(tmp_path, times_utc):
    return _up(tmp_path, [{"video_id": f"v{i}", "topic": f"s-{i}", "at": t}
                          for i, t in enumerate(times_utc)])


def test_切り分けの日が予約済みなら_その日と読める日を返す(tmp_path):
    # JST 05:00〜09:00（UTC は前日 20:00〜）—— **UTC の日で割ると前日に落ちます**
    up = _booked(tmp_path, ["2026-08-26T20:00:00Z", "2026-08-26T21:00:00Z",
                         "2026-08-26T22:00:00Z", "2026-08-26T23:00:00Z",
                         "2026-08-27T00:00:00Z"])
    b = day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 25), uploaded=up, **_FIT)
    assert b is not None
    assert b["day"] == "2026-08-27"
    assert b["before"] == 4                      # 08:59 より前 ＝ 05:00〜08:00
    assert b["total"] == 5
    assert (b["count"], b["window"], b["gap"]) == (2, 5, 3)
    # **読める日は「最後の本が齢 6時間」**。09:00 + 6h ＝ 15:00 JST（同じ日）。
    # ここは長らく **+5日**（「伸びきる2日 + Analytics 3日遅れ」）でした ——
    # `window()` が読む `data/views.jsonl` は **Data API** なので、Analytics の
    # 遅れは1日も掛かりません。2026-08-27 に、答えを6日 遅らせていたのを直した。
    assert b["answer"] == "2026-08-27"
    assert b["answer_at"] == "15:00"


def test_予測の差が付かない日は_切り分けの日にならない(tmp_path):
    """**門は「早い本があるか」ではなく「2つの予測が離れるか」**（2026-08-27 に直した）。

    ここは長らく「早い本が1本も無い日は切り分けの日にならない」でした。
    **必要でも十分でもありません** —— 下の2件がその反例です。
    """
    up = _booked(tmp_path, ["2026-08-27T00:00:00Z", "2026-08-27T01:00:00Z"])  # JST 09:00/10:00
    assert day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 25),
                                    uploaded=up, **_FIT) is None


def test_早い本が0でも_13時半より後ろが多ければ切り分ける(tmp_path):
    """**窓のほうが少なく予測する側**でも切り分きます（実測 2026-09-07 の形）。

    `booked_split_day()` は長らく「早い本が1本も無い日」を門前払いしていました。
    ところが 09/07〜09/19 は早い本が **0本**のまま、予測の差が **5本** あります
    ——13:30 より後ろに置いた本は、(A) では生きて (B) では死ぬからです。
    """
    up = _booked(tmp_path, ["2026-08-27T00:00:00Z",   # JST 09:00
                            "2026-08-27T01:00:00Z",   # JST 10:00
                            "2026-08-27T05:00:00Z",   # JST 14:00 —— 13:30 より後
                            "2026-08-27T06:00:00Z",   # JST 15:00
                            "2026-08-27T07:00:00Z",   # JST 16:00
                            "2026-08-27T08:00:00Z",   # JST 17:00
                            "2026-08-27T09:00:00Z",   # JST 18:00
                            "2026-08-27T10:00:00Z"])  # JST 19:00
    b = day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 25), uploaded=up,
                                 c=10, t_min=13 * 60 + 30)
    assert b is not None and b["before"] == 0
    assert (b["count"], b["window"], b["gap"]) == (8, 2, 6)


def test_今日の日を飛ばさない_走っている日が答える(tmp_path):
    """**その日が今日になった瞬間に対照日が消える**のを止めた（2026-08-27）。

    実測: 08/27 の予約は 19本・05:00 から30分きざみ・同じ分の組0 で、
    **(A) 10本 ／ (B) 18本**（差 8）。それでも `<= today` で飛ばしていたので、
    道具は **差 3 しかない 09/02** を名指しし、「読めるのは 09-07」
    「答えが返るまで他の日の本数を増やすな」と毎回 印字していました。
    """
    up = _booked(tmp_path, ["2026-08-26T20:00:00Z", "2026-08-26T21:00:00Z",
                         "2026-08-26T22:00:00Z", "2026-08-26T23:00:00Z",
                         "2026-08-27T00:00:00Z"])
    b = day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 27), uploaded=up, **_FIT)
    assert b is not None and b["day"] == "2026-08-27" and b["running"] is True


def test_過ぎた日は返さない_読みのほうで数えるから(tmp_path):
    up = _booked(tmp_path, ["2026-08-19T20:00:00Z"])   # JST 08/20 05:00
    assert day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 25),
                                    uploaded=up, **_FIT) is None


def test_控えの後の行を採る_予約を動かした本(tmp_path):
    """`uploaded.jsonl` は足すだけの帳面。**4つ目の読み手を書かない**ことの担保。"""
    up = _up(tmp_path, [
        {"video_id": "a", "topic": "s-1", "at": "2026-08-27T02:00:00Z"},   # JST 11:00
        {"video_id": "a", "topic": "s-1", "at": "2026-08-26T20:00:00Z"},   # → JST 08/27 05:00
        {"video_id": "b", "topic": "s-2", "at": "2026-08-26T21:00:00Z"},   # JST 06:00
        {"video_id": "c", "topic": "s-3", "at": "2026-08-26T22:00:00Z"},   # JST 07:00
        {"video_id": "d", "topic": "s-4", "at": "2026-08-26T23:00:00Z"},   # JST 08:00
        {"video_id": "e", "topic": "s-5", "at": "2026-08-27T00:00:00Z"},   # JST 09:00
    ])
    b = day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 25), uploaded=up, **_FIT)
    # 後の行（05:00）を採れば 08:59 より前は 4本。前の行（11:00）を採ると 3本。
    assert b is not None and b["before"] == 4 and b["total"] == 5


# --- **切り分ける力は、予約の形だけで先に分かる**（2026-08-27 に足した） ---

def test_split_power_門は差と同分の組の2つ():
    def t(hh, mm=0):
        return dt.datetime(2026, 8, 27, hh, mm, tzinfo=day_cap.JST)

    # 05:00 から30分きざみで 18本 ＋ 16:00 の1本 ＝ 実測 08/27 の形
    times = [t(5) + dt.timedelta(minutes=30 * i) for i in range(18)] + [t(16)]
    p = day_cap.split_power(times, 10, 13 * 60 + 30)
    assert (p["count"], p["window"], p["gap"], p["ties"]) == (10, 18, 8, 0)
    assert p["decisive"] is True

    # 同じ分に2本 —— そこで死んだ本を割り当てられないので、決めない
    tied = times + [t(16)]
    assert day_cap.split_power(tied, 10, 13 * 60 + 30)["decisive"] is False

    # 差が `DECIDE_GAP_MIN` 未満の日も決めない
    near = [t(9) + dt.timedelta(minutes=30 * i) for i in range(11)]
    p2 = day_cap.split_power(near, 10, 13 * 60 + 30)
    assert p2["gap"] < day_cap.DECIDE_GAP_MIN and p2["decisive"] is False
