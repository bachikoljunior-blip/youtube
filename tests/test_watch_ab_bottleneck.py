"""**A/B の待ちが「あと N本」と言うとき、本当に足りないのが本かどうか。**

2026-08-27 の実測（`status.py` の待ちの節）:

    あと **16本**  題の問い-両群16本（いま 0 / 要る 16）  問い 0本 / 断定 0本

**これは「16本 作れ」と読めます。** 同じ日に `judgeable.members("title_form")` を
数えると、群には **問い 56本 / 断定 65本** が既に居ました。**1本も要りません** ——
足りないのは公開からの齢（`SETTLE_DAYS + ANALYTICS_LAG_DAYS`）だけで、
床に届くのは 2026-09-05 です。

同じ日の 6件のうち **4件** がこの形（`title_form` / `hook_form` /
`stat_split` / `opening_motion`）で、本当に本が足りないのは
`slide_pace` と `request_form` の 2件だけでした。

**なぜ目標に効くか。** 同じ回の `scripts/eta.py` は腕 `density` の天井を **×1.00**
（＝「本数を増やしても在庫を増やしても、日付は動きません」）と印字しています。
目盛りを字面どおり読んだ回は、**1日も早まらない側**へ丸ごと持っていかれます。
そして「あと何日か」は印字されないので、**いつ判定できるようになるか**が
どこにも出ません（`status.py` の「直近20回の verdict: 0件」）。

**この形は一度、1件だけ直されています** —— `config/hypotheses.yaml` の
`opening_motion` の註（2026-08-26）「**本数は足りていて、縛っているのは日付でした**」。
**直したのはその前提の期限だけで、そう読ませている目盛りは直っていませんでした。**
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ab_split, judgeable, watches  # noqa: E402

LAG = ab_split.SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS


def test_本が足りているときは本数を足せと言わない():
    """群が床に届いていたら、note は「齢待ち」と日付を言うこと。"""
    today = date(2026, 8, 27)
    # 床 3本。群には 5本ずつ居るが、公開はこれから（＝齢が足りないだけ）
    groups = {
        "問い": [today + timedelta(days=i) for i in range(1, 6)],
        "断定": [today + timedelta(days=i) for i in range(1, 6)],
    }
    note = watches._ab_bottleneck(groups, 3, today, LAG)
    assert "本が足りません" not in note, note
    assert "足りないのは本ではありません" in note, note
    # 3本目は 08/30 公開 → 落ち着くのは +LAG 日
    settles = today + timedelta(days=3) + timedelta(days=LAG)
    assert str(settles) in note, note
    assert "あと " in note and "日" in note, note


def test_本が足りないときは何本足りないかを言う():
    today = date(2026, 8, 27)
    groups = {"速い": [today + timedelta(days=1)] * 5,
              "遅い": [today + timedelta(days=1)] * 3}
    note = watches._ab_bottleneck(groups, 16, today, LAG)
    assert "本が足りません" in note, note
    assert "速い 11本" in note and "遅い 13本" in note, note
    assert "齢待ち" not in note, note


def test_片方だけ足りないなら本の側に倒す():
    """**両群そろって初めて判定できる**ので、1群でも足りなければ本の話。"""
    today = date(2026, 8, 27)
    groups = {"処置": [today + timedelta(days=1)] * 20,
              "対照": [today + timedelta(days=1)] * 2}
    note = watches._ab_bottleneck(groups, 8, today, LAG)
    assert "本が足りません" in note, note
    assert "対照 6本" in note, note


def test_実物のどの群でもどちらかを必ず名指しする():
    """**裸の「あと N本」を出さないこと。**

    `Gauge.left` は必ず本数で出るので、note の側が「本か齢か」を言わないと
    画面には「N本 作れ」としか読めない行が残ります。
    """
    for name in judgeable.MEMBER_SOURCES:
        g = watches._k_ab_group({"experiment": name})
        if g.err or g.met:
            continue
        assert ("本が足りません" in g.note) or ("齢待ち" in g.note), (
            f"{name}: 足りないのが本か齢か、note が言っていません: {g.note!r}"
        )


def test_床が満ちていたら余計なことを言わない():
    today = date(2026, 8, 27)
    old = today - timedelta(days=LAG + 5)
    groups = {"A": [old] * 5, "B": [old] * 5}
    note = watches._ab_bottleneck(groups, 3, today, LAG)
    assert "本が足りません" not in note and "齢待ち" not in note, note
