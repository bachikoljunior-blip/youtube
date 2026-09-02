"""**サブが0体なら、経過時間に関係なく GO。**（2026-08-31・オーナー指示）

## オーナー原文（**一字も変えないこと**）

> **「何で止まってんだよ！」**
> **「だったら良いに決まってんだろ！顔色伺ってんじゃねえよ！」**

## 何が起きたか

親が `scripts/next_round.py` の出す間隔（週の使用量から伸ばした **191分**）を
**手を止める理由に使い、サブが1体も走っていない状態で待ちました。**
`decide()` は経過時間しか見ていなかったので、**空いている時間が丸ごと落ちます。**

**間隔は「二重に立てない」ためのものであって、遊ばせるためのものではありません。**

## この検査が固定するもの

    1. `live == 0` なら、**間隔の途中でも GO**（`floor` をいくら伸ばしても）
    2. `live > 0` なら、これまでどおり間隔を待つ（＝二重に立てない）
    3. `live` が渡されない回は、**GO にも WAIT にも倒さない** ——
       これまでどおり間隔で解き、**「数が渡されていない」と印字する**
    4. 台帳（`data/live_subs.json`）が古いときは「読めなかった」扱い ——
       **親が落ちたあとの 0 を、いつまでも信じないこと**

**戻すには、この file を消すしかありません**（diff に出ます）。

**覆る条件**: サブが 0体 でも立ててはいけない状態が見つかったとき。
そのときは**間隔ではなく、その原因のほうを直すこと**
（`CLAUDE.md` 2026-08-31「止めるのではなく直すこと」）。
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("next_round_mod",
                                               ROOT / "scripts" / "next_round.py")
nr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nr)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _pinned(monkeypatch, tmp_path):
    """**間隔と台帳を、この検査の外の実物から切り離す。**"""
    monkeypatch.setattr(nr, "floor_minutes", lambda: (191.0, "検査で固定"))
    monkeypatch.setattr(nr, "LIVE", tmp_path / "live_subs.json")
    # 直前に「そろった周」が立っている ＝ 穴埋めの枝には落ちない
    started = (NOW - timedelta(minutes=5)).isoformat()
    group = [{"at": started, "role": r, "round": "R1"} for r in nr.ROLES]
    monkeypatch.setattr(nr, "current_round", lambda *a, **k: group)
    return group


def test_サブが0体なら間隔の途中でもGO():
    """**これが本体です。** 経過5分・間隔191分でも、0体なら立てること。"""
    d = nr.decide(now=NOW, live=0)
    assert d["go"] is True, d
    assert set(d["roles"]) == set(nr.ROLES), "0体なのに片肺で立てています"
    assert d.get("idle") is True


def test_間隔をいくら伸ばしても0体ならGO(monkeypatch):
    """**間隔は「空きを作る側」に使わないこと。**"""
    for floor in (35.0, 191.0, 10_000.0):
        monkeypatch.setattr(nr, "floor_minutes", lambda f=floor: (f, "検査で固定"))
        assert nr.decide(now=NOW, live=0)["go"] is True, floor


def test_理由の行が間隔ではなく0体を名指しする():
    """**「間隔まであと N分」だけだと、また同じ止まり方をします。**"""
    why = nr.decide(now=NOW, live=0)["why"]
    assert "0体" in why, why
    assert "間隔は見ません" in why, why


def test_走っているサブが在れば間隔を待つ():
    """**間隔の役目は二重に立てないこと。** そこは残すこと。"""
    d = nr.decide(now=NOW, live=2)
    assert d["go"] is False, d
    assert d["wait_min"] > 0


def test_数が渡されない回はこれまでどおり():
    """**GO にも倒さないこと。** 付け忘れた親が毎回 二重に立てます。"""
    d = nr.decide(now=NOW, live=None)
    assert d["go"] is False, d
    assert d["live"] is None, "読めていないのに数のような顔をしています"


def test_台帳から読める(monkeypatch):
    nr.live_write(0, now=NOW - timedelta(minutes=1))
    d = nr.decide(now=NOW)
    assert d["live"] == 0
    assert d["go"] is True, "台帳の 0体 が効いていません"


def test_古い台帳は読めなかった扱い():
    """**親が落ちたあとの 0 を、いつまでも信じないこと。**"""
    nr.live_write(0, now=NOW - timedelta(minutes=nr.LIVE_STALE_MIN + 1))
    n, why = nr.live_read(now=NOW)
    assert n is None, "古い台帳を信じています"
    assert "古い" in why
    assert nr.decide(now=NOW)["go"] is False


def test_壊れた台帳でも落ちない():
    nr.LIVE.parent.mkdir(parents=True, exist_ok=True)
    nr.LIVE.write_text("{これはJSONではない", encoding="utf-8")
    n, _ = nr.live_read(now=NOW)
    assert n is None
    assert nr.decide(now=NOW)["go"] is False


def test_台帳の書き込みは1行のJSON():
    row = nr.live_write(3, now=NOW)
    got = json.loads(nr.LIVE.read_text(encoding="utf-8"))
    assert got["live"] == 3 == row["live"]
    assert got["at"] == NOW.isoformat()


def test_0体でも1周に立つ数は役の数で頭打ち():
    """**暴走しないこと。** 0体 GO は「何体でも立てる」ではありません。"""
    d = nr.decide(now=NOW, live=0)
    assert len(d["roles"]) == len(nr.ROLES)


def test_オーナー原文がこの機械のどこかに在る():
    """**理由が消えたら、次の回が「間隔を守るのが正しい」に戻ります。**"""
    body = (ROOT / "scripts" / "next_round.py").read_text(encoding="utf-8")
    assert "何で止まってんだよ" in body, (
        "`decide()` の docstring から、なぜ 0体 GO なのかの原文が消えています")


def test_数が無い回はWAITを印字しない(monkeypatch, capsys):
    """**2026-09-02 21:2x。** 親は 0体 と数えたうえで `--live` を付けずに撃ち、
    出た WAIT を「（0体・WAIT 74分）」と出した（オーナー「てめえほんとバカだな」）。
    08-31 と同じ止まり方の2回目。**数が無い回に見せるのは COUNT だけ**（WAIT も GO も無し）。"""
    import sys
    monkeypatch.setattr(nr, "live_read", lambda now=None: (None, "台帳がありません"))
    monkeypatch.setattr(sys, "argv", ["next_round.py"])
    rc = nr.main()
    out = capsys.readouterr().out
    assert rc == 2, out
    lines = [ln.strip() for ln in out.splitlines()]
    assert "COUNT" in lines, out
    assert not any(ln.startswith("WAIT") for ln in lines), out
    assert not any(ln.startswith("GO") for ln in lines), out
    assert "--live" in out
