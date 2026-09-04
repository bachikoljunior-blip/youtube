"""**台帳がまだ厚い間、`premise` の回に枠を使わせない門**（2026-09-05・最適化の回）。

なぜ要るか（`python scripts/optimized.py` を撃って出た実測・`data/runs.jsonl`
直近5日 **241 ship**）:

    fix 149 → 門1' が動いた回 0 ／ improve 48 → 0 ／ **premise 25 → 0** ／
    verdict 7 → 0 ／ upload 6 → 0 ／ means 6 → 0
    **測れた 23件・近づいた 0件・合計 +0.0日**

同じ5日で `data/eta.jsonl` の **再生/日(7d) は 6,299 → 943（−85%）**。

`premise` が 0 なのは運ではなく**定義**です —— `scripts/eta.py` の頭が毎周
「腕が動くのは前提を1件 **閉じた** ときだけ」と印字します。それでも
`docs/GOAL.md` は `premise` を「0単位・いつでも撃てる」と書き、`fix` の門は
自分で「`premise` は通ります」と逃げ道に名指ししていました。

ここが押さえるのは4つだけ:

1. 台帳が `premise_lead_days()` より厚く、腕に開いている前提が在るとき、門が閉じること。
2. **覆る条件1** —— 台帳が薄くなったら、門が**自分で**開くこと（定数を持たない）。
3. **禁止ではないこと** —— 開いている前提が 0件 の腕は通ること。
4. **読めない台帳で回を止めないこと** —— 読めなければ通すこと。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker  # noqa: E402


def _install_yaml(monkeypatch, tmp_path: Path, rows: list[dict]) -> None:
    """`ledger_days()` が読む台帳を、この検査のものに差し替える。"""
    import yaml
    p = tmp_path / "hypotheses.yaml"
    p.write_text(yaml.safe_dump({"hypotheses": rows}, allow_unicode=True),
                 encoding="utf-8")
    real = Path.read_text

    def fake(self, *a, **k):
        if self.name == "hypotheses.yaml":
            return real(p, *a, **k)
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake)


# --- `ledger_days()` そのもの ---------------------------------------------

def test_ledger_days_counts_live_fuel_and_close_rate(monkeypatch, tmp_path):
    """生きた燃料 ÷ 閉じる速さ ＝ 残り日数。**腕の無い前提は燃料に数えない。**"""
    _install_yaml(monkeypatch, tmp_path, [
        {"claim": "a", "lever": "per_video"},
        {"claim": "b", "lever": "per_video"},
        {"claim": "c", "lever": "sub_rate"},
        {"claim": "d", "lever": "none"},          # 腕なし＝燃料ではない
        {"claim": "e", "lever": "rpm", "closed_on": "2026-09-03", "verdict": True},
        {"claim": "f", "lever": "rpm", "closed_on": "2026-09-02", "verdict": False},
    ])
    r = run_marker.ledger_days(as_of=date(2026, 9, 5), window=7)
    assert r["open"] == 4          # 閉じた2件は外れる
    assert r["live"] == 3          # `none` は燃料に数えない
    assert r["closed_recent"] == 2
    assert r["rate"] == pytest.approx(2 / 7)
    assert r["days"] == pytest.approx(3 / (2 / 7))
    assert r["by_lever"]["per_video"] == 2


def test_verdict_false_counts_as_closed(monkeypatch, tmp_path):
    """**`verdict: false` は「外れた＝閉じた」**（鍵の有無で見ること）。

    値の真偽で見ると、**いちばん価値のある判定**を未判定に数えます
    （`scripts/drift.overdue()` が 2026-08-24 に踏んだのと同じ穴）。
    """
    _install_yaml(monkeypatch, tmp_path, [
        {"claim": "a", "lever": "per_video", "verdict": False},
        {"claim": "b", "lever": "per_video"},
    ])
    assert run_marker.ledger_days(as_of=date(2026, 9, 5))["open"] == 1


def test_unreadable_ledger_returns_empty(monkeypatch):
    """**読めない道具で回を止めないこと** —— 読めなければ空（＝門は開く）。"""
    def boom(self, *a, **k):
        raise OSError("no")
    monkeypatch.setattr(Path, "read_text", boom)
    assert run_marker.ledger_days() == {}


def test_lead_days_is_settle_plus_lag():
    """きょう立てた前提が熟すまで ＝ 落ち着き ＋ 実データの遅れ（どちらも実測）。"""
    from src import judgeable
    assert run_marker.premise_lead_days() == (
        int(judgeable.SETTLE_DAYS) + int(judgeable.ANALYTICS_LAG_DAYS))


# --- 門そのもの（`main()` を通す） -----------------------------------------

@pytest.fixture()
def _ship_stub(monkeypatch):
    """`ship()` を止める（この検査は控えに書きません）。前の門も開けておく。"""
    monkeypatch.setattr(run_marker, "ship", lambda *a, **k: 0)
    monkeypatch.setattr(run_marker, "premise_opened_today",
                        lambda: {"today": 1, "cover": 1.0, "total": 1, "dated": 1})
    monkeypatch.setattr(run_marker, "note_premise_gate", lambda *a, **k: None)


def _argv(lever: str = "per_video") -> list[str]:
    return ["--ship", "premise: 天井を疑う1件（0件）", "--kind", "premise",
            "--lever", lever, "--moves", "0"]


def _fake_ledger(monkeypatch, days, by_lever):
    monkeypatch.setattr(run_marker, "ledger_days", lambda *a, **k: {
        "open": sum(by_lever.values()), "live": sum(by_lever.values()),
        "closed_recent": 14, "rate": 2.0, "window": 7,
        "days": days, "by_lever": by_lever})


def test_thick_ledger_closes_the_gate(monkeypatch, capsys, _ship_stub):
    """**1.** 台帳が厚く、腕に前提が在る → 通らない。"""
    _fake_ledger(monkeypatch, 17.0, {"per_video": 20})
    with pytest.raises(SystemExit):
        run_marker.main(_argv())
    err = capsys.readouterr().err
    assert "台帳には、まだ" in err
    assert "17.0日ぶん" in err
    # **行き先を必ず名指しすること**（門が自分の出口を塞がないこと）
    assert "verdict" in err


def test_thin_ledger_opens_the_gate_by_itself(monkeypatch, _ship_stub):
    """**2. 覆る条件1** —— 残りが `premise_lead_days()` を切ったら自分で開く。"""
    _fake_ledger(monkeypatch, float(run_marker.premise_lead_days()) - 0.5,
                 {"per_video": 20})
    assert run_marker.main(_argv()) == 0


def test_uncovered_arm_passes(monkeypatch, _ship_stub):
    """**3. 禁止ではない** —— 開いている前提が 0件 の腕は通る。"""
    _fake_ledger(monkeypatch, 17.0, {"per_video": 20})
    assert run_marker.main(_argv(lever="rpm")) == 0


def test_unmeasured_ledger_passes(monkeypatch, _ship_stub):
    """**4.** 測れなかった（`days is None`）ときは通す。"""
    _fake_ledger(monkeypatch, None, {"per_video": 20})
    assert run_marker.main(_argv()) == 0


def test_other_kinds_are_not_blocked(monkeypatch, _ship_stub):
    """止めているのは `premise` だけ（`improve` は素通り）。"""
    _fake_ledger(monkeypatch, 17.0, {"per_video": 20})
    assert run_marker.main(
        ["--ship", "improve: 09/05 の枠の本を1か所 直した（1件）",
         "--kind", "improve", "--lever", "per_video", "--moves", "0"]) == 0


# --- 2つの門が同じことを言うこと ------------------------------------------

def test_dry_ledger_menu_does_not_offer_a_hand_that_is_closed(monkeypatch):
    """**通らない手を「通る手」に並べないこと**（`_premise_hand_line()` の註）。

    `dry_ledger_gate()` の止めの文は `premise` を通る手に名指ししていました。
    同じ回に足した台帳の門は、台帳が厚い間 `premise` を通しません ——
    **案内どおり撃った回が、次の門でもう1回 止められます。**
    """
    monkeypatch.setattr(run_marker, "ledger_days", lambda *a, **k: {
        "days": 17.0, "live": 34, "rate": 2.0, "closed_recent": 14,
        "window": 7, "open": 36, "by_lever": {"per_video": 20}})
    line = run_marker._premise_hand_line()
    assert "いま通りません" in line
    assert "--kind premise  『" not in line

    # **薄くなったら、案内も戻ること**（片方だけ残さない）。
    monkeypatch.setattr(run_marker, "ledger_days", lambda *a, **k: {
        "days": 1.0, "live": 2, "rate": 2.0, "closed_recent": 14,
        "window": 7, "open": 4, "by_lever": {"per_video": 2}})
    assert "--kind premise" in run_marker._premise_hand_line()
    assert "いま通りません" not in run_marker._premise_hand_line()


def test_premise_hand_line_survives_an_unreadable_ledger(monkeypatch):
    """読めなければ、案内は元の（通る手として並べる）側に戻ること。"""
    def boom(*a, **k):
        raise OSError("no")
    monkeypatch.setattr(run_marker, "ledger_days", boom)
    assert "--kind premise" in run_marker._premise_hand_line()
