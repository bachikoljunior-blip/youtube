"""親の間隔を、**心拍の刻みへ「近いほうへ」丸める**（`scripts/next_round.decide`）。

**なぜ要るか**（2026-09-08 19:1x JST・optimizer・Opus が実測して足した。`docs/METHOD.md` §5）:

親が起きられるのは cron `59 * * * *` ＝ **毎時1回**だけ（`list_triggers` で撃って確かめた）。
`decide()` は `passed >= floor` で GO を出していたので、**間隔は必ず刻みへ切り上がって**いた:

    pace() の求め 77分  → 実際の周から周 **119.3分**
    pace() の求め 48分  → 実際の周から周 **59.8分**

実測（`data/rounds.jsonl`・09/07 10:18〜09/08 18:59 の 15区間）: **120±5分 が 12区間**・
**60±5分 が 2区間**（残り1つは 378分 の穴）。60分 の 2区間 だけが `floor` 48分 の回で、
77分 に変わった直後から 119.3分 に戻っている ＝ **求めの 29分 の差が、実際の間隔を 2倍**。
効き目: 許される **0.775 %/時** に対して、区間の実測は **0.443 %/時**（57%）。

§5 17:0x は「77分 > 60分 なので、いまは cron（毎時）が上限ではありません」と書いたが、**逆**。
60分 の心拍では、**60分 を越える求めは全部 120分 になる。**
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import next_round

BEAT = 60.0
T0 = datetime(2026, 9, 8, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def rounds(tmp_path, monkeypatch):
    """前の周を1つだけ置いた台帳に差し替える。**本物には触らない。**"""
    p = tmp_path / "rounds.jsonl"
    rows = [{"at": T0.isoformat(), "role": r, "round": T0.isoformat()}
            for r in next_round.ROLES]
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    monkeypatch.setattr(next_round, "ROUNDS", p)
    monkeypatch.setattr(next_round, "WAKES", tmp_path / "parent_wakes.jsonl")
    return p


def _decide(monkeypatch, *, floor, passed, live=1, beat=BEAT):
    monkeypatch.setattr(next_round, "floor_minutes", lambda: (floor, "検査"))
    monkeypatch.setattr(next_round, "heartbeat_minutes", lambda *a, **k: (beat, "検査"))
    return next_round.decide(now=T0 + timedelta(minutes=passed), live=live)


# ---- 心拍そのものを数える ------------------------------------------------

def _wakes(tmp_path, monkeypatch, ats, who="owner"):
    p = tmp_path / "parent_wakes.jsonl"
    p.write_text("".join(
        json.dumps({"at": a.isoformat(), "who": who}, ensure_ascii=False) + "\n"
        for a in ats), encoding="utf-8")
    monkeypatch.setattr(next_round, "WAKES", p)
    return p


def test_間隔が足りないうちは_cronの写しを使う(tmp_path, monkeypatch):
    """**推測しない。** 数えられるようになるまでは、cron に書いてある数（写しだと言う）。"""
    _wakes(tmp_path, monkeypatch, [T0, T0 + timedelta(minutes=60)])
    beat, src = next_round.heartbeat_minutes()
    assert beat == next_round.HEARTBEAT_FALLBACK_MIN
    assert "写し" in src


def test_たまったら台帳から数え直す_写しを持たない(tmp_path, monkeypatch):
    """**これが本題** —— オーナーが cron を触ったら、台帳の間隔が先に変わる。"""
    ats = [T0 + timedelta(minutes=30 * i) for i in range(6)]
    _wakes(tmp_path, monkeypatch, ats)
    beat, src = next_round.heartbeat_minutes()
    assert beat == 30.0
    assert "実測" in src


def test_親以外の行は数えない(tmp_path, monkeypatch):
    """サブや人が手で撃った回を混ぜると、心拍が短いほうへ倒れる（`who` の当のもの）。"""
    ats = [T0 + timedelta(minutes=60 * i) for i in range(5)]
    p = _wakes(tmp_path, monkeypatch, ats)
    with p.open("a", encoding="utf-8") as fh:
        for i in range(5):
            fh.write(json.dumps({"at": (T0 + timedelta(minutes=60 * i + 1)).isoformat(),
                                 "who": "direct"}) + "\n")
    beat, _ = next_round.heartbeat_minutes()
    assert beat == 60.0


def test_壊れた台帳で心拍を0や1日にしない(tmp_path, monkeypatch):
    """歯止め。0 にすると間隔が消え、長すぎると周が立たなくなる。"""
    _wakes(tmp_path, monkeypatch, [T0 + timedelta(seconds=i) for i in range(6)])
    beat, _ = next_round.heartbeat_minutes()
    assert beat >= 10.0
    _wakes(tmp_path, monkeypatch, [T0 + timedelta(days=i) for i in range(6)])
    beat, _ = next_round.heartbeat_minutes()
    assert beat <= 180.0


# ---- 丸め方 --------------------------------------------------------------

def test_実測の当のもの_求め77分は次の心拍を待たない(rounds, monkeypatch):
    """**この検査が、直しの理由そのもの。**

    実測 09/08 17:00 → 18:59（119.3分）。`floor` 77分・心拍 60分 で、
    **59.8分 の起きは GO でなければならない**（待つと 119.8分 ＝ 42.8分 も外れる）。
    """
    d = _decide(monkeypatch, floor=77.0, passed=59.8)
    assert d["go"] is True


def test_遠いほうへは丸めない_求め90分は次の心拍を待つ(rounds, monkeypatch):
    """近いほうへ、であって「いつでも早く」ではない。90分 は 119.5分 のほうが近い。"""
    assert _decide(monkeypatch, floor=90.0, passed=59.8)["go"] is False
    assert _decide(monkeypatch, floor=90.0, passed=119.5)["go"] is True


def test_1心拍に2周は立てない(rounds, monkeypatch):
    """心拍の外から起こされた回（`send_later`・手で撃った回）で早められると、
    **同じ1時間に2周 立ちます。** 下限で締めてあること。"""
    assert _decide(monkeypatch, floor=77.0, passed=30.0)["go"] is False
    assert _decide(monkeypatch, floor=48.0, passed=20.0)["go"] is False


def test_求めが心拍より短い回は今までどおり(rounds, monkeypatch):
    """`floor` 48分 の回は前から 59.8分 で GO だった。**丸めで早まってはいけない。**"""
    assert _decide(monkeypatch, floor=48.0, passed=59.8)["go"] is True
    assert _decide(monkeypatch, floor=48.0, passed=47.0)["go"] is False


def test_0体の回は丸めない(rounds, monkeypatch):
    """**0体 なら親は `send_later` で分の粒度の起こしを置ける** ＝ 刻みに縛られていない。
    丸める理由が無く、丸めると起こしの時刻と食い違う。"""
    d = _decide(monkeypatch, floor=77.0, passed=59.8, live=0)
    assert d["go"] is False
    assert d["wake_at"] == T0 + timedelta(minutes=78.0)


def test_理由に数が出る(rounds, monkeypatch):
    """次に読む回が、丸めたことと その代償を数で見られること。"""
    d = _decide(monkeypatch, floor=77.0, passed=59.8)
    assert "心拍" in d["why"]
    assert d["heartbeat_min"] == BEAT


def test_心拍が変われば丸めも変わる(rounds, monkeypatch):
    """心拍 30分 なら、77分 の求めは 59.8分 では**まだ**早い（89.8分 のほうが近い）。"""
    assert _decide(monkeypatch, floor=77.0, passed=59.8, beat=30.0)["go"] is False
    assert _decide(monkeypatch, floor=77.0, passed=62.0, beat=30.0)["go"] is True
