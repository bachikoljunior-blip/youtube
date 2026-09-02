"""**サブが0体でも間隔は守る。ただし遊ばない —— 起こしを置いて待つ。**（2026-09-03）

## オーナー原文（**一字も変えないこと**）

> **「何で止まってんだよ！」**（2026-08-31）
> **「だったら良いに決まってんだろ！顔色伺ってんじゃねえよ！」**（同）
> **「使用量は定期的に画面送るからとりあえず最初は今までの最高速度の二分の一の速度でやって」**（09/02 18:4x）
> **「サブで判断して」**（09/03 06:3x）

## 何が起きたか（2つ）

**08-31**: 親が `next_round.py` の間隔（191分）を手を止める理由に使い、
サブが1体も走っていない状態で**何も置かずに**待った。→ この検査は「0体 なら即 GO」を固定した。

**09-03**: その「0体 なら即 GO」が、背景のサブ（~25分 で終わる）の完了通知で親を起こし、
**2体 を 17〜30分 ごと**に立てた（`data/rounds.jsonl` 09/03 00:04〜06:39・15周）。
実測 22:01→06:21 JST で 週「すべてのモデル」19→45%・「Fable のみ」21→71%（3.12 %/時 ＝
上限 0.743 の 4.2倍）。**このままなら 09/03 23:58 JST に尽き、土曜 07:00 まで 31時間 止まる。**
親は 03:3x・06:2x に食い違いを伝え、オーナー「サブで判断して」→ optimizer が決めた。

## この検査が固定するもの

    1. `live == 0` で間隔の途中なら **WAIT**。ただし `wake_at`／`wake_min`（起こし）を返す
    2. `live == 0` で間隔が明けていれば **GO**（全役）
    3. `live == 0` の待ちは `IDLE_WAIT_MAX_MIN` で頭打ち（推定が外れても 6時間 に1回は実物で確かめる）
    4. `live > 0` なら、これまでどおり間隔を待つ（＝二重に立てない）
    5. `live` が渡されない回は、**GO にも WAIT にも倒さない**（COUNT）
    6. 台帳（`data/live_subs.json`）が古いときは「読めなかった」扱い
    7. `main()` の 0体 WAIT は **`send_later` の撃ち方と「（0体・次 HH:MM）」を印字**し、
       同じ起こしを2度 置かない（`data/parent_wake.json`）

**覆る条件**: 実測で「起こしが届かない」が出たら（`wake_at` を 15分 過ぎても周が無い）、
起こしの口を直す —— **0体 即 GO に戻すのではなく**。オーナーが速さの上限を外したら、
間隔は `quota.py` の側で縮む（この検査は触らない）。
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
STARTED = NOW - timedelta(minutes=5)


@pytest.fixture(autouse=True)
def _pinned(monkeypatch, tmp_path):
    """**間隔と台帳を、この検査の外の実物から切り離す。**"""
    monkeypatch.setattr(nr, "floor_minutes", lambda: (191.0, "検査で固定"))
    monkeypatch.setattr(nr, "LIVE", tmp_path / "live_subs.json")
    monkeypatch.setattr(nr, "WAKE", tmp_path / "parent_wake.json")
    # 直前に「そろった周」が立っている ＝ 穴埋めの枝には落ちない
    group = [{"at": STARTED.isoformat(), "role": r, "round": "R1"} for r in nr.ROLES]
    monkeypatch.setattr(nr, "current_round", lambda *a, **k: group)
    return group


def test_サブが0体でも間隔の途中ならWAITで起こしを返す():
    """**これが本体です。** 経過5分・間隔191分・0体 → 立てない。ただし起こしの時刻を返す。"""
    d = nr.decide(now=NOW, live=0)
    assert d["go"] is False, d
    assert d.get("idle") is True
    assert d["wait_min"] == pytest.approx(186.0, abs=0.5)
    assert d["wake_min"] >= 1
    assert d["wake_at"] > NOW + timedelta(minutes=186), "起こしが間隔より前に置かれています"
    assert d["wake_at"] <= NOW + timedelta(minutes=188), "起こしが間隔からいくらも遅れています"


def test_0体で間隔が明けていればGO(monkeypatch):
    monkeypatch.setattr(nr, "floor_minutes", lambda: (4.0, "検査で固定"))
    d = nr.decide(now=NOW, live=0)
    assert d["go"] is True, d
    assert set(d["roles"]) == set(nr.ROLES), "0体なのに片肺で立てています"


def test_0体の待ちは上限で頭打ち(monkeypatch):
    """**推定が外れても、6時間 に1回は実物で確かめる。**"""
    monkeypatch.setattr(nr, "floor_minutes", lambda: (10_000.0, "検査で固定"))
    d = nr.decide(now=NOW, live=0)
    assert d["go"] is False
    assert d["floor_min"] == nr.IDLE_WAIT_MAX_MIN
    assert d["wait_min"] <= nr.IDLE_WAIT_MAX_MIN


def test_理由の行が0体と起こしを名指しする():
    why = nr.decide(now=NOW, live=0)["why"]
    assert "0体" in why, why
    assert "起こし" in why, why


def test_前の周の記録が無ければ0体はGO(monkeypatch):
    monkeypatch.setattr(nr, "current_round", lambda *a, **k: [])
    assert nr.decide(now=NOW, live=0)["go"] is True


def test_0体で片方だけ欠けていれば欠けをGO(monkeypatch):
    group = [{"at": STARTED.isoformat(), "role": nr.ROLES[0], "round": "R1"}]
    monkeypatch.setattr(nr, "current_round", lambda *a, **k: group)
    d = nr.decide(now=NOW, live=0)
    assert d["go"] is True and d.get("patch") is True
    assert d["roles"] == [nr.ROLES[1]]


def test_走っているサブが在れば間隔を待つ():
    """**間隔の役目は二重に立てないこと。** そこは残すこと。"""
    d = nr.decide(now=NOW, live=2)
    assert d["go"] is False, d
    assert d["wait_min"] > 0
    assert not d.get("idle")
    assert "wake_at" not in d, "走っているサブが在るのに起こしを置こうとしています"


def test_数が渡されない回はこれまでどおり():
    """**GO にも倒さないこと。** 付け忘れた親が毎回 二重に立てます。"""
    d = nr.decide(now=NOW, live=None)
    assert d["go"] is False, d
    assert d["live"] is None, "読めていないのに数のような顔をしています"


def test_台帳から読める(monkeypatch):
    nr.live_write(0, now=NOW - timedelta(minutes=1))
    d = nr.decide(now=NOW)
    assert d["live"] == 0
    assert d.get("idle") is True, "台帳の 0体 が効いていません"


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


def test_オーナー原文がこの機械のどこかに在る():
    """**理由が消えたら、次の回が惰性で戻します。** 両方の原文が要ります。"""
    body = (ROOT / "scripts" / "next_round.py").read_text(encoding="utf-8")
    assert "何で止まってんだよ" in body, "08-31 の原文が消えています"
    assert "サブで判断して" in body, "09-03 の原文（判断の出どころ）が消えています"
    assert "二分の一" in body, "速さの上限の原文が消えています"


def test_数が無い回はWAITを印字しない(monkeypatch, capsys):
    """**2026-09-02 21:2x。** 親は 0体 と数えたうえで `--live` を付けずに撃ち、
    出た WAIT を「（0体・WAIT 74分）」と出した（オーナー「てめえほんとバカだな」）。
    **数が無い回に見せるのは COUNT だけ**（WAIT も GO も無し）。"""
    import sys
    monkeypatch.setattr(nr, "live_read", lambda now=None: (None, "台帳がありません"))
    monkeypatch.setattr(nr, "refresh_rendered", lambda: [])
    monkeypatch.setattr(sys, "argv", ["next_round.py"])
    rc = nr.main()
    out = capsys.readouterr().out
    assert rc == 2, out
    lines = [ln.strip() for ln in out.splitlines()]
    assert "COUNT" in lines, out
    assert not any(ln.startswith("WAIT") for ln in lines), out
    assert not any(ln.startswith("GO") for ln in lines), out
    assert "--live" in out


def test_0体のWAITは起こしの撃ち方と出す文字を印字する(monkeypatch, capsys):
    """**親は印字どおりに動く。** `send_later` と「（0体・次 HH:MM）」が無いと、
    親は 08-31 の形（何も置かずに待つ）か、09-03 の形（即 立てる）に戻ります。"""
    import sys
    monkeypatch.setattr(nr, "refresh_rendered", lambda: [])
    # `main()` は実時刻で解くので、周の開始も実時刻の 5分 前に置く
    started = datetime.now(timezone.utc) - timedelta(minutes=5)
    group = [{"at": started.isoformat(), "role": r, "round": "R1"} for r in nr.ROLES]
    monkeypatch.setattr(nr, "current_round", lambda *a, **k: group)
    monkeypatch.setattr(sys, "argv", ["next_round.py", "--live", "0"])
    rc = nr.main()
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "\nWAIT " in "\n" + out, out
    assert "send_later" in out and "delay_minutes=" in out, out
    assert "（0体・次 " in out, out
    assert "GO " not in out.splitlines()[0]
    # 2回目は、同じ起こしを置かない
    rc = nr.main()
    out2 = capsys.readouterr().out
    assert rc == 0
    assert "置いてあります" in out2, out2
    assert "delay_minutes=" not in out2, out2


def test_起こしの台帳は過ぎたら無い扱い():
    nr.wake_write(NOW - timedelta(minutes=1), now=NOW - timedelta(minutes=10))
    assert nr.wake_read(now=NOW) is None
    nr.wake_write(NOW + timedelta(minutes=30), now=NOW)
    assert nr.wake_read(now=NOW) == NOW + timedelta(minutes=30)
