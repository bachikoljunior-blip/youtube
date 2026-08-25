"""`src/levers.py` と `run_marker.py --lever` の検査 —— **腕の宣言**。

## なぜ先にここを固定するのか

これは**測定の器**です（オーナー指示 2026-08-19 21:2x「毎回達成までの予測して…
それを早めるための行動考えてから進めるのは毎回の最初にやること」）。

壊れ方が3つあり、**どれも出力を見ても分かりません**:

- **`--lever` を書かなくても通る** … 宣言が虫食いになり、「10回のうち何回」が数えられない
- **語彙が `eta.py` と食い違う** … 選んだ腕を何倍にすればいいかが、どこにも出ない
- **後から書き足せる** … 何を狙って出したかは、その回にしか分からない

**既知の当たりを1件、先に固定してあります**（`docs/trigger_main.md` §4）——
**「直近10回の ship に、動かす腕が1件も無い」**。この道具が正しければ、
実物の `data/runs.jsonl` に対してそう言うはずです（言わなくなったら、
それは実績が動いた証拠なので、そのときに検査のほうを向け直すこと）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src import levers
from src.config import ROOT


def test_vocabulary_matches_what_eta_prints():
    """**腕は `eta.py` が印字するものと1対1。** 出ない腕は、効いたか誰も測れません。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "1本あたりの再生数" in src and "RPM" in src, "天井の2つが eta から消えています"
    assert "登録率" in src and "公開の密度" in src, "門1の2つが eta から消えています"
    assert set(levers.LEVERS) == {"per_video", "rpm", "density", "sub_rate", "none"}


def test_none_is_a_real_choice():
    """**`none` を塞がないこと。** 塞ぐと嘘の宣言が増え、数えたい比が壊れます。"""
    assert "none" in levers.LEVERS
    assert "none" not in levers.MOVING


def test_ship_without_lever_is_refused():
    """**`--lever` の無い `--ship` は通らないこと。**（宣言の虫食いを作らない）"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_marker.py"), "--ship", "検査用"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "--lever" in r.stderr


def test_unknown_lever_is_refused():
    """**語彙の外は通らないこと。**（`--closes` と違い、こちらは数える対象）"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_marker.py"),
         "--ship", "検査用", "--lever", "なんとなく"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0


def test_tally_counts_undeclared_rows_instead_of_dropping_them(tmp_path: Path):
    """**宣言の無い古い行を 0 にしないこと。**

    落とすと「10回のうち10回が動かす腕」に見えます。**分母は回数のほう**です。
    """
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"kind": "start", "at": "2026-08-19T20:00:00+09:00"},
        {"kind": "ship", "at": "2026-08-19T20:10:00+09:00", "what": "古い回"},
        {"kind": "ship", "at": "2026-08-19T21:10:00+09:00", "what": "新しい回", "lever": "per_video"},
    ]), encoding="utf-8")
    rows = levers.recent(p)
    assert len(rows) == 2, "ship 以外を数えています"
    counts = levers.tally(rows)
    assert counts["未宣言"] == 1 and counts["per_video"] == 1


def test_report_says_zero_when_nothing_moves_the_date(tmp_path: Path):
    """**動かす腕が0件の一覧では、そう言うこと。**（実物がいまその状態です）"""
    p = tmp_path / "runs.jsonl"
    p.write_text(json.dumps({"kind": "ship", "at": "x", "what": "道具", "lever": "none"}) + "\n",
                 encoding="utf-8")
    text = "\n".join(levers.report(p))
    assert "0 / 1" in text
    assert "1回もありません" in text


# --- `--moves`（2026-08-20 08:0x・オーナー指示3回目） -----------------------------
#
# > 「20万達成までのプランを作って達成日時を予測して、
# >   **毎回達成日時を早めることを考えてから進める**ようにして」
#
# **「考えてから進めた」は、外から見えません。** 見えるようにする道は
# 「先に言って、後で突き合わせる」の1つだけです。だから ship に
# **見込みの日数**を書かせ、次の回が実際の差と並べます。


def test_ship_without_moves_is_refused():
    """**見込みの無い `--ship` は通らないこと。**（`--lever` と同じ形で虫食いを作らない）"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_marker.py"),
         "--ship", "検査用", "--lever", "rpm"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "--moves" in r.stderr


def test_moves_alone_is_refused():
    """出したものと対でなければ、後から裏が取れません（`--closes` と同じ扱い）。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_marker.py"), "--moves", "-3"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "--moves" in r.stderr


def test_reconcile_lines_up_declared_against_actual():
    """**宣言と実際を並べること。** 実際は「次の ship が残した予測日との差」。"""
    rows = [  # `recent()` は新しい順に返すので、その向きで渡す
        {"kind": "ship", "at": "2026-08-21T09:00:00+09:00", "lever": "density",
         "moves": -2, "eta_target": "2026-12-13"},
        {"kind": "ship", "at": "2026-08-20T09:00:00+09:00", "lever": "rpm",
         "moves": -10, "eta_target": "2026-12-23"},
    ]
    text = "\n".join(levers.reconcile(rows))
    assert "宣言 -10日" in text
    assert "実際 -10日" in text          # 12-23 → 12-13 で 10日 早まった
    assert "実際 —" in text              # 新しいほうは、まだ次の ship がない


def test_reconcile_marks_a_miss():
    """**外したと分かることが目的です。** 当たり率を上げるための欄ではありません。"""
    rows = [
        {"kind": "ship", "at": "2026-08-21T09:00:00+09:00", "lever": "rpm",
         "moves": 0, "eta_target": "2026-12-30"},
        {"kind": "ship", "at": "2026-08-20T09:00:00+09:00", "lever": "rpm",
         "moves": -30, "eta_target": "2026-12-23"},
    ]
    text = "\n".join(levers.reconcile(rows))
    assert "外した" in text
    assert "言ったより遠のいています" in text


def test_reconcile_is_quiet_before_the_first_declaration():
    rows = [{"kind": "ship", "at": "2026-08-19T09:00:00+09:00", "lever": "none"}]
    text = "\n".join(levers.reconcile(rows))
    assert "まだありません" in text
