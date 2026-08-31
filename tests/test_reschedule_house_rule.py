"""**`reschedule.py` は、規則より多く1日に置かない。**（2026-08-31 に踏んだ）

## 何が起きていたか

オーナー原文（**一字も変えないこと**）:

> **「動画は1日一本作り置きはなしにして。次の投稿予定までにそこで投稿する動画を
>    改善し続ける。それは固定にして。その上で目標を目指す」**

規則は `src/house_rule.PUBLISH_PER_DAY = 1` に入り、`batch_build`（作る側）と
`eta`（読む側）はそこを読むようになりました。**`reschedule.py`（置く側）だけが
残っていました。**

`_measured_per_day()` は `day_cap.measure()`（＝ **1日に何本まで再生が付くか**という
**観測**・実測 10本/日）をそのまま返し、`--compact` / `--spread` は
**1日10本 詰める割り当て**を組みます。

そして `scripts/status.py` は、同じ日にこう鳴らしていました:

    [!] **予約が1本も無い日が 10日あります**（＝その日は投稿が途切れます）
        …そうでなければ **`python scripts/reschedule.py --compact`** で詰めること

**規則が入った直後に、道具のほうがそれを元へ戻す案内を出していた**ことになります。
この repo でいちばん多い壊れ方 ——「**言っている所と、している所が別**」そのものです。

## この検査が固定するもの

    1. 既定の本数（`_measured_per_day`）が、**規則を超えないこと**
    2. **`--per-day` を明示で渡した回も**締まること
       （既定だけ締めて口を開けると、「今日は詰めたいから」で毎回そこを通ります）
    3. **観測そのものは消していないこと** —— 規則が緩めば観測の側が戻ること
    4. **0本/日 にしないこと**（規則が 0 でも 1 が床。置けなくなると投稿が止まる）

**戻すには、この file を消すしかありません**（diff に出ます）。

**覆る条件**: オーナーが規則を外したとき。**数をべた書きしていないので、
この file は自動で追随します。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("reschedule_rule_mod",
                                               ROOT / "scripts" / "reschedule.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

from src import house_rule  # noqa: E402


def test_既定の本数が規則を超えない():
    """**これが本体です。** `--compact` の既定が 1日10本 に戻ったら落とすこと。"""
    got = rs._measured_per_day()
    assert got <= house_rule.PUBLISH_PER_DAY, (
        f"1日 {got}本 で割り当てを組もうとしています。"
        f"規則は {house_rule.PUBLISH_PER_DAY}本/日 です（`src/house_rule.py`）")


def test_観測が大きくても規則で締まる():
    assert rs._clamp_per_day(92) <= house_rule.PUBLISH_PER_DAY
    assert rs._clamp_per_day(10) <= house_rule.PUBLISH_PER_DAY


def test_規則が緩めば観測の側が戻る(monkeypatch):
    """**観測を消していないこと。** 規則は上限であって、置き換えではありません。"""
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", 25)
    assert rs._clamp_per_day(10) == 10, "規則が緩んでも観測が戻っていません"
    assert rs._clamp_per_day(92) == 25, "規則が上限として効いていません"


def test_0本日にはしない(monkeypatch):
    """**置けなくなると投稿が止まります**（`CLAUDE.md`「途切れさせないこと」）。"""
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", 0)
    assert rs._clamp_per_day(10) == 1
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", -3)
    assert rs._clamp_per_day(10) == 1


def test_明示のper_dayも締まる(capsys):
    """**既定だけ締めて口を開けないこと。**

    `--per-day 10` が素通りするなら、「今日は詰めたいから」で毎回そこを通ります
    （`batch_build` の `--count` を規則で締めたのと同じ理由）。
    """
    args = rs.build_parser().parse_args(["--list", "--per-day", "10"])
    assert args.per_day == 10, "解析の時点では、渡された数がそのまま入ること"
    assert rs._clamp_per_day(args.per_day) <= house_rule.PUBLISH_PER_DAY


def test_規則の出どころは1か所():
    """**写しを持たないこと。** `reschedule.py` に数を直書きしないこと。"""
    body = (ROOT / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    assert "house_rule" in body, (
        "`reschedule.py` が `src/house_rule` を読んでいません（写しを持つと必ずずれます）")
