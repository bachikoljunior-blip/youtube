"""**証拠が、結論とは別の問いを測っていた**（2026-08-29・最適化の回）。

`scripts/queue_lag.answering_lines()` は毎周こう印字していました:

    **これから作るショートは、足りない群に自動で入ります**（直近の実測 **87%**）

**その 87% は `judgeable.short_share()`** ＝「直近30日に作った本のうち、
**ショートだった**割合」です。**文と数が別のことを言っています** ——
片方は「群に入るか」、もう片方は「ショートか長尺か」。

実測 2026-08-29 —— 同じ日に3つの数が出ます:

    87%   `short_share()`          作った本のうち ショートだった割合  ← 印字していた数
    13%   直近30日のショートのうち、いま足りない群に入っているもの
    100%  **実験が入った後**に作ったショートのうち、群に入ったもの  ← 文が言っている数

**13% は不当に低い**（30日の窓のうち 28日ぶんは実験が入る前に作った本で、
`_members_by_request_form()` の `built < exp.landed` で**必ず**落ちます）。
**87% は無関係。** 文が言っているのは3つ目で、それは **100%** です
（`request_form` 58/58本・`slide_pace` 24/24本）。

**結論は正しく、証拠のほうが弱かった**わけです ——
そして弱い数を並べたせいで、**「87% しか入らない」と読める**形でした。
`queue_lag` のこの節は「**答えは『作るのをやめる』ではなく『作り続ける』**」を
言うためのもので、**符号が逆に読まれると、いちばん高くつきます。**

## この検査が守っているもの

1. **分母は「実験が入った後に作ったショート」だけ**（前の本を混ぜない）
2. 標本 8本 未満では**言わない**（引きの偏りで反対を言うので）
3. `queue_lag` がこの数を**ショート率と取り違えない**

## 覆る条件

振り分けが「テーマIDだけを見る純関数」でなくなったら 100% は割れます
（`src/script_writer.request_form` / `src/pipeline.slide_pace`）——
そのときはこの関数がそのまま下がって教えます。**写さず、毎回 撃つこと。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import judgeable as SJ  # noqa: E402

JST = timezone(timedelta(hours=9))
LANDED = datetime(2026, 8, 26, 19, 8, tzinfo=JST)


class _Exp:
    landed = LANDED


def _stub(monkeypatch, builds: dict, joined: set[str]) -> None:
    from src import ab_split

    monkeypatch.setattr(ab_split, "EXPERIMENTS", {"k": _Exp()}, raising=False)
    monkeypatch.setattr(SJ, "build_times", lambda: builds)
    monkeypatch.setattr(SJ, "_short_topics", lambda: set(builds))
    monkeypatch.setattr(SJ, "_video_by_topic", lambda: {t: f"vid-{t}" for t in builds})
    monkeypatch.setattr(SJ, "members", lambda _k: {"g": [(None, v) for v in joined]})


def test_実験が入る前に作った本を_分母に入れない(monkeypatch):
    """**1: これが 100% を 13% に見せていた原因です。**

    前に作った本は `built < exp.landed` で**必ず**群から落ちるので、
    分母に置くと「入らなかった」に数えられます —— **入りようがない本**です。
    """
    before = {f"old{i}": LANDED - timedelta(days=5) for i in range(20)}
    after = {f"new{i}": LANDED + timedelta(hours=i + 1) for i in range(10)}
    _stub(monkeypatch, {**before, **after},
          joined={f"vid-new{i}" for i in range(10)})

    got = SJ.starved_share(["k"])
    assert got == (10, 10), "実験が入る前の本を分母に入れています"


def test_入った後の本が群から漏れていれば_下がる(monkeypatch):
    """**逆向きも守ること。** 100% は「必ず 100%」の意味ではありません。

    振り分けが純関数でなくなれば、ここがそのまま下がって教えます
    （それがこの関数の存在理由）。
    """
    after = {f"new{i}": LANDED + timedelta(hours=i + 1) for i in range(10)}
    _stub(monkeypatch, after, joined={f"vid-new{i}" for i in range(4)})
    assert SJ.starved_share(["k"]) == (4, 10)


def test_標本が薄い回は_言わない(monkeypatch):
    """**2: 引きの偏りで反対を言うくらいなら、黙ること**（`short_share` と同じ）。"""
    after = {f"new{i}": LANDED + timedelta(hours=i + 1) for i in range(7)}
    _stub(monkeypatch, after, joined={f"vid-new{i}" for i in range(7)})
    assert SJ.starved_share(["k"]) is None


def test_長尺は分母に入らない(monkeypatch):
    """長尺は依頼そのものを書かないので、群に入りようがありません。"""
    after = {f"new{i}": LANDED + timedelta(hours=i + 1) for i in range(12)}
    _stub(monkeypatch, after, joined={f"vid-new{i}" for i in range(12)})
    # 4本 を「ショートではない」に倒す
    monkeypatch.setattr(SJ, "_short_topics", lambda: {f"new{i}" for i in range(8)})
    assert SJ.starved_share(["k"]) == (8, 8)


def test_queue_lag_は_ショート率と取り違えない():
    """**3: 印字の側の見張り。**

    `answering_lines()` の「足りない群に自動で入ります」に添える数は
    `_starved_share()` であって、**`_short_share()` ではありません。**
    """
    src = (ROOT / "scripts" / "queue_lag.py").read_text(encoding="utf-8")
    i = src.index("足りない群に自動で入ります")
    head = src[max(0, i - 1200):i]
    assert "_starved_share(" in head
    # **ショート率のほうを、この文の証拠に戻さないこと**
    assert "pct = f\"（直近の実測 {share[0]" not in src
