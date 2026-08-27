"""**群ごとに歩くこと**（2026-08-28・最適化の回。実測で**符号が逆に出ていました**）。

`scripts/queue_lag.supply_lines()` は長らく、足りない群の**合計** `need` で帯を
1回だけ歩き、**その1つの日付を、群ごとの期限に順に当てて**いました。
つまりどの群についても「**その群が最後に埋まる場合**」しか見ていません ——
**足りない群が2件 以上ある回は、それが全部の群について同時に真になりえません**
（最後に埋まる群は1つだけです）。

実測 2026-08-28（`request_form` 99本 ／ `slide_pace` 20本 ＝ 合計 119本）:

    合計で歩く   119本 → 10/04  → `slide_pace` は期限を **17日 超過**
    群だけで歩く  20本 → 09/11  → `slide_pace` は期限まで **6日 余裕**

**`slide_pace` の「材料を足しても、この床は期限内に埋まりません」は、まるごと偽**
でした。`request_form` も 99本 単独なら超過 **5日 → 2日**（2.5倍 の膨らみ）。

そして直すと、**独立した2つの道具が一致します** ——
`scripts/deadline_check.py` は伸び率から `slide_pace` を
「09-24（±10日）・期限はその帯の中」＝ **間に合う** と出しており、
**合計で歩いた側だけが逆を言っていました。**

**08/27 に見つからなかった理由**: あの日 足りない群は `request_form` **1件だけ**で、
**合計 ＝ 単独** でした。**この穴は、群が2件 以上ある回にしか現れません。**
2026-08-27 の `ee2ec73` は「合計です」と**註を足しただけ**で、
**数のほうは合計のまま**でした（＝ 表示は直り、判定は直っていない）。

## この検査が守っているもの

1. 群ごとの期限は、**その群だけの本数**で歩いた日と比べる
2. 自分だけなら間に合う群には、**「順番で決まる」と言い、順番を名指しする**
   （＝ その回に選べる手がある、と分かる形にする）
3. **単独でも越える群には、はっきり越えると言う**（逆向きも守る）

## 覆る条件

`live_plan()` が「どの群の本か」を見て置くようになったら（いまは見ていません）、
「先に埋める」は道具側で自動に決まるので、2 の名指しは要らなくなります。
そのときはここの 2 を落として構いません —— **1 と 3 は残すこと。**
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import queue_lag as QL  # noqa: E402


def _walk_by_need(base: date):
    """`need` 本 ＝ `base` から `need` 日後、という当てもの。

    **群ごとの本数で呼ばれているか**を見るためのものです ——
    合計で呼んでいれば、どの群についても同じ日が返ります。
    """
    def _w(_bb, need, _grid, cap="auto"):                        # noqa: ANN001
        return (base + timedelta(days=int(need)), int(need))
    return _w


def _stub(monkeypatch, deadlines: dict[str, date]) -> None:
    from src import supply as _supply

    monkeypatch.setattr(_supply, "sweep_novel",
                        lambda **_kw: {"novel": 100, "undecided": 20,
                                       "total": 100, "at": None, "age_hours": 0.0})
    monkeypatch.setattr(
        _supply, "supply",
        lambda *_a, **_kw: {"supply_total": 5000, "stock": 10,
                            "sweep_novel": 100, "sweep_undecided": 20,
                            "dry_date": date(2026, 9, 7)})
    monkeypatch.setattr(QL, "_shorts_only", lambda _keys: [])
    monkeypatch.setattr(QL, "_short_share", lambda *_a, **_k: None)
    monkeypatch.setattr(QL.judgeable, "deadlines", lambda: deadlines)


def test_群ごとの期限は_その群だけの本数で歩く(monkeypatch):
    """**合計の日付を、群ごとの期限に当てないこと。**

    小さい群（20本）は、大きい群（99本）の後ろに積まれた日付ではなく、
    **自分の 20本 だけを置いた日付**で期限と比べること。
    """
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    base = date(2026, 8, 28)
    _stub(monkeypatch, {"big": base + timedelta(days=99 + lag),
                        "small": base + timedelta(days=20 + lag)})
    monkeypatch.setattr(QL, "_walk_days", _walk_by_need(base))
    out = "\n".join(QL.supply_lines([("big", "g", 99), ("small", "g", 20)]))

    # 合計 119本 で歩いた日（base+119）を、どちらの群にも当てていないこと
    assert "119日" not in out
    assert "`small` の 20本" in out
    assert "`big` の 99本" in out
    # 小さい群は、自分だけなら間に合う ＝ **偽の「埋まりません」を出さない**
    assert "`small` に要る" not in out


def test_順番で決まる回は_順番を名指しする(monkeypatch):
    """**「間に合いません」で終えないこと。**

    自分だけなら間に合い、後回しにすると越える群は、
    足りないのは**本でも材料でもなく順番**です。**その回に選べる手があります。**
    """
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    base = date(2026, 8, 28)
    _stub(monkeypatch, {"big": base + timedelta(days=200 + lag),
                        "small": base + timedelta(days=26 + lag)})
    monkeypatch.setattr(QL, "_walk_days", _walk_by_need(base))
    out = "\n".join(QL.supply_lines([("big", "g", 99), ("small", "g", 20)]))

    assert "順番で決まります" in out
    assert "先に埋めれば **間に合います**" in out
    assert "`small` を`big` より先に埋めること" in out
    # **偽の断定を出さないこと**（これが 08/28 に消した行）
    assert "この群だけを最優先しても間に合いません" not in out


def test_単独でも越える群には_はっきり越えると言う(monkeypatch):
    """**逆向きも守ること。** 順番を変えても届かない群は、そう言う。

    ここを緩めると「順番さえ直せば全部間に合う」と読めます ——
    実測 2026-08-28 の `request_form` は、99本 単独でも **2日 越え**ていました。
    """
    lag = QL.SETTLE_DAYS + QL.judgeable.ANALYTICS_LAG_DAYS
    base = date(2026, 8, 28)
    _stub(monkeypatch, {"big": base + timedelta(days=97 + lag),
                        "small": base + timedelta(days=200 + lag)})
    monkeypatch.setattr(QL, "_walk_days", _walk_by_need(base))
    out = "\n".join(QL.supply_lines([("big", "g", 99), ("small", "g", 20)]))

    assert "この群だけを最優先しても間に合いません" in out
    assert "期限を 2日 越えます" in out          # 合計 119本 の 22日 ではない
    assert "材料を足しても" in out
    # 後回しにした場合の日も、伏せずに並べること
    assert "最後に回すと" in out
