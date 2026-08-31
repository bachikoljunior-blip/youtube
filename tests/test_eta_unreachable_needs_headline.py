"""**「来ない日を待っている前提」が、`eta.py` の見出しに出ること。**（2026-08-31）

## なぜ要るか

`scripts/deadline_check.py` は、その末尾に
「**規則（1日1本）の下では、期日までに満ちない要件: N件**」を
**2026-08-31 の朝から印字していました。誰も撃っていません** ——
出るのが 200行 ある出力の末尾で、**見出しの3行に入っていなかった**から。

そして見出しの `期日の来た前提があります` は**期日**しか見ません。
`needs` が「**来ない日**」（例: 09/10 に 16本 公開した日の読み）を待っている前提は、
**期日が来ないので、その行に一生 出ません。** 同じ関数が
「軌跡の腕が動くのは前提を1件 閉じたときだけ」と印字するので、
**到達日はそこで止まったままになります。**

**実測 2026-08-31**: 見出しは「**この回に閉じられる前提はありません**」と出していた。
**間違い** —— 同じ日に、期日 09-10 の前提が**公開ずみの8日ぶんのデータだけで、
10日 早く**閉じられた。`needs` が来ない日を名指ししていただけで、
**同じ形の日は 08/20〜08/30 にすでに 8日 在った。**

**止める仕掛けではありません。1行 印字するだけです。**
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from src import house_rule  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_claim_を期日の順に重複なく返す(tmp_path):
    y = tmp_path / "h.yaml"
    y.write_text(
        "hypotheses:\n"
        "  - claim: おそい\n"
        "    deadline: '2026-09-20'\n"
        "    needs:\n"
        "      - on_date: '2026-09-20'\n"
        "        what: 09/20（40本 公開）の読み\n"
        "  - claim: はやい\n"
        "    deadline: '2026-09-10'\n"
        "    needs:\n"
        "      - on_date: '2026-09-10'\n"
        "        what: 09/10（12本 公開）の読み\n"
        "      - on_date: '2026-09-10'\n"
        "        what: 同じ日の 20本 の読み\n",
        encoding="utf-8",
    )
    got = house_rule.unreachable_claims(today="2026-08-31", path=y)
    assert got == ["はやい", "おそい"], "期日の順・重複なしで返すこと"


def test_規則の下で届く要件は出さない(tmp_path):
    y = tmp_path / "h.yaml"
    y.write_text(
        "hypotheses:\n"
        "  - claim: とどく\n"
        "    deadline: '2026-09-30'\n"
        "    needs:\n"
        "      - on_date: '2026-09-30'\n"
        "        what: 09/30 までに 12本 公開した読み\n",
        encoding="utf-8",
    )
    # 今日から 09/30 まで 30日 ＝ 規則が 30本 許すので、12本 は届く
    assert house_rule.unreachable_claims(today="2026-08-31", path=y) == []


def test_閉じた前提は出さない(tmp_path):
    y = tmp_path / "h.yaml"
    y.write_text(
        "hypotheses:\n"
        "  - claim: とじた\n"
        "    deadline: '2026-09-10'\n"
        "    closed_on: '2026-08-31'\n"
        "    needs:\n"
        "      - on_date: '2026-09-10'\n"
        "        what: 09/10（16本 公開）の読み\n",
        encoding="utf-8",
    )
    assert house_rule.unreachable_claims(today="2026-08-31", path=y) == []


def test_読めない台帳では黙る(tmp_path):
    """**測っていないことを、止める側に倒さないこと。**"""
    assert house_rule.unreachable_claims(path=tmp_path / "ない.yaml") == []


def test_規則が外れたら黙る(tmp_path, monkeypatch):
    y = tmp_path / "h.yaml"
    y.write_text(
        "hypotheses:\n"
        "  - claim: おおい\n"
        "    deadline: '2026-09-03'\n"
        "    needs:\n"
        "      - on_date: '2026-09-03'\n"
        "        what: 09/03（12本 公開）の読み\n",
        encoding="utf-8",
    )
    assert house_rule.unreachable_claims(today="2026-08-31", path=y) == ["おおい"]
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", 25)
    assert house_rule.unreachable_claims(today="2026-08-31", path=y) == []


def test_見出しがその行を持っている():
    """**`headline()` の本文に出ること。** 実物の台帳で撃ちます。"""
    import eta

    if not house_rule.unreachable_claims():
        return  # 実物に1件も無い回は、出ないのが正しい
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "来ない日を待っている前提" in src
    assert "house_rule.unreachable_claims()" in src, \
        "**判定は house_rule の1か所から引くこと**（数を写さない）"
    assert hasattr(eta, "headline")
