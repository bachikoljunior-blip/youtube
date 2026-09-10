"""**置いた起こしが、狙った時刻に周を出したか**（`next_round.wake_missed`）。

**なぜ要るか**（2026-09-10 22:0x JST・optimizer・Opus。**この回に引かれた条件**）:

`decide()` の覆る条件 (2) は 09/03 から
**「`wake_at` を 15分 過ぎても `rounds.jsonl` に周が無いなら、起こしの口を直す」**と
書いていましたが、**その数をどこも数えていませんでした** ——次の回が
`parent_wakes.jsonl` と `rounds.jsonl` を手で突き合わせるしかない形で、
§7 (j)（「0件」も「7本」もどこも数えていなかった）・(m) と同じ型です。

実測（この回・`wake_missed()`）: 置いた起こし **25本**・遅れの中央値 **1.76分**・
5分 超 **2本**・**15分 超 1本（09/10 12:00 の 18.5分 ＝ 4%）**。
その 1本 は §7 (d) の門 1.25 を 12窓 で初めて越えた窓（**1.481**）の当のもので、
拾ったのは起こしではなく**心拍**（11:59:31 ＋ 18.28分 ＝ 12:18:32）でした。

**この検査が見ているのは 3つ**: 分母が「`wake_placed` が True の行だけ」であること・
遅れを**狙った時刻**から数えること（置いた時刻からではない）・
周を `round` で畳んでから数えること（1周 2行 を 2つ の届きに数えない）。
"""
import datetime as dt

from scripts import next_round

BASE = dt.datetime(2026, 9, 10, 0, 0, tzinfo=dt.timezone.utc)


def _t(minutes: float) -> dt.datetime:
    return BASE + dt.timedelta(minutes=minutes)


def _placed(at_min: float, wake_min: float, placed: bool = True) -> dict:
    return {"at": _t(at_min).isoformat(), "who": "owner",
            "wake_at": _t(wake_min).isoformat(), "wake_placed": placed}


def test_狙った時刻に周が立てば_届いた側(monkeypatch):
    got = next_round.wake_missed(rows=[_placed(0, 36)], starts=[_t(37.5)])
    assert got["placed"] == 1
    assert got["missed"] == []
    assert abs(got["median_lag"] - 1.5) < 1e-6


def test_15分_過ぎても周が無ければ_届かなかった側(monkeypatch):
    got = next_round.wake_missed(rows=[_placed(0, 36)], starts=[_t(54.5)])
    assert got["placed"] == 1
    assert len(got["missed"]) == 1
    assert abs(got["missed"][0][1] - 18.5) < 1e-6


def test_門ちょうどは鳴らない(monkeypatch):
    """15.0分 ちょうどは「過ぎても」ではない（**陰性対照**）。"""
    got = next_round.wake_missed(rows=[_placed(0, 36)], starts=[_t(51)])
    assert got["missed"] == []


def test_置かなかった行は分母に入れない(monkeypatch):
    """`wake_placed` が False の行・列を持たない古い行は、どちらも分母の外。"""
    old = {"at": _t(0).isoformat(), "who": "owner", "wake_at": _t(36).isoformat()}
    got = next_round.wake_missed(
        rows=[old, _placed(1, 37, placed=False), _placed(2, 38)],
        starts=[_t(39)])
    assert got["placed"] == 1


def test_親以外の行は数えない(monkeypatch):
    row = _placed(0, 36)
    row["who"] = "sub"
    got = next_round.wake_missed(rows=[row], starts=[_t(60)])
    assert got["placed"] == 0 and got["missed"] == []


def test_周が起こしの少し手前に立っても_同じ届き(monkeypatch):
    """周の記録は起こしの数秒 前に立つことが在る（親は**記録してから**押す・§5）。
    そこを「まだ来ていない」と読むと、**次の周までの丸ごと**が遅れに化けます。"""
    got = next_round.wake_missed(rows=[_placed(0, 36)],
                                 starts=[_t(35.7), _t(72)])
    assert got["missed"] == []
    assert got["median_lag"] < 0


def test_まだ来ていない起こしは分母だけに居る(monkeypatch):
    """先の時刻に置いたばかりの起こしを「届かなかった」に数えないこと
    （**陽性対照**: `after` の空を落ちた側に数えると、置いた直後の毎周が鳴ります）。"""
    got = next_round.wake_missed(rows=[_placed(0, 36)], starts=[_t(10)])
    assert got["placed"] == 1
    assert got["missed"] == [] and got["lags"] == []


def test_同じ周の2行を_2つの届きに数えない(monkeypatch):
    """`rounds.jsonl` は 1周 に役の数だけ行を書きます（`round_gaps` の註）。
    畳まずに数えると届きが二重になるので、**畳んだ `round_starts` を通す**こと。"""
    starts = next_round.round_starts.__doc__
    assert starts and "畳んだ" in starts
    rounds = [{"at": _t(37).isoformat(), "round": "r1", "role": "hourly"},
              {"at": _t(37).isoformat(), "round": "r1", "role": "optimizer"}]
    monkeypatch.setattr(next_round, "rows", lambda: rounds)
    got = next_round.wake_missed(rows=[_placed(0, 36)])
    assert len(got["lags"]) == 1


def test_実物の台帳でも数が出る():
    """実物で 1つも数えられない形（列名のずれ）を、この場で捕まえるため。"""
    got = next_round.wake_missed()
    assert got["placed"] >= 1
    assert all(l >= -1.0 for l in got["lags"])


def test_decide_が台帳に数を書く(monkeypatch, tmp_path):
    """次の回が手で突き合わせないための列（`wake_missed` / `wake_missed_n`）。"""
    monkeypatch.setattr(next_round, "LIVE", tmp_path / "live.json")
    monkeypatch.setattr(next_round, "WAKE", tmp_path / "wake.json")
    got = next_round.decide(live=1)
    assert "wake_missed" in got and "wake_missed_n" in got
    assert got["wake_missed_n"] >= got["wake_missed"]
