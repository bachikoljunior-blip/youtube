"""**帯は、数え上げの誤差だけでは足りない。**

2026-08-27 夜（最適化の回）。`_ans_accrual` の帯は `1/√have` ——
**数え上げの誤差だけ**を見ています。ところが `days = (want - have) / rate` を
動かしているのは **`rate` のほう**で、そちらは公開本数で日ごとに振れます。

実測（前提「長尺の登録率はショートより1桁以上高い」。**`config/hypotheses.yaml`
の註が、自分で履歴を書き残していました**）:

    08-25  あと 80日  → 期限 11-13
    08-25  （同じ日にもう一度）→ 11-09
    08-26  → 11-16                                （+7日）
    08-26  伸び率 7日で 10.57/日（have 74）→ 11-22  （+6日・帯 ±7）
    08-27  伸び率 8日で 13.38/日（have 107）→ 11-02 （**-20日**・帯 ±7）

**伸び率が1日で +27% 動いています。** `1/√107` は 9.7% ＝ ±7日 なので、
毎回「帯の外だ、書き換えろ」と出て、**3日で4回 期限だけが書き換わりました。**
その4回で、前提も、データの来る日も、**1日も動いていません。**

`Verdict.waits` の註は「**帯の中の待ちは数えません**（数えると、推定の
ゆらぎのぶんだけ『縮めること』と言い続け、書き換えても次の回にまた
言われます）」と、**この失敗の形を正確に予言していました。**
足りなかったのは**帯の幅**です。

**この検査が落ちてよいとき**: `count_expr` の伸び率が、日ごとではなく
連続に測れるようになったら（＝控えを日で畳む必要がなくなったら）、
`_rate_scatter` ごと別のものに置き換えてよい。
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc                                    # noqa: E402

KEY = "42"          # `count_expr` がそのまま鍵。検査では固定の式を使う


def _log(tmp_path, rates: list[float]) -> Path:
    p = tmp_path / "deadline_est.jsonl"
    p.write_text("".join(
        json.dumps({"at": f"2026-08-{20 + i:02d}", "key": KEY, "rate": r},
                   ensure_ascii=False) + "\n"
        for i, r in enumerate(rates)), encoding="utf-8")
    return p


def test_1点では散らばりを名乗らない(tmp_path):
    assert dc._rate_scatter(KEY, _log(tmp_path, [10.0])) is None


def test_散らばりと点の数を返す(tmp_path):
    got = dc._rate_scatter(KEY, _log(tmp_path, [10.0, 12.0]))
    assert got is not None
    scatter, n = got
    assert n == 2
    assert scatter == pytest.approx((12.0 - 10.0) / 12.0)      # median は 12.0


def test_伸び率の振れで帯が広がる(tmp_path, monkeypatch):
    """**実測と同じ形**: 10.57 → 13.38（+27%）で、±7日 が ±15日 になる。"""
    # **鍵は `count_expr` そのもの**なので、控えの鍵も同じ文字列にする
    p = tmp_path / "deadline_est.jsonl"
    p.write_text("".join(
        json.dumps({"at": f"2026-08-{26 + i:02d}", "key": "107", "rate": r},
                   ensure_ascii=False) + "\n"
        for i, r in enumerate([10.571429, 13.375])), encoding="utf-8")
    monkeypatch.setattr(dc, "RATE_LOG", p)
    ans = dc._ans_accrual({"kind": "accrual", "count_expr": "107", "need": 1000,
                           "since": "2026-08-19"}, date(2026, 8, 27))
    assert ans.ready is not None
    assert ans.slack >= 15, f"帯が広がっていません: ±{ans.slack}日"
    assert "伸び率の振れ" in ans.why
    assert "下限" in ans.why, "2点 しかないのに「下限」と言っていません"


def test_控えが無ければこれまでどおり(tmp_path, monkeypatch):
    """**書いていない要件は、今までどおり `1/√have` だけ**。"""
    monkeypatch.setattr(dc, "RATE_LOG", tmp_path / "nope.jsonl")
    need = {"kind": "accrual", "count_expr": "107", "need": 1000,
            "since": "2026-08-19"}
    ans = dc._ans_accrual(need, date(2026, 8, 27))
    assert ans.slack == 7 and "伸び率の振れ" not in ans.why


def test_3点以上なら下限と言わない(tmp_path, monkeypatch):
    p = tmp_path / "deadline_est.jsonl"
    p.write_text("".join(
        json.dumps({"at": f"2026-08-{24 + i:02d}", "key": "107", "rate": r},
                   ensure_ascii=False) + "\n"
        for i, r in enumerate([10.5, 13.4, 11.9])), encoding="utf-8")
    monkeypatch.setattr(dc, "RATE_LOG", p)
    ans = dc._ans_accrual({"kind": "accrual", "count_expr": "107", "need": 1000,
                           "since": "2026-08-19"}, date(2026, 8, 27))
    assert "下限" not in ans.why


def test_控えは1鍵1日1行(tmp_path):
    """**同じ日に何度 撃っても増えないこと。**

    増えると、控えは「この機械が何回 撃たれたか」を数えるようになり、
    伸び率の散らばりではなくなります。
    """
    p = tmp_path / "deadline_est.jsonl"
    a = dc.Answer(date(2026, 9, 1), "why", rate=1.5, rate_key="k")
    v = dc.Verdict(claim="c", deadline=date(2026, 9, 1), ready=a.ready, answers=[a])
    assert dc.record_estimates([v], path=p, as_of=date(2026, 8, 27)) == 1
    assert dc.record_estimates([v], path=p, as_of=date(2026, 8, 27)) == 0
    assert dc.record_estimates([v], path=p, as_of=date(2026, 8, 28)) == 1
    assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_伸び率を持たない答えは積まない(tmp_path):
    p = tmp_path / "deadline_est.jsonl"
    a = dc.Answer(date(2026, 9, 1), "why")                     # rate なし
    v = dc.Verdict(claim="c", deadline=None, ready=a.ready, answers=[a])
    assert dc.record_estimates([v], path=p, as_of=date(2026, 8, 27)) == 0
    assert not p.exists()


# ---------------------------------------------------------------------------
# **帯は左右対称ではない**（2026-08-27 夜・最適化の回）
# ---------------------------------------------------------------------------
#
# 遅れから作った日は **＋1／−0** です。`analytics_lag_band()` の実測は
# **3日 が 381観測・4日 が 57・2日 は 0**、そして印字する `ready` は
# **小さいほう（3日）で作っています** —— つまりその日はもう最速。
#
# ±1 として扱うと `slips` が `ready - 1` まで許し、**同じ機械の2か所が
# 同じ数から逆の指示**を出しました（実測・`title_form`）:
#
#     `src/judgeable.py`  16本目 08/31 ＋3＋3 → **09/06 へ延ばすこと**
#     `deadline_check`    判定できるのは 09-06（±1日）→ **書き換えないこと**
#
# **`judgeable` が正しい** —— 遅れが 2日 だった観測が1つも無い以上、
# 09/05 に判定できる目はありません。
#
# **この検査が落ちてよいとき**: `src/settle.analytics_lag_band()` の実測に
# **2日 が現れたら**。そのときは下向きの幅を 0 でなくすこと。


def test_遅れ由来の帯は下へ効かない():
    """`slack_down=0` の答えは、期限が1日でも前なら `slips`。"""
    a = dc.Answer(date(2026, 9, 6), "遅れ由来", slack=1, slack_down=0)
    v = dc.Verdict(claim="c", deadline=date(2026, 9, 5), ready=a.ready, answers=[a])
    assert v.slack == 1, "上向きの幅は残すこと（`waits` はこちらを見ます）"
    assert v.slack_down == 0
    assert v.slips, "**judgeable と逆の指示**に戻っています"


def test_遅れ由来の帯は上へは効く():
    """**`waits` は上向きのまま。** 下だけを締めて、上まで締めないこと。"""
    a = dc.Answer(date(2026, 9, 5), "遅れ由来", slack=1, slack_down=0)
    v = dc.Verdict(claim="c", deadline=date(2026, 9, 6), ready=a.ready, answers=[a])
    assert v.waits == 0, "帯の中の待ちを数えると、書き換えの往復が戻ります"


def test_slack_downを書かない答えはこれまでどおり対称():
    """**伸び率の推定は左右対称のまま**（上にも下にも外れます）。"""
    a = dc.Answer(date(2026, 9, 20), "推定", slack=15)
    v = dc.Verdict(claim="c", deadline=date(2026, 9, 10), ready=a.ready, answers=[a])
    assert v.slack_down == 15 and not v.slips


def test_haveの無い行の書き直しは1回だけ(tmp_path):
    """**移行の1回は書き直す。2回目からは足さない。**（2026-08-27 夜・最適化の回）

    `have` を控え始めた日は、その日の行が既に `have` 無しで在ります。
    それを1回だけ書き直すのは正しい —— **ただし条件を「その行に `have` が
    無いか」に置くと、`have` を持たない答えでは毎周1行ずつ増えます。**

    増えると害が出るのは行数ではなく**帯**です。`_rate_scatter()` は点の
    散らばりで ±N日 を出すので、**同じ値の行が増えるほど帯が狭く出ます** ——
    狭い帯は「書き換えてよい」に読めて、churn（3日に4回 期限が書き換わる）が
    戻ります。
    """
    p = tmp_path / "deadline_est.jsonl"
    p.write_text(json.dumps({"at": "2026-08-27", "key": "k", "rate": 1.5},
                            ensure_ascii=False) + "\n", encoding="utf-8")

    # `have` を持つ答えなら、1回だけ書き直す
    a = dc.Answer(date(2026, 9, 1), "why", rate=1.5, rate_key="k", have=5)
    v = dc.Verdict(claim="c", deadline=date(2026, 9, 1), ready=a.ready, answers=[a])
    assert dc.record_estimates([v], path=p, as_of=date(2026, 8, 27)) == 1
    assert dc.record_estimates([v], path=p, as_of=date(2026, 8, 27)) == 0, \
        "**書き直しは1回だけ。**2回目からは (鍵, 日) に `have` を持つ行が在ります"

    # `have` を持たない答えは、その日の1行目だけ（毎周 足さない）
    q = tmp_path / "b.jsonl"
    b = dc.Answer(date(2026, 9, 1), "why", rate=1.5, rate_key="k")
    w = dc.Verdict(claim="c", deadline=date(2026, 9, 1), ready=b.ready, answers=[b])
    assert dc.record_estimates([w], path=q, as_of=date(2026, 8, 27)) == 1
    assert dc.record_estimates([w], path=q, as_of=date(2026, 8, 27)) == 0
    assert dc.record_estimates([w], path=q, as_of=date(2026, 8, 27)) == 0
