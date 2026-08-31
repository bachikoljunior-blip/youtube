"""**時刻を足したせいで、日付が消えていました**（2026-08-28 23:3x・最適化の回）。

`scripts/deadline_check.py` の `_ans_after` は `at_time_jst:` が書いてあって
その時刻がまだ来ていないとき、**`Answer(None, ...)` を返していました。**
日が出ない ＝ `ready_by_claim()` が落とす ＝ `unready_claims()` へ回り、
`src/arm_speed.forward()`（予定表の θ）と `forward_by_arm()`（腕べつ）の
**両方から、その前提が消えます。**

実測 2026-08-28 23:1x、`unready` の 3件 のうち1件がこれでした ——

    「1日に再生が付く本の集合は、左端つきの帯（08:59〜13:30 JST）で決まる。
      本数（先頭10本）ではない」   `on_date: 2026-09-03` / `at_time_jst: "04:00"`

同じ回の `scripts/queue_lag.py` は、この前提が切り分ける (A)/(B) の差を
**27倍**（判定 34日後 対 8日後）と印字しています。**台帳でいちばん高い前提**で、
しかも**いちばん正確に日の分かっている要件**（時計。伸び率の推定ですらない）が、
**唯一「判定できる日が出せません」の側に居ました。**

腕べつの実測（この直しの前 → 後）:

    density  14日窓  n **4 → 5**（per_day 0.286 → 0.357）／ undated **1 → 0**

そして `warming` に落ちるので、印字の結論はこうなります ——

    → **今日の 04:00 JST に出ます。**…… **その時刻まで待つこと**

**実際は 09/03 で、6日 ずれています。** すぐ上の行は
「**09/03 04:00 JST** に出ます（いま 08/28 23:16 JST）」と正しく出しており、
**同じ枠の2行が食い違って、結論を言う側だけが誤り**でした。

**早撃ちを止める役目は、ここではありません。**
`scripts/drift.py` の `split_overdue()` が 2026-08-28 から
「`ready == today` かつ `ready_at` がまだ来ていない」を見ています。
だから `ready=on` ＋ `ready_at=when` を返せば、日は残り、早撃ちは止まります。

**この検査が落ちる ＝ どちらかが戻った**:
  (1) `_ans_after` が時刻待ちで日を捨てる形に戻った
  (2) `warming` の印字が `at_time_jst` だけを見て「今日の」と書く形に戻った
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as J  # noqa: E402


def _future(days: int) -> date:
    return datetime.now(J.JST).date() + timedelta(days=days)


def test_先の日の時刻待ちでも日を捨てない():
    """**本体。** `on_date` が先なら、その日が `ready` として出ること。"""
    on = _future(6)
    need = {"kind": "after", "on_date": on.isoformat(), "at_time_jst": "04:00",
            "what": "6時間の読み"}
    a = J._ans_after(need, lag=3)
    assert a.ready == on, f"**日を捨てています**: ready={a.ready!r}（要 {on}）"
    assert a.ready_at is not None, "その日のうちの時刻が `ready_at` に載っていません"
    assert a.ready_at.hour == 4 and a.ready_at.date() == on


def test_先の日なら_日は来ていますと言わない():
    """`why` の括弧が「日は来ています」と言うのは、**今日のときだけ**。"""
    on = _future(6)
    need = {"kind": "after", "on_date": on.isoformat(), "at_time_jst": "04:00",
            "what": "6時間の読み"}
    why = J._ans_after(need, lag=3).why
    assert "日は来ていますが" not in why, f"**先の日なのに『日は来ています』**: {why}"
    assert "あと 6日" in why, why


def test_今日の時刻待ちは今までどおり日は来ていますと言う():
    """**同じ日の枝を壊さないこと。** ここは文言も振る舞いも変えていません。"""
    now = datetime.now(J.JST)
    later = now + timedelta(hours=2)
    if later.date() != now.date():
        return                      # 日をまたぐ回は、この枝を測れない
    need = {"kind": "after", "on_date": now.date().isoformat(),
            "at_time_jst": later.strftime("%H:%M"), "what": "6時間の読み"}
    a = J._ans_after(need, lag=3)
    assert a.ready == now.date(), "**今日でも日を捨てないこと**（早撃ちは `drift` が止めます）"
    assert a.ready_at is not None and a.ready_at > now
    assert "日は来ていますが" in a.why


def test_ready_atが載っていること_これが早撃ちの唯一の門():
    """`ready=today` を返す以上、**`ready_at` が無いと `drift` は止められません**。

    `drift.split_overdue()` は `(kind, ready, slips, slack, ready_at)` の
    5つ目を見ます。ここが `None` だと `str(ready) <= today` で
    「**いま判定できる**」に入り、**時刻の前に撃ちます。**
    """
    now = datetime.now(J.JST)
    need = {"kind": "after", "on_date": now.date().isoformat(),
            "at_time_jst": "23:59", "what": "6時間の読み"}
    a = J._ans_after(need, lag=3)
    if a.ready is None:              # 23:59 を過ぎた回（データ側の枝へ落ちる）
        return
    assert a.ready_at is not None, "**`ready_at` が無いと早撃ちが止まりません**"


def test_warmingの印字が今日と決めつけないこと():
    """**別の need が warming の前提**でも、日を間違えないこと。

    `_ans_after` を直したので、この枝は「同じ前提の**別の** need が
    まだ数えはじめたところ」のときにしか通りません。**そのときこそ**
    日を間違えると、読んだ回が今夜まで待って空振りします。
    """
    on = _future(6)
    v = J.Verdict(
        claim="つくりもの", deadline=on, ready=None,
        answers=[J.Answer(None, "まだ数えはじめたところ")],
        needs=[{"kind": "accrual", "need": 16, "have": 0},
               {"kind": "after", "on_date": on.isoformat(), "at_time_jst": "04:00"}])
    assert v.warming, "この組み立てが warming でなくなったら、検査の前提のほうを直すこと"
    text = "\n".join(J.lines([v], 3))
    assert "今日の 04:00" not in text, f"**先の日を『今日』と書いています**:\n{text}"
    assert f"{on:%m/%d} 04:00" in text, text
    assert "今日ではありません" in text, text


def test_checkを通しても_日と時刻が両方そろって出ること():
    """**`drift.py` が読むのはここです。**`Verdict.ready` と `Verdict.ready_at`。

    `drift._judge_state_by_claim()` は `(kind, ready, slips, slack, ready_at)`
    を組み、`split_overdue()` がその5つ目で「今日だが時刻はまだ」を止めます
    （`tests/test_drift_soonest_time_gate.py`）。**`_ans_after` と
    `split_overdue` の間の配線**を、ここで1回だけ通して見ます ——
    片側ずつ緑でも、`Verdict.ready_at` が拾い損ねたら早撃ちに戻ります。
    """
    now = datetime.now(J.JST)
    later = now + timedelta(hours=2)
    if later.date() != now.date():
        return
    item = {"claim": "つくりもの・配線の確認",
            "deadline": now.date().isoformat(),
            "needs": [{"kind": "after", "on_date": now.date().isoformat(),
                       "at_time_jst": later.strftime("%H:%M"),
                       "what": "6時間の読み"}]}
    v = J.check([item])[0]
    assert v.ready == now.date(), f"日が落ちています: {v.ready!r}"
    assert v.ready_at is not None and v.ready_at > now, (
        "**`Verdict.ready_at` が空です** —— `drift.split_overdue()` は"
        " `str(ready) <= today` だけを見て、時刻の前に撃ちます")


def test_台帳の帯の前提が_判定できる日を持っていること():
    """**現物での確認。** この1件が `unready` に戻ったら、θ から消えています。"""
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    want = [h for h in doc["hypotheses"]
            if "左端つきの帯" in str(h.get("claim") or "")
            and not any(k in h for k in ("verdict", "closed_on", "outcome"))]
    if not want:
        return                       # 閉じたら、この検査は役目を終えます
    claim = str(want[0]["claim"])
    assert claim not in J.unready_claims(), (
        "**`day_cap` の (A)/(B) を切り分ける前提が、また『日が出せない』側です。**"
        " `queue_lag.py` はこの差を 27倍 と印字しています —— 予定表から消さないこと")
    assert J.ready_by_claim().get(claim) is not None
