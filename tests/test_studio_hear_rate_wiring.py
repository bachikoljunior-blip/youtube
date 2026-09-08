"""`studio/hear._add_rates` の配線（2026-09-09 06:5x・optimizer・Opus）。

`tail_rate` そのものの検査は `tests/test_studio_hear_tail_rate.py`。ここは**繋がっているか**だけを見る:

  - 切り落としの在るコマに `rate` が付くこと
  - **切り落としが1つも無い回は、音の長さを1度も測らないこと**
    （`probe_duration` は ffprobe を呼ぶ。**この配線が無かったせいで、偽の wav 名を使う
      既存の検査 2件（`tests/test_studio_hear.py`）が落ちた** —— 06:5x に踏んで直した）
  - 長さが引けない回は**黙って出さない**（`tail_probe` の答えだけが残る）
"""
import pytest

from studio import hear


def _rows():
    return [
        {"i": 1, "exp": "あ" * 40, "diffs": [], "_gap": None, "_wav": "1.wav"},
        {"i": 2, "exp": "あ" * 50, "diffs": [], "_gap": None, "_wav": "2.wav"},
        {"i": 3, "exp": "あ" * 60, "diffs": [("すえ", "")], "_gap": "すえ" * 6, "_wav": "3.wav"},
    ]


def test_切り落としの在るコマに秒数が付く(monkeypatch):
    # コマ1 40字/8秒 = 5.0・コマ2 50字/10秒 = 5.0 ＝ 帯は 5.0〜5.0
    # コマ3 60字/12秒 = 5.0 ／ 末尾 12字 が無いなら 48/12 = 4.0 ＝ 帯の外 → present
    durs = {"1.wav": 8.0, "2.wav": 10.0, "3.wav": 12.0}
    monkeypatch.setattr(hear, "probe_duration", lambda w: durs[w])
    rows = _rows()
    hear._add_rates(rows)
    assert "rate" not in rows[0] and "rate" not in rows[1]
    assert rows[2]["rate"]["present"] is True
    assert rows[2]["rate"]["without"] == 4.0


def test_切り落としが無ければ長さを1度も測らない(monkeypatch):
    """**これが無いと、偽の wav 名を使う検査が落ちる**（06:5x に実際に落ちた）。"""
    def boom(w):
        raise AssertionError("切り落としが無い回に probe_duration を呼んだ")
    monkeypatch.setattr(hear, "probe_duration", boom)
    rows = [r for r in _rows() if not r["_gap"]]
    hear._add_rates(rows)
    assert all("rate" not in r for r in rows)


def test_長さが引けない回は黙って出さない(monkeypatch):
    def boom(w):
        raise OSError("ffprobe が無い")
    monkeypatch.setattr(hear, "probe_duration", boom)
    rows = _rows()
    hear._add_rates(rows)
    assert all("rate" not in r for r in rows)


def test_一致したコマが無ければ帯を作らない(monkeypatch):
    """帯は一致したコマだけから作る —— 分母が空なら、何も言わない。"""
    monkeypatch.setattr(hear, "probe_duration", lambda w: 10.0)
    rows = [{"i": 1, "exp": "あ" * 50, "diffs": [("x", "")], "_gap": "x", "_wav": "1.wav"}]
    hear._add_rates(rows)
    assert "rate" not in rows[0]
