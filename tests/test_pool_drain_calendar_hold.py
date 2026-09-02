"""**暦に穴が空いている間、`pool_drain --apply` は外さない**（API 0単位）。

## なぜ要るか（2026-09-02 01:0x に測って足した）

`scripts/pool_drain.py` と `scripts/reschedule.py --compact` は、
**同じ予約の山に、逆向きの手**を当てます。どちらも `[暦]` の鳴っている回に
候補として出てきます。実測（2026-09-02 01:0x の控え・予約 108本）:

    pool_drain            「残す 1本／**外す 107本**（5,457単位）」
    reschedule --compact  「**25本 を 09/03〜09/27 へ 1日1本**（1,250単位）」

**先に池化を撃つと、穴を埋める本がその場で無くなります** ——
106本 は 09/24〜10/09 に積んであり、手前の **09/03〜09/23 は 20日 まるごと 0本**。
外した本は private の下書きへ戻るので、入れ直しには `videos.update`（日枠の内側）が
要ります。**穴の20日は「埋める本が1本も無い」状態で確定します。**

どちらが先かは釣り合いで決まります —— 空白の20日は
**その間に閉じられたはずの前提が1件も閉じない**という意味で `eta.py` の θ に効き
（同じ回の実測: 今後14日 の θ は 0.57/日 ＝ 過去の 1.10/日 の 52%、
「この窓で縛っているのは公開の順番のほう」）、
作り置きが山のまま残ることは θ を1日も遅らせません。**穴が先です。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

pool_drain = pytest.importorskip("pool_drain")


def _cal(**kw) -> dict:
    base = {"total": 108, "days": 37, "empty": 20, "run": 19,
            "run_from": "2026-09-05", "over": []}
    base.update(kw)
    return base


def _patch(monkeypatch, cal: dict) -> None:
    from src import next_slot
    monkeypatch.setattr(next_slot, "calendar", lambda *a, **k: cal)


@pytest.fixture()
def legacy(monkeypatch):
    """**規則5（固定その4）が入る前の枝**を試すための札（2026-09-02）。

    オーナーが 2026-09-02 に「**現在の日付にしか予約しないってことだからね？**」を
    固定したので、**この門は既定で黙ります** —— 埋める手
    （`reschedule --compact --apply`）が、いま禁じられた手だからです。
    そして門が残っていると、**オーナーが名指しした `--apply --keep 0` が
    `--despite-gap` 無しでは1本も外せません**でした。

    **下の一群は消していません。** 規則5 が外れたら、そのまま効きます。
    """
    from src import house_rule
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", False)
    return house_rule


def test_規則5の下では門ごと黙る(monkeypatch):
    """**いまの既定**（2026-09-02）。空いた日は欠陥ではありません。"""
    from src import house_rule
    if not house_rule.same_day_only():
        pytest.skip("規則5 が外れています（この検査の前提）")
    _patch(monkeypatch, _cal())
    assert pool_drain._calendar_hold() == [], \
        "**規則5 の下で門が残っていると、`--apply --keep 0` が撃てません**"


def test_穴が空いていたら詰めるほうを名指しする(legacy, monkeypatch):
    _patch(monkeypatch, _cal())
    lines = pool_drain._calendar_hold()
    assert lines, "19日 連続の空白で黙るのは、この欠陥の再発です"
    body = "\n".join(lines)
    assert "reschedule.py --compact" in body
    assert "19日 連続" in body
    assert "2026-09-05" in body


def test_穴が埋まっていれば黙る(monkeypatch):
    """**そのとき池化が正になります。**「詰めてから、余りを外す」の順。"""
    _patch(monkeypatch, _cal(empty=0, run=0, run_from=None))
    assert pool_drain._calendar_hold() == []


def test_1日の空白では止めない(monkeypatch):
    """1日は詰める手の対象になりません（`run < 2` は黙る）。"""
    _patch(monkeypatch, _cal(empty=1, run=1, run_from="2026-09-05"))
    assert pool_drain._calendar_hold() == []


def test_予約が1本も無い回は黙る(monkeypatch):
    _patch(monkeypatch, _cal(total=0))
    assert pool_drain._calendar_hold() == []


def test_暦が読めない回は黙る_推測で止めない(monkeypatch):
    from src import next_slot

    def _boom(*a, **k):
        raise RuntimeError("控えが読めない")

    monkeypatch.setattr(next_slot, "calendar", _boom)
    assert pool_drain._calendar_hold() == []


def _stub(monkeypatch, dropped: list, thumbs: list):
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
    rows = [{"id": f"v{i}", "title": f"t{i}", "topic": "s-x",
             "at": base + timedelta(hours=i)} for i in range(3)]
    monkeypatch.setattr(pool_drain, "pool", lambda *a, **k: rows)
    monkeypatch.setattr(pool_drain, "plan", lambda r, keep: (r[:1], r[1:]))
    monkeypatch.setattr(pool_drain, "by_day", lambda r: {})
    monkeypatch.setattr(pool_drain, "today_rows", lambda r: [])
    monkeypatch.setattr(pool_drain, "swap_reserve", lambda *a, **k: None)
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda *a, **k: "NEXT1")
    monkeypatch.setattr(pool_drain, "_push_thumbnail_first",
                        lambda vid: (thumbs.append(vid), 0)[1])
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda: {})
    # **`report=` を受けること**（2026-09-02。上と同じ理由）。
    def _stub_update(svc, vid, at, fallback_status=None, report=None):
        dropped.append(vid)
        if report is not None:
            report.update({"wrote": True, "reason": "wrote"})
        return True

    monkeypatch.setattr(pool_drain.reschedule, "_update", _stub_update)
    monkeypatch.setattr(pool_drain.dupes, "retime", lambda vid, at: None)


def test_apply_は穴が空いている間_1本も外さない(legacy, monkeypatch, capsys):
    """**門は「外す」の直前です。**`--despite-gap` を付けた回だけ通します。

    **サムネイル（50単位）は門より前**に残してあります —— あれは §4 が
    いちばん高い 50単位 と呼んでいる手で、暦の穴とは関係がありません。
    ここで止めるのは `videos.update`（外す）のほうだけです。
    """
    _patch(monkeypatch, _cal())
    dropped: list = []
    thumbs: list = []
    _stub(monkeypatch, dropped, thumbs)

    rc = pool_drain.main(["--apply", "--no-inbox"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "この回は外しません" in out
    assert "--despite-gap" in out
    assert not dropped, "穴が空いているのに外しています"
    assert thumbs == ["NEXT1"], "サムネイル（50単位）まで止めています"


def test_despite_gap_を付けた回は通る(legacy, monkeypatch, capsys):
    """**逃げ道を残すこと**（理由を JOURNAL に）。"""
    _patch(monkeypatch, _cal())
    dropped: list = []
    thumbs: list = []
    _stub(monkeypatch, dropped, thumbs)

    rc = pool_drain.main(["--apply", "--no-inbox", "--despite-gap"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "この回は外しません" not in out
    assert dropped, "`--despite-gap` でも外せないなら、逃げ道になっていません"


def test_数えるだけの回にも順番は出る(legacy, monkeypatch, capsys):
    """**撃つ前に順番が見えていないと、次の回がまた同じ順で撃ちます。**"""
    _patch(monkeypatch, _cal())
    _stub(monkeypatch, [], [])
    pool_drain.main(["--no-inbox"])
    out = capsys.readouterr().out
    assert "reschedule.py --compact" in out
    assert "この回は外しません" not in out      # 数えるだけの回に門は要りません
