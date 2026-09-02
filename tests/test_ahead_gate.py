"""**「先の日付の予約が0本」の門が、鳴るべきときに鳴り、鳴らないときに黙ること。**

## なぜ要るか（2026-09-02・オーナー原文）

> **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

規則5（固定その4）は「**先の日付には1本も置かない**」。それでも 08/31 の固定から
2日で 459本 → 107本 にしか減っていません。**減らす手は在ったが、
「その回が選べば撃つ」形だった**からです（09/01 の実測: `fix` 82% / `upload` 0件）。

`scripts/ahead_gate.py` はそれを門にしたものです。**この検査は、その門が
「発火したことのない検査」にならないよう、故障を注入して発火を確かめます**
（`CLAUDE.md`「**発火したことのない検査は検査ではない**」）。

**逃げ道が1つだけであること**も、ここで見ます —— 逃げ道は「日枠が尽きている」で、
**回の裁量ではありません。** そこが緩んだら、また同じことが起きます。

## 覆る条件

- `house_rule.SAME_DAY_SCHEDULING_ONLY` が `False` になったら、この門は黙るのが
  正しい振る舞いです（下の `test_規則5_が外れたら黙る` がそれを見ています）
- 控えは「口に在って控えに無い予約」を見落とす側に外れます。だから
  **「鳴らない ＝ 0本」ではありません** —— `--live` の観測を要求する枝が
  そこを塞いでいます（`test_控えが0本でも実物を見ていなければ止める`）
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

_spec = importlib.util.spec_from_file_location(
    "ahead_gate_mod", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ahead_gate)

NOW = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)          # 09/02 14:00 JST


def _row(days: int, hour: int = 20, vid: str = "v") -> dict:
    """`NOW` の JST 日付から `days` 日ずらした日の `hour` 時に予約が1本ある控えの行。"""
    day = (NOW.astimezone(JST) + timedelta(days=days)).date()
    t = datetime(day.year, day.month, day.day, hour, 0, tzinfo=JST)
    return {"id": vid, "title": "t",
            "at": t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}


class _Quota:
    def __init__(self, open_: bool):
        self.open = open_
        self.line = "日枠: " + ("開いています" if open_ else "尽きています")


@pytest.fixture()
def 窓(monkeypatch, tmp_path):
    """観測の置き場を砂場へ移し、日枠を差し替えられるようにする。"""
    monkeypatch.setattr(ahead_gate, "_path", lambda: tmp_path / "ahead_live.jsonl")
    monkeypatch.setattr(ahead_gate.upload_cap, "window_start",
                        lambda now=None: NOW - timedelta(hours=2))
    return tmp_path


def _quota(monkeypatch, open_: bool) -> None:
    monkeypatch.setattr(ahead_gate.upload_cap, "day_quota",
                        lambda now=None: _Quota(open_))


# ---------------------------------------------------------------- 数える側
def test_きょうぶんは_先の日付ではない():
    """当日の予約は規則どおり。**外す対象に混ぜないこと**（外すと公開が0本の日になる）。"""
    assert ahead_gate.ahead([_row(0)], NOW) == []


def test_明日以降は_1本でも数える():
    assert len(ahead_gate.ahead([_row(1)], NOW)) == 1


def test_もう過ぎた予約は数えない():
    """控えの `at` は公開ずみの本にも残る。数えると永久に 0本 にならない。"""
    assert ahead_gate.ahead([_row(-3)], NOW) == []


def test_日ごとに割れる():
    rows = [_row(1, 20, "a"), _row(1, 21, "b"), _row(2, 20, "c")]
    days = ahead_gate.by_day(ahead_gate.ahead(rows, NOW))
    assert sorted(days.values()) == [1, 2]


# ---------------------------------------------------------------- 門の側
def test_故障を注入すると発火する_先の日付に1本(窓, monkeypatch):
    """**注入する故障**: 明日に1本 置く。枠は開いている。"""
    _quota(monkeypatch, True)
    v = ahead_gate.verdict(NOW, [_row(1)])
    assert v["block"] is True
    assert v["ahead"] == 1


def test_控えも実物も0本なら通す(窓, monkeypatch):
    _quota(monkeypatch, True)
    ahead_gate.record(0, [], "videos.list", NOW - timedelta(minutes=10))
    v = ahead_gate.verdict(NOW, [_row(0)])
    assert v["block"] is False
    assert "正しい状態" in v["why"]


def test_控えが0本でも実物を見ていなければ止める(窓, monkeypatch):
    """**2026-09-01 16:33 の形**: 控え 0本／Studio に4本。控えだけで通さないこと。"""
    _quota(monkeypatch, True)
    v = ahead_gate.verdict(NOW, [_row(0)])
    assert v["block"] is True
    assert "実物" in v["why"]


def test_控えが0本でも実物に在れば止める(窓, monkeypatch):
    _quota(monkeypatch, True)
    ahead_gate.record(4, ["a", "b", "c", "d"], "videos.list", NOW - timedelta(minutes=1))
    v = ahead_gate.verdict(NOW, [])
    assert v["block"] is True
    assert "実物には 4本" in v["why"]


def test_前の窓の観測は証拠にならない(窓, monkeypatch):
    """窓が変われば口の中身も変わりうる。**古い観測で通さないこと。**"""
    _quota(monkeypatch, True)
    ahead_gate.record(0, [], "videos.list", NOW - timedelta(hours=5))   # 窓の前
    v = ahead_gate.verdict(NOW, [])
    assert v["block"] is True
    assert ahead_gate.last_observation(NOW) is None


# ---------------------------------------------------------------- 逃げ道
def test_逃げ道は日枠だけ(窓, monkeypatch):
    """**枠が尽きている回だけ通します。** 撃てないので、止めても進みません。"""
    _quota(monkeypatch, False)
    v = ahead_gate.verdict(NOW, [_row(1), _row(2)])
    assert v["block"] is False
    assert v["ahead"] == 2
    assert v["quota_open"] is False


def test_日枠が読めない回は止める側へ倒す(窓, monkeypatch):
    """読めないことを「尽きている」と読むと、**外せる回まで外さなくなります。**"""
    def _boom(now=None):
        raise RuntimeError("読めない")
    monkeypatch.setattr(ahead_gate.upload_cap, "day_quota", _boom)
    v = ahead_gate.verdict(NOW, [_row(1)])
    assert v["block"] is True


def test_規則5_が外れたら黙る(窓, monkeypatch):
    """オーナーが「先の日付にも置いてよい」と言ったら、判定は `house_rule` 1か所で外れる。"""
    _quota(monkeypatch, True)
    monkeypatch.setattr(ahead_gate.house_rule, "same_day_only", lambda: False)
    v = ahead_gate.verdict(NOW, [_row(1), _row(9)])
    assert v["block"] is False


# ---------------------------------------------------------------- 観測の記録
def test_観測は追記されて読み直せる(窓):
    ahead_gate.record(3, ["a"], "videos.list", NOW - timedelta(minutes=5))
    ahead_gate.record(0, [], "videos.list", NOW - timedelta(minutes=1))
    seen = ahead_gate.last_observation(NOW)
    assert seen is not None and seen["count"] == 0
    lines = (窓 / "ahead_live.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["count"] == 3


def test_手順が実物を見る手を名指ししている():
    """**印字ではなく手を渡すこと。** 「どうやって直すか」が無い門は読まれません。"""
    assert "--live" in ahead_gate.HOWTO
    assert "pool_drain.py --apply --keep 0" in ahead_gate.HOWTO
    assert "きょうのぶん" in ahead_gate.HOWTO
