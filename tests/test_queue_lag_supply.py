"""**「置ける枠がある」と「その本を作れる」は別の話です**（2026-08-27）。

`scripts/queue_lag.band_lines()` は「足りない N本 を帯に置くと、最後の1本は M/D」と
出します —— **枠の話しかしていません。** `python -m src.supply` は
「在庫＋掃引の候補で T本・いつ尽きる」と出します —— **要る本数を知りません。**

**その2つを引き算する所が、どこにも無かった**というのがこの検査の対象です。
実測 2026-08-27:

    要る    114本（`request_form` 途中あり 58 ／ 終端のみ 56）
    材料    110本 × ショート率 91% ＝ **100本** → **14本 足りません**
    枠      114本目は 10/01 で、公開の期限 09/30 を **1日 越えます**

**どちらの道具も「足りない」とは一言も言っていませんでした。**
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import queue_lag as QL  # noqa: E402

JST = timezone(timedelta(hours=9))


def _fake_supply(monkeypatch, total: int, stock: int = 10, novel: int = 100,
                 undecided: int = 20, dry: date | None = None):
    from src import supply as _supply

    monkeypatch.setattr(_supply, "sweep_novel",
                        lambda **_kw: {"novel": novel, "undecided": undecided,
                                       "total": novel, "at": None, "age_hours": 0.0})
    monkeypatch.setattr(
        _supply, "supply",
        lambda *_a, **_kw: {"supply_total": total, "stock": stock,
                            "sweep_novel": novel, "sweep_undecided": undecided,
                            "dry_date": dry or date(2026, 9, 7)})


def test_足りない群が無ければ何も出さない():
    assert QL.supply_lines([]) == []


def test_材料が足りなければ本数で言う(monkeypatch):
    """**「作って帯へ置くこと」だけで終えないこと。** 作れない回があります。"""
    _fake_supply(monkeypatch, total=100)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines", lambda: {})
    out = "\n".join(QL.supply_lines([("k", "g", 114)]))
    assert "114本" in out and "14本 足りません" in out
    # **床を下げて釣り合わせないこと**を、同じ所で言うこと
    assert "床は下げないこと" in out


def test_材料が足りていれば律速は枠だと言う(monkeypatch):
    _fake_supply(monkeypatch, total=500)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines", lambda: {})
    out = "\n".join(QL.supply_lines([("k", "g", 114)]))
    assert "足ります" in out and "枠のほうです" in out
    assert "足りません" not in out


def test_ショートだけを数える前提には_ショート率を掛ける(monkeypatch):
    """**材料の総数をそのまま当てないこと。** 長尺は群に入りません。"""
    _fake_supply(monkeypatch, total=110)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: ["request_form"])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: (91, 100))
    monkeypatch.setattr(QL.judgeable, "deadlines", lambda: {})
    out = "\n".join(QL.supply_lines([("request_form", "途中あり", 114)]))
    assert "**100本**" in out          # 110 × 0.91
    assert "14本 足りません" in out


def test_ショートだけかは_宣言ではなく標本から見る(monkeypatch):
    """`_members_by_request_form` の「長尺は落ちる」を**写さない**こと。

    写した所は腐ります（この repo で6回 起きた形）。
    """
    monkeypatch.setattr(QL.judgeable, "_short_topics", lambda: {f"s-{i}" for i in range(10)})
    monkeypatch.setattr(QL.judgeable, "_video_by_topic",
                        lambda: {f"s-{i}": f"v{i}" for i in range(10)} | {"long-1": "vL"})
    ms_short = {"a": [(date(2026, 8, 27), f"v{i}") for i in range(5)],
                "b": [(date(2026, 8, 27), f"v{i}") for i in range(5, 10)]}
    monkeypatch.setattr(QL.judgeable, "members", lambda _k: ms_short)
    assert QL._shorts_only(["x"]) == ["x"]

    # 長尺が1本でも混ざれば「ショートだけ」ではない
    ms_mixed = {"a": ms_short["a"] + [(date(2026, 8, 27), "vL")], "b": ms_short["b"]}
    monkeypatch.setattr(QL.judgeable, "members", lambda _k: ms_mixed)
    assert QL._shorts_only(["x"]) == []


def test_標本が少なすぎる回は_ショートだけと言わない(monkeypatch):
    """**8本 未満で決めつけないこと**（引きの偏りで反対を言います）。"""
    monkeypatch.setattr(QL.judgeable, "_short_topics", lambda: {"s-0", "s-1"})
    monkeypatch.setattr(QL.judgeable, "_video_by_topic", lambda: {"s-0": "v0", "s-1": "v1"})
    monkeypatch.setattr(QL.judgeable, "members",
                        lambda _k: {"a": [(date(2026, 8, 27), "v0"), (date(2026, 8, 27), "v1")]})
    assert QL._shorts_only(["x"]) == []


def test_帯の最後の1本が期限を越えたら言う(monkeypatch):
    """**材料さえ足せば閉じる、と読ませないこと。**

    実測 2026-08-27 は**材料も枠も**足りていませんでした（最後の1本が期限の翌日）。
    """
    _fake_supply(monkeypatch, total=500)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines",
                        lambda: {"request_form": date(2026, 10, 6)})
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    due = date(2026, 10, 6) - timedelta(days=lag)
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: (due + timedelta(days=1), 35))
    out = "\n".join(QL.supply_lines([("request_form", "途中あり", 114)]))
    assert "期限を 1日 越えます" in out
    assert "材料を足しても" in out

    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: (due - timedelta(days=1), 33))
    out2 = "\n".join(QL.supply_lines([("request_form", "途中あり", 114)]))
    assert "枠の側は間に合います" in out2


def test_公開の期限は判定日から落ち着きと遅れを引いたもの(monkeypatch):
    """**判定日を公開の期限として読ませないこと**（`_ready()` と同じ引き方）。"""
    _fake_supply(monkeypatch, total=500)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines",
                        lambda: {"request_form": date(2026, 10, 6)})
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    out = "\n".join(QL.supply_lines([("request_form", "途中あり", 114)]))
    assert str(date(2026, 10, 6) - timedelta(days=lag)) in out


def test_walk_days_は同じ問いを2度_解かない():
    """`band_lines` と `supply_lines` が同じ数を要ります（`live_plan` は数秒）。"""
    calls = []

    class _BB:
        @staticmethod
        def live_plan(n, grid=None, horizon=None, cap=None):
            calls.append(n)
            base = datetime.now(JST).date()
            return [(f"t{i}", base + timedelta(days=i // 10)) for i in range(n)]

    QL._WALK.clear()
    grid = [(9, 0), (9, 30)]
    a = QL._walk_days(_BB, 12, grid)
    b = QL._walk_days(_BB, 12, grid)
    assert a == b and len(calls) == 1
    QL._WALK.clear()


def test_実物で落ちない():
    """**実物の出力で1件は見ること**（作り物だけだと、実データの形で落ちます）。"""
    _per_day, _ans, short = QL.answering(QL.scheduled())
    out = QL.supply_lines(short)
    assert isinstance(out, list)
    if short:
        assert any("材料" in s for s in out)


def test_掃引の点の古さを出す(monkeypatch):
    """**この節の結論は、点の古さで符号ごと変わります**（実測 2026-08-27）。

    0.4時間前 の点で「14本 足りない」→ 測り直すと「10本 余る」（候補 568 → 735件）。
    古さを出さないと、**24本 ずれた数で符号が決まります。**
    """
    from src import supply as _supply

    monkeypatch.setattr(_supply, "sweep_novel",
                        lambda **_kw: {"novel": 100, "undecided": 20, "total": 100,
                                       "at": None, "age_hours": 3.5})
    monkeypatch.setattr(_supply, "supply",
                        lambda *_a, **_kw: {"supply_total": 500, "stock": 10,
                                            "sweep_novel": 100, "sweep_undecided": 20,
                                            "dry_date": date(2026, 9, 9)})
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines", lambda: {})
    out = "\n".join(QL.supply_lines([("k", "g", 114)]))
    assert "3.5時間前" in out


def test_足りないときは_先に測り直させる(monkeypatch):
    """**測らずに「足りない」を信じないこと。** 実測で符号が変わっています。"""
    _fake_supply(monkeypatch, total=100)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines", lambda: {})
    out = "\n".join(QL.supply_lines([("k", "g", 114)]))
    assert "まず測り直すこと" in out and "--measure" in out
    assert "符号ごと変わります" in out


def test_帯の超過は下限だと言う(monkeypatch):
    """`live_plan()` は**今日から全部 詰めた場合**。実際は遅れこそすれ早まりません。"""
    _fake_supply(monkeypatch, total=500)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines",
                        lambda: {"request_form": date(2026, 10, 6)})
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    due = date(2026, 10, 6) - timedelta(days=lag)
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: (due + timedelta(days=1), 35))
    out = "\n".join(QL.supply_lines([("request_form", "途中あり", 114)]))
    assert "**下限**です" in out


def test_期限を越えると出したら_突き合わせ先も同じ所に出す(monkeypatch):
    """**この行だけで期限を書き換えさせないこと**（2026-08-27 に危うくやりかけた）。

    `scripts/deadline_check.py` は同じ床を**伸び率**から解いていて、実測 08/27 は
    `request_form` を **09/30・±10日** と出しました —— こちらの帯の歩き（10/01）と
    **1日** しか違いません。**帯の中なら書き換えても届く日は1日も動きません。**
    """
    _fake_supply(monkeypatch, total=500)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines",
                        lambda: {"request_form": date(2026, 10, 6)})
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    due = date(2026, 10, 6) - timedelta(days=lag)
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: (due + timedelta(days=1), 35))
    out = "\n".join(QL.supply_lines([("request_form", "途中あり", 114)]))
    assert "deadline_check.py" in out
    assert "帯の中なら期限を書き換えないこと" in out
    assert "床を下げるのは、どちらの場合も禁止" in out


def test_どの群にも入らない本を_作りすぎと読ませない(monkeypatch):
    """**符号が逆になる読み違えです**（2026-08-27 に自分で読み違えかけた）。

    予約に居る 258本（79%）が群に入らないのは、**作った時刻**で群が決まるから
    （`judgeable._members_by_request_form` の `built < exp.landed`）。
    **入れ替えても後から群には入りません。** 一方これから作るショートは自動で入るので、
    答えは「作るのをやめる」ではなく **「作り続ける」**です。
    """
    import datetime as _dt

    now = _dt.datetime.now(JST)
    rows = [{"video_id": f"v{i}", "at": now + timedelta(days=1, minutes=30 * i),
             "topic": f"t{i}"} for i in range(6)]
    monkeypatch.setattr(QL.day_cap, "live_ids", lambda _rows: {r["video_id"] for r in rows})
    monkeypatch.setattr(QL, "published", lambda: rows)
    monkeypatch.setattr(QL, "open_floors",
                        lambda: [("request_form", "途中あり", 72,
                                  [(now.date(), "v0")])])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: (91, 100))
    monkeypatch.setattr(QL, "band_lines", lambda *_a, **_k: [])
    monkeypatch.setattr(QL, "supply_lines", lambda *_a, **_k: [])
    out = "\n".join(QL.answering_lines(rows))
    assert "「作りすぎ」ではありません" in out
    assert "作り続ける" in out
    assert "91%" in out


def test_毎回_読む道具に_この節が載っていること():
    """**`status.py` に無い節は、主実行から見て存在しません**（2026-08-27）。

    `CLAUDE.md` が「分析は毎回やる」と名指ししているのは `scripts/status.py` だけです。
    この節（材料の引き算・期限の超過・「作りすぎではない」）は、
    長いあいだ `queue_lag.py` を**手で撃った回だけ**が読めていました ——
    前の回の日誌が「書き足した所が読まれていない」と言っていた形そのものです。

    **`status.py` は `lag_lines` しか呼んでいませんでした。**
    """
    src = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "answering_lines(" in src, (
        "`status.py` が `queue_lag.answering_lines()` を呼んでいません。"
        "呼ばないと、材料と期限の引き算は主実行から見えません"
    )


def test_足りない前提が2件_以上なら_合計だと断る(monkeypatch):
    """**黙って1件の話にしないこと。** `need` は足りない群ぜんぶの合計です。

    **2026-08-28 に、この検査の当たり先を変えました。**
    元の版は「合計です・2件」という**断りの文言**だけを見ていました ——
    ところが `ee2ec73` が足したのはその断りだけで、**判定に使う数は合計のまま**
    でした（下の `test_群ごとの期限は_その群だけの本数で歩く` が本体）。
    **断りが出ていることは、正しく判定していることを1つも意味しません。**
    だからここは「群ごとの本数が出ていること」と
    「合計も伏せずに併記していること」の両方を見ます。
    """
    _fake_supply(monkeypatch, total=500)
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines",
                        lambda: {"a": date(2026, 10, 6), "b": date(2026, 10, 8)})
    monkeypatch.setattr(QL, "_walk_days", lambda *_a, **_k: (date(2026, 9, 1), 5))
    out = "\n".join(QL.supply_lines([("a", "g1", 40), ("b", "g2", 20)]))
    # 群ごとの本数で語ること（合計 60本 を両方に当てない）
    assert "`a` の 40本" in out and "`b` の 20本" in out
    # 合計も伏せないこと
    assert "合計 60本" in out

    # 1件だけの回には、合計の断りは出さない（雑音になる）
    out1 = "\n".join(QL.supply_lines([("a", "g1", 40)]))
    assert "合計" not in out1
