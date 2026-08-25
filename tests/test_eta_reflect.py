"""`scripts/eta.py --reflect` —— **その回で動いた入力を、その回のうちに予測へ入れ直す。**

## この検査が守っているもの（2026-08-20・オーナー指示。原文は1行）

> 毎回の実行で予測するように言ったはずなので、毎回その予測に反映して

**予測を「出す」ことは、既に毎回やっています**（`scripts/eta.py` が周の1行目）。
言われているのは**反映**のほうです。8/20 の実例:

    歩留り 1.0→0.156 ／ 供給 21日→4日 ／ A/B の在庫の数え方 ／
    掃引の候補数 ／ `retention` の6本

**どれも、その回の予測に入っていません。** 逆に、入れてはいけないもの
（`density_month 25.0`）が別の欄から戻って**予測を3分の1にしました。**

だから固定するのは、次の4つです。

1. **反映が「前 → 後（±N日）」を機械が読める形で残すこと**（`data/eta.jsonl`）
2. **反映の行を、予測の点として数えないこと**
   （数えると `growth_per_day` の回帰に「中身が同じで時刻だけ違う点」が入り、
   `_drift` の「前の回」が**同じ回の自分自身**になる）
3. **動いた入力が1つも無い回を、「効いていない」と言わないこと**
   （Analytics は日次で3日遅れ。`_drift` に同じ趣旨の断りが既にあります）
4. **`run_marker.py --ship` が、既定で反映を呼ぶこと**
   —— 註に書くだけでは素通りします（8/20 に書いたものは全部素通りしました）
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_reflect_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


# **軌跡が解けた回**の目印。`None` を渡すと `reflect()` は軌跡の欄を落とします
# （出発点の日付が「後」として残り、差が黙って +0日 になるのを防ぐため）。
_TR = {"base": {}, "choice": [], "arms": {}}


def _point(**over):
    """`data/eta.jsonl` の点1つ（実測は 2026-08-20 のもの）。"""
    base = dict(
        at="2026-08-20T11:15:07+00:00",
        subs_net=9, views_all=27777, views_7d=8802, views_28d=20303, views_90d=22534,
        subs_gained_28d=9, subs_gained_90d=11, long_hours_365=0.1,
        shorts_views_90d=22515, views_per_video=923, median_views_per_video=1041,
        videos_with_views_28d=22, long_per_video=2.0, long_median_per_video=2,
        long_videos_28d=5, long_views_28d=11,
        traj_date="2026-11-29", traj_days=100.4,
        target_date="2027-01-24", days_to_target=156.9,
        density_month=4.0, make_rate_per_day=4.1,
        binding="収益化の門＋その後の30日", lever_hint="sub_rate",
    )
    base.update(over)
    return base


@pytest.fixture
def log(tmp_path, monkeypatch):
    p = tmp_path / "eta.jsonl"
    monkeypatch.setattr(eta, "LOG", p)
    return p


def _write(log, *rows):
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")


def _rows(log):
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------------------
# 1. 前後差が、機械の読める形で残る
# ---------------------------------------------------------------------------

def test_reflect_records_the_date_before_and_after(log, monkeypatch):
    """**「この回で入れた実測 → 日付 ○ → △（±N日）」が1行で読めること。**"""
    _write(log, _point())

    def fake_solve(m, points):
        row = dict(m)
        row.update(traj_date="2026-11-14", traj_days=85.4,
                   target_date="2027-01-09", days_to_target=141.9,
                   make_rate_per_day=9.0)      # ← この回で動いた入力
        return {"a": {}, "sup": None, "pl": {}, "tr": _TR, "row": row}

    monkeypatch.setattr(eta, "solve", fake_solve)
    code, rec = eta.reflect("fix: 供給を測り直した")
    assert code == 0

    assert rec["kind"] == "reflect"
    assert rec["base_at"] == "2026-08-20T11:15:07+00:00"
    assert rec["traj_date_before"] == "2026-11-29"
    assert rec["traj_date"] == "2026-11-14"
    # **負なら早まった**（`run_marker.py --moves` と同じ向き）。
    assert rec["traj_delta_days"] == -15
    assert rec["target_delta_days"] == -15
    assert rec["no_movable_input"] is False
    assert rec["moved"]["make_rate_per_day"] == [4.1, 9.0]
    assert rec["note"] == "fix: 供給を測り直した"

    # **積まれること。** 日誌の散文ではなく、ここが正本です。
    written = _rows(log)[-1]
    assert written["kind"] == "reflect" and written["traj_delta_days"] == -15


def test_moved_does_not_list_the_date_itself(log, monkeypatch):
    """**日付は「動いた入力」ではなく「結果」です。** 混ぜると入力が動いたように見える。"""
    _write(log, _point())
    monkeypatch.setattr(eta, "solve", lambda m, points: {
        "a": {}, "sup": None, "pl": {}, "tr": _TR,
        "row": {**m, "traj_date": "2026-11-14", "make_rate_per_day": 9.0}})
    _, rec = eta.reflect()
    assert "traj_date" not in rec["moved"]
    assert "make_rate_per_day" in rec["moved"]


# ---------------------------------------------------------------------------
# 2. 反映の行を、予測の点として数えない
# ---------------------------------------------------------------------------

def test_reflect_rows_are_not_counted_as_prediction_points(log):
    """数えると `growth_per_day` の回帰と `_drift` の「前の回」が壊れます。"""
    _write(log,
           _point(at="2026-08-20T10:00:00+00:00"),
           {"at": "2026-08-20T10:30:00+00:00", "kind": "reflect",
            "traj_date": "2026-11-14", "traj_delta_days": -15},
           _point(at="2026-08-20T11:15:07+00:00"))
    pts = eta._points()
    assert len(pts) == 2
    assert all(p.get("kind") != "reflect" for p in pts)
    # 読みたいときは読める（反映そのものを数える側のため）。
    assert len(eta._points(reflect=True)) == 3


def test_reflect_compares_against_the_prediction_not_another_reflect(log, monkeypatch):
    """**出発点は「この回の予測」です。** 直前の反映を基準にすると差が0になります。"""
    _write(log,
           _point(),
           {"at": "2026-08-20T11:20:00+00:00", "kind": "reflect",
            "traj_date": "2026-11-14", "traj_days": 85.4})
    monkeypatch.setattr(eta, "solve", lambda m, points: {
        "a": {}, "sup": None, "pl": {}, "tr": _TR,
        "row": {**m, "traj_date": "2026-11-14"}})
    _, rec = eta.reflect()
    assert rec["base_at"] == "2026-08-20T11:15:07+00:00"
    assert rec["traj_delta_days"] == -15


# ---------------------------------------------------------------------------
# 3. 「動かせる入力が無かった」を「効いていない」と言わない
# ---------------------------------------------------------------------------

def test_no_movable_input_is_not_called_ineffective(log, monkeypatch, capsys):
    """`_drift` と同じ断り。**混同すると、読む側が日付を動かす作業から離れます。**"""
    _write(log, _point())
    monkeypatch.setattr(eta, "solve", lambda m, points: {
        "a": {}, "sup": None, "pl": {}, "tr": _TR, "row": dict(m)})
    _, rec = eta.reflect()
    assert rec["no_movable_input"] is True
    assert rec["moved"] == {}
    assert rec["traj_delta_days"] == 0
    out = capsys.readouterr().out
    assert "動かせる入力" in out
    assert "「効いていない」ではありません" in out
    assert "効いていません" not in out.replace("「効いていない」ではありません", "")


def test_input_moved_but_date_did_not_says_it_is_outside_the_binding(log, monkeypatch, capsys):
    """入力が動いて日付が動かないのは、**いまの律速の外**という情報です。"""
    _write(log, _point())
    monkeypatch.setattr(eta, "solve", lambda m, points: {
        "a": {}, "sup": None, "pl": {}, "tr": _TR,
        "row": {**m, "make_rate_per_day": 9.0}})
    _, rec = eta.reflect()
    assert rec["no_movable_input"] is False and rec["traj_delta_days"] == 0
    assert "律速の外" in capsys.readouterr().out


def test_reflect_never_stops_the_cycle(log, monkeypatch, capsys):
    """**反映は記録であって門ではありません。** 解けなくても 0 を返すこと。"""
    _write(log, _point())

    def boom(m, points):
        raise RuntimeError("解けない")

    monkeypatch.setattr(eta, "solve", boom)
    code, rec = eta.reflect()
    assert code == 0 and rec == {}
    assert "回は止めないこと" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 4. **飛ばせない形になっているか**（註に書くだけにしない）
# ---------------------------------------------------------------------------

def test_ship_calls_reflect_by_default():
    """`run_marker.py --ship` が既定で反映を呼ぶこと。**この周で唯一飛ばせない呼び出し。**"""
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert "def _reflect_now(" in src
    assert "_reflect_now(what)" in src
    assert '"--reflect"' in src
    # 逃げ道はあるが、**既定ではない**
    assert '"--no-reflect"' in src
    assert "reflect: bool = True" in src


def test_stop_check_asks_when_shipped_without_reflecting():
    """`--no-reflect` を使った回・反映が落ちた回を、終わる前に引き止めること。"""
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert 'REFLECTED=' in src
    assert '"$SHIP_STATE" = "shipped" ] && [ "$REFLECTED" = "no" ]' in src
    assert "eta.py --reflect" in src


def test_the_procedure_says_it_where_it_cannot_be_skipped():
    """**手順書に組み込むこと**（註に書くだけにしない。8/20 の註は全部素通りしました）。"""
    doc = (ROOT / "docs" / "trigger_main.md").read_text(encoding="utf-8")
    assert "--reflect" in doc
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "--reflect" in claude


def test_unsolved_trajectory_is_not_read_as_zero(log, monkeypatch, capsys):
    """**「動かなかった」と「測れなかった」を同じ字にしないこと。**

    `_row()` は軌跡が解けないと軌跡の欄を書きません。反映は**出発点の行そのもの**を
    `m` として渡すので、書かれなければ出発点の日付がそのまま残り、
    **差が黙って +0日**になります。いちばん悪い形なので、ここで落とします。
    """
    _write(log, _point())
    monkeypatch.setattr(eta, "solve", lambda m, points: {
        "a": {}, "sup": None, "pl": {}, "tr": None, "row": dict(m)})
    _, rec = eta.reflect()
    assert rec["traj_solved"] is False
    assert rec["traj_date"] is None and rec["traj_delta_days"] is None
    assert "軌跡を解けませんでした" in capsys.readouterr().out


def test_the_next_cycle_actually_sees_the_reflection(log):
    """**残す所と読む所の、両方が要ります。**

    `retention.py` は 8/10〜8/20 のあいだ正しく印字していました。
    **3本は 8/18 に出て、誰も気づきませんでした** —— 印字は、その道具を走らせた
    回にしか届かないからです。反映も同じ形にしないこと。
    """
    _write(log,
           _point(),
           {"at": "2026-08-20T12:00:00+00:00", "kind": "reflect",
            "moved": {"make_rate_per_day": [4.1, 9.0]}, "no_movable_input": False,
            "traj_delta_days": -15, "note": "fix: 供給を測り直した"},
           {"at": "2026-08-20T13:00:00+00:00", "kind": "reflect",
            "moved": {}, "no_movable_input": True, "traj_delta_days": 0,
            "note": "fix: 手順の配線"})
    out = "\n".join(eta._reflect_recap())
    assert "make_rate_per_day" in out and "-15日" in out
    assert "動かせる入力なし" in out and "「効いていない」ではありません" in out
    assert "入れ直した回: 2回 / うち入力が動いたのは 1回" in out


def test_recap_is_empty_before_anything_was_reflected(log):
    _write(log, _point())
    assert eta._reflect_recap() == []


def test_ship_from_the_tests_does_not_write_to_the_real_ledger():
    """**入れた当日に踏みました。**

    `tests/test_closes_vocab.py` は `run_marker.ship()` を**直接**呼びます。
    反映を既定にした瞬間、その検査が**本物の `data/eta.jsonl` に 19行**書きました
    （1回 3.3秒 × 19）。`tests/conftest.py` は `src/alerts.py` の台帳で
    同じ形を 2026-08-17 に踏んで塞いでいます —— **同じ傘に入れること。**
    """
    import os
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert 'SKIP_REFLECT_ENV = "YT_SKIP_REFLECT"' in src
    assert "os.environ.get(SKIP_REFLECT_ENV)" in src
    conf = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert 'os.environ["YT_SKIP_REFLECT"]' in conf
    # **いま実際に立っていること**（conftest が効いていなければ、ここで落ちます）
    assert os.environ.get("YT_SKIP_REFLECT")
