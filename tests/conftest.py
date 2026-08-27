"""**検査は、本物の台帳に書かないこと**（2026-08-17 に踏んで足した）。

`data/alerts.jsonl` の `status_lines` は 8回鳴って当たり0で畳まれ、
`status.py` の「警告の当たり率」にもそう出ていました。実物を数えると、
**8回とも鳴らしたのは `pytest`** です（`alerts._dedupe_token()` はセッションIDなので、
1周につき1行きっかり積まれる）。**`status.py` の出力が中央値の1.5倍を超えたことは
一度もありません。**

    当たり率という計器が、測っていたのは **検査の実行回数** でした。

そして8回目で畳まれた瞬間、**その畳みを見にいく検査そのものが赤くなります**
（`tests/test_status_lines.py::test_the_actual_break_would_have_rung`）。
放っておくと、次の子は毎回**赤い pytest で始まります** ——
8/17 14:1x の申し送り「届いた直後に pytest を叩く手順が要る」の、まさに逆側です。

**これは `src/alerts.py` の「一覧が当たりを含まないまま育つ」の7件目ですが、
原因の向きが新しい**（育て方でも時刻でもなく、**鳴らしている側が検査だった**）。

ここで環境変数を立てるのは、**呼ぶ側に何も書かせないため**です。
「検査では `ledger=` を渡す」を約束にすると、一覧を足した回が必ず片方だけ忘れます
（通算7回踏んだ形）。**`conftest.py` は全部の検査に自動で掛かります。**
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _alerts_ledger_to_tmp(tmp_path_factory):
    """`src/alerts.py` の台帳を、この検査だけの場所へ向ける。

    **`src` を import する前に環境変数を立てても間に合いません**
    （`alerts` は import 時に `LEDGER` を決めるので、import 済みなら効かない）。
    だから**モジュールの属性を直接差し替えます。**
    """
    d = tmp_path_factory.mktemp("alerts")
    os.environ["YT_ALERTS_LEDGER"] = str(d / "alerts.jsonl")
    os.environ["YT_ALERTS_RUNS"] = str(d / "runs.jsonl")

    from src import alerts

    keep = (alerts.LEDGER, alerts.RUNS)
    alerts.LEDGER = d / "alerts.jsonl"
    alerts.RUNS = d / "runs.jsonl"
    # **`ship()` の反映も、ここで止めます**（2026-08-20 に足した。理由は同じ）。
    # `tests/test_closes_vocab.py` は `run_marker.ship()` を直接呼ぶので、
    # 反映を既定にしたら**本物の `data/eta.jsonl` に 19行**入りました。
    # **`growth_per_day()` の回帰を汚す向き**なので、規律ではなく機械で外します。
    os.environ["YT_SKIP_REFLECT"] = "1"

    yield
    alerts.LEDGER, alerts.RUNS = keep


@pytest.fixture(autouse=True, scope="session")
def _measure_window_dynamic_off():
    """**`measure_window` の動的な窓を、検査のあいだ止める**（2026-08-27 に足した）。

    `WINDOWS` は手で書いた日付なので、`inside()` は純粋な関数でした。
    2026-08-27 に `day_cap` の**切り分けの対照日**を動的に守るようにしたので、
    **`inside()` は本物の予約（`data/uploaded.jsonl`）に依ります。**

    そうすると、**「適当な未来の日」を定数に使っている検査**が、
    たまたまその日が対照日になった回だけ落ちます ——
    実測 2026-08-27: `tests/test_live_slots.py` の5件が `2026-09-02` を
    使っていて、まとめて赤くなりました。**中身は1行も変わっていません。**

    **呼ぶ側に「その日は避けて書いてね」と約束させないこと** ——
    このファイルの冒頭が、まさにその理由で書かれています
    （「一覧を足した回が必ず片方だけ忘れる」通算7回）。

    動的な窓そのものは `tests/test_measure_window_split_day.py` が
    **旗を降ろして**見張ります（あちらは `day_cap` を差し替えて呼びます）。
    """
    from src import measure_window

    keep = measure_window.DISABLE_DYNAMIC
    measure_window.DISABLE_DYNAMIC = True
    yield
    measure_window.DISABLE_DYNAMIC = keep
