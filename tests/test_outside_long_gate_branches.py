"""**24h の先読みの門が、それが門をしている決定を実際に変えられること。**

## なぜ要るか（2026-09-04・最適化の回。「最適化されてんの？」→ **いいえ** の理由を1つ潰した）

`src/daily_pick.outside_long_readout()` の 24h の先読みの門（`OUTSIDE_24H_GATE`）は、
**門を越えた枝も、割った枝も、どちらも「次の未決の日の1本は長尺」と印字していました。**

    v >= OUTSIDE_24H_GATE  → 「次の未決の日の1本も外の作りの長尺」
    v <  OUTSIDE_24H_GATE  → 「**それでも**次の未決の日の1本は長尺」

**＝ 門が、決定を1度も変えられない。** それでも毎周 数字は出るので、回は
「測って決めた」と読み、`data/daily_pick.jsonl` の決めは 09-04・09-05 とも長尺、
`data/eta.jsonl` の 再生/日(7d) は 6,299（08-25）→ 1,344（09-03）＝ **-79%** でした。

割ったときの言い分（「ショートは 4,000時間 の門に 0時間」）は 門2 だけの比較で、
**同じファイルの `gate_arithmetic()` が名指ししている「AND の片脚を落とす」誤り**です
（門1 は両方の道に要る。長尺経由 ×314 対 ショート経由 ×11）。

**この検査が見ているのは「どちらの形が正しいか」ではありません** —— 形は
`gate_arithmetic()["nearer"]` が毎周 数え直します。見ているのは
**先読みの門の2つの枝が、同じ文を出さないこと**だけです。

**覆る条件**: `gate_arithmetic()` が両形の脚を出せない回は `and_path_form()` が
`(None, 理由)` を返し、`stop` の枝は「長尺のまま」に落ちます（＝そのときは 2つの枝が
同じ形を名指しますが、**理由の文は別**）。門そのものを畳んだら、この検査ごと消すこと。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src import daily_pick

JST = daily_pick.JST


def _readout(monkeypatch, views: int):
    """`outside_long_readout` が読む2つの控えを、その場で差し替えて撃つ。"""
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    pub = now - timedelta(hours=30)
    uploaded = {"vid1": {"topic": "t-out", "at": pub.isoformat(), "video_id": "vid1"}}
    obs = {"id": "vid1", "views": views, "hours": 30.0, "at": pub.isoformat()}
    monkeypatch.setattr(daily_pick, "_latest_uploaded", lambda *a, **k: uploaded)
    monkeypatch.setattr(daily_pick, "_latest_obs", lambda vid, *a, **k: obs)
    tops = [{"id": "t-out", "style": "outside_long"}]
    return daily_pick.outside_long_readout(now=now, topics=tops)


def test_門の上と下で判定が別になる(monkeypatch):
    """`go` と `stop` は、同じ門の別の側。ここが同じなら門は飾りです。"""
    _, over = _readout(monkeypatch, daily_pick.OUTSIDE_24H_GATE + 5)
    _, under = _readout(monkeypatch, daily_pick.OUTSIDE_24H_GATE - 5)
    assert over == "go"
    assert under == "stop"


def test_門の両側が_次の日に別の形を名指すこと(monkeypatch):
    """**これが 2026-09-04 まで壊れていた所。**

    文が1文字でも違えば通る検査ではありません（旧版も文言だけは別でした）。
    見るのは **名指された「次の未決の日の形」** —— 門の上と下で同じ形なら、
    門は決定を1度も変えていません。"""
    monkeypatch.setattr(daily_pick, "and_path_form",
                        lambda *a, **k: ("ショート", "（検査の値）"))
    over, _ = _readout(monkeypatch, daily_pick.OUTSIDE_24H_GATE + 5)
    under, _ = _readout(monkeypatch, daily_pick.OUTSIDE_24H_GATE - 5)
    o, u = "\n".join(over), "\n".join(under)
    # 門の上: 次の日も長尺（前提を続ける）。門の下: 門の算が名指した形。
    assert "次の未決の日の1本も外の作りの長尺" in o
    assert "次の未決の日の1本も外の作りの長尺" not in u
    assert "次の未決の日の1本は ショート" in u, f"門を割っても形が動いていません:\n{u}"


def test_門を割った枝は門の算が名指しした形を出す(monkeypatch):
    """`and_path_form()` がショートを返す回は、割った枝もショートを名指すこと
    （**形は決め打ちしません** —— `nearer` が長尺へ戻れば、この文も戻ります）。"""
    monkeypatch.setattr(daily_pick, "and_path_form",
                        lambda *a, **k: ("ショート", "（検査の値）"))
    lines_under, verdict = _readout(monkeypatch, daily_pick.OUTSIDE_24H_GATE - 5)
    assert verdict == "stop"
    text = "\n".join(lines_under)
    assert "ショート" in text
    assert "それでも次の未決の日の1本は長尺" not in text


def test_門の算が出せない回は長尺のままに落ちる(monkeypatch):
    """**推測で埋めないこと。** 脚が立たない回は、形を動かさない。"""
    monkeypatch.setattr(daily_pick, "and_path_form",
                        lambda *a, **k: (None, "門1 の脚が立ちません"))
    lines_under, verdict = _readout(monkeypatch, daily_pick.OUTSIDE_24H_GATE - 5)
    assert verdict == "stop"
    assert "長尺のまま" in "\n".join(lines_under)
