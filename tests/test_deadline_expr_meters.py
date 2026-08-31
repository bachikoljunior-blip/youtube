"""`count_expr` から計器を引く表が、式の名前空間とずれないこと。

## なぜ要るか（2026-08-31・最適化の回）

`scripts/deadline_check.py` の `_stale_todo` は「計器が止まっているのに
『あと N日』と出る」を塞ぐ門です。**要件が `needs.data_file:` を申告した
ときだけ**効いていて、実測 2026-08-31 の申告率は **16/22件**でした。

素通りしていた 6件 のうち 5件 は、`count_expr` が `latest_views()` /
`rows('batch_runs.jsonl')` のような**閉じた名前**を呼んでいるだけで、
どのファイルを開くかは `deadline_check.py` 自身に書いてあります。
そこで `_EXPR_METERS` から引くようにしました（申告があればそちらが勝つ）。

**この直しは、表と名前空間が同じ形でいるあいだだけ正しい。**
`EXPR_NS` に名前が増えて `_EXPR_METERS` に載らなければ、
その名前を使う要件は**黙って素通り**に戻ります —— 08/27 に取り下げた
「偽の判定日」と同じ形で、しかも今度は「引けているはず」が支えます。

だからここで留めます。**計器を開かない名前は `_EXPR_NO_METER` に置くこと。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deadline_check as dc  # noqa: E402


def test_EXPR_NS_の名前は全部_表かNO_METERに載っていること():
    unmapped = sorted(
        k for k in dc.EXPR_NS
        if k not in dc._EXPR_METERS and k not in dc._EXPR_NO_METER
    )
    assert not unmapped, (
        f"`EXPR_NS` に足して `_EXPR_METERS` に載せていない名前: {unmapped}。"
        "計器を開くなら `_EXPR_METERS` へ、開かないなら `_EXPR_NO_METER` へ。"
        "どちらにも無いと、その名前を使う要件は黙って素通りします"
    )


def test_表に載る名前は_EXPR_NSに実在すること():
    ghosts = sorted(k for k in dc._EXPR_METERS if k not in dc.EXPR_NS)
    assert not ghosts, f"`EXPR_NS` に無い名前が表に居ます: {ghosts}"


def test_引いた計器のパスは_dataの下であること():
    for name, files in dc._EXPR_METERS.items():
        for f in files:
            assert f.startswith("data/"), f"{name}: {f}"


def test_式から計器を引けること():
    assert dc._expr_meters("sum(v for v in latest_views().values())") == [
        "data/views.jsonl"]
    assert dc._expr_meters("len(rows('batch_runs.jsonl'))") == [
        "data/batch_runs.jsonl"]
    # 2つ呼べば2つ返る（**いちばん古いほうで鳴らす**ため）
    got = dc._expr_meters("sum(latest_views().get(v, 0) for v in long_ids())")
    assert set(got) == {"data/views.jsonl", "data/batch_runs.jsonl"}
    # 計器を開かない名前では鳴らさない
    assert dc._expr_meters("ab_members('x')") == []
    assert dc._expr_meters("") == []


def test_申告があるときは申告が勝つこと():
    """人が「この式はこの計器で待つ」と決めた場合を、機械が上書きしないこと。"""
    need = {"kind": "accrual", "data_file": "data/reach.jsonl",
            "count_expr": "sum(latest_views().values())",
            "stale_after_hours": 100000}
    # 申告した計器はまだ新しい扱い（しきい値を大きく取る）＝ 何も言わない。
    # 引く側（views.jsonl）が古くても、申告が勝つので黙ること。
    assert dc._stale_todo(need) == ""


def test_取り直す手は日枠の一覧が読める名前で書くこと():
    """`_refresh_pool_note` は `upload_cap.DATA_API_TOOLS` と文字列一致で
    「いまこの窓で撃てるか」を決めます。同じことをする道具でも、
    **一覧に載っているほうの名前**を書かないと、日枠が尽きている窓で
    「いま撃てます」と嘘を出します（2026-08-31 に踏んだ ——`status.py` は
    一覧に無く、実際には `channels.list` で 403 を踏んで落ちます）。"""
    from src import upload_cap

    tools = tuple(upload_cap.DATA_API_TOOLS)
    assert "scripts/snapshot.py" in tools
    assert dc._METER_REFRESH["data/views.jsonl"] == "python scripts/snapshot.py"
