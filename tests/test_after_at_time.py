"""**「その日が来た」と「そのデータが出た」は別です。**

## この試験が守っているもの（2026-08-27・最適化の回）

`scripts/deadline_check.py` の `kind: after` は**日の粒**しか持っていませんでした。
`scripts/drift.py` の `split_overdue()` は `str(ready) <= today` で見るので、
**その日の 00:00 から「いま判定できる」**と言います。

**実際に踏みました。** 2026-08-27 **00:22 JST** に `drift.py` が

    **期限が来ていて、いま判定できる前提: 1件**
    [!] **外れています。** … **この回は verdict を出すこと。**

と印字しました。要るデータは **05/06/07/08時 の4本の、公開から6時間の読み**で、
`config/hypotheses.yaml` の `falsified_if` は
「`data/views.jsonl` が **08-27 14:00 JST 以降**の点を持っていること。
持っていなければ判定せず、期限だけ延ばすこと」と**散文で**書いていました。
そのとき `src/day_cap.window()` は `confounded=True` / `verdict=None` です。

**正しい文はあって、門が読んでいたのは日付だけ**でした。
しかも**その早撃ちは一度 起きています**（同じ前提の `note`:
「本数モデルの予測（10本）に着地して `verdict='count' confounded=False` を
印字しました —— **確信つきで逆**です」）。

**この前提は `density` の腕の天井（1日 10本 → 18枠 ＝ 1.8倍）を決めます。**
早撃ちで逆に閉じると、天井を間違えたまま到達日を解き続けます。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))


def _dc():
    spec = importlib.util.spec_from_file_location(
        "dc_under_test", ROOT / "scripts" / "deadline_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dc_under_test"] = mod
    spec.loader.exec_module(mod)                    # type: ignore[union-attr]
    return mod


@pytest.fixture()
def dc():
    return _dc()


def test_時刻が来る前は日を返さない(dc, monkeypatch):
    """**これが本体です。** 日は来ていても、時刻が来ていなければ `ready` は出ません。"""
    today = datetime.now(JST).date()

    class 朝(dc.datetime):                                     # noqa: N801
        @classmethod
        def now(cls, tz=None):
            return dc.datetime(today.year, today.month, today.day, 0, 22, tzinfo=JST)

    monkeypatch.setattr(dc, "datetime", 朝)
    need = {"kind": "after", "on_date": today.isoformat(),
            "at_time_jst": "14:00", "what": "6時間の読み"}
    a = dc._ans_after(need, 3)
    assert a.ready is None, "時刻が来ていないのに判定できる日を出しています"
    assert "14:00" in a.why and "まだ出ていません" in a.why


def test_時刻を過ぎたら日を返す(dc, monkeypatch):
    """**遅らせる道具ではありません。** 時刻を過ぎたら、その日が `ready` です。"""
    today = datetime.now(JST).date()

    class 夕(dc.datetime):                                     # noqa: N801
        @classmethod
        def now(cls, tz=None):
            return dc.datetime(today.year, today.month, today.day, 14, 1, tzinfo=JST)

    monkeypatch.setattr(dc, "datetime", 夕)
    need = {"kind": "after", "on_date": today.isoformat(),
            "at_time_jst": "14:00", "what": "6時間の読み"}
    assert dc._ans_after(need, 3).ready == today


def test_時刻を書かない要件は今までどおり(dc):
    """**既定を変えていません。** `at_time_jst` の無い `after` は日の粒のまま。"""
    d = date(2026, 9, 30)
    a = dc._ans_after({"kind": "after", "on_date": d.isoformat(), "what": "x"}, 3)
    assert a.ready == d


def test_読めない時刻は日を出さない(dc):
    """**黙って日の粒へ倒さないこと。** 書いてあるのに読めないなら、止まるほうがよい。"""
    d = date.today()
    a = dc._ans_after({"kind": "after", "on_date": d.isoformat(),
                       "at_time_jst": "ごご2じ", "what": "x"}, 3)
    assert a.ready is None
    assert "at_time_jst" in a.why


def test_台帳の側にも時刻が入っている():
    """**この前提だけは、時刻まで書いてあること**（散文の `falsified_if` と一致させる）。

    **覆る条件**: 08/27 の切り分けが閉じたら、この前提ごと台帳から消えます。
    そのとき**この試験も畳むこと** —— 残すと、次に来た側が
    「消えた前提を探して直す」ほうへ回ります。
    """
    rows = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text())
    hyps = rows.get("hypotheses") if isinstance(rows, dict) else rows
    hit = [h for h in hyps
           if "時刻の窓ではない" in str(h.get("claim") or "")]
    if not hit:
        pytest.skip("前提が閉じました（この試験も畳んでよい）")
    needs = hit[0].get("needs") or []
    assert any(n.get("at_time_jst") for n in needs), (
        "`falsified_if` は「14:00 JST 以降の点」と言っているのに、"
        "`needs` は日付しか持っていません —— **門はそちらを読みます**"
    )
