"""**焼き直しは、一度も終わったことがありませんでした**（2026-09-04 06:4x に数えた）。

    data/rebake.jsonl   start 22件 ／ beat 15件 ／ skip 3件 ／ **done 0件**

死に方は毎回 同じ。`rebake_today()` は `subprocess.Popen(start_new_session=True)` で
背景へ逃がすが、**逃がす先はこの器の中**で、回が終われば器ごと回収される。
直近5日のサブは `start` から中央値 11分 で終わり、焼き直しは分かりやすさの輪だけで
14分 を超える（この回に実測）。＝ **背景へ逃がすかぎり、構造上 間に合わない。**

画面（`next_slot.machine_rebake_lines`）は長らく
「いま焼いています → **手で撃たないこと**」だけを出していた。回はそれを読んで
その場で終わり、器はその瞬間に回収され、焼く側も道連れになる。
**「走っている」と「終わる」は別**で、後者はこれまで 0件 —— それを言わないかぎり
この形は永久に回り続ける。
"""
from __future__ import annotations

import pytest

from scripts import ahead_sweep
from src import next_slot


def test_起きた数と終わった数を分けて数える(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"kind": "start"}, {"kind": "beat"}, {"kind": "start"},
            {"kind": "skip"}, {"kind": "done", "rc": 0}]
    monkeypatch.setattr(ahead_sweep, "_rebake_rows", lambda root=None: rows)
    assert ahead_sweep.rebake_tally() == (2, 1)


def test_一度も終わっていなければ待てと言う(monkeypatch: pytest.MonkeyPatch) -> None:
    """**この行が無いと、回は「機械がやるだろう」で終わり、機械は道連れで死にます。**"""
    monkeypatch.setattr(ahead_sweep, "rebake_tally", lambda root=None: (22, 0))
    monkeypatch.setattr(ahead_sweep, "rebake_plan_for",
                        lambda day, t, **kw: {"video_id": "V1", "do": False, "sha": "s",
                                              "topic": "t", "why": "焼いている最中"})
    monkeypatch.setattr(ahead_sweep, "_rebake_rows",
                        lambda root=None: [{"video_id": "V1", "sha": "s", "kind": "beat",
                                            "at": "2026-09-04T06:22:39+09:00"}])
    monkeypatch.setattr(ahead_sweep, "rebake_died", lambda *a, **k: False)
    out = "\n".join(next_slot.machine_rebake_lines("V1"))
    assert "いま焼いています" in out
    assert "22回 起きて、0回" in out
    assert "終わるまで待つこと" in out


def test_一度終わったあとも待てと言う(monkeypatch: pytest.MonkeyPatch) -> None:
    """**`done` が出ても「待て」は消してはいけません**（2026-09-04 08:2x に置き直した）。

    この検査は前は逆のこと（「一度でも終わっていれば待てとは言わない」）を守っていました。
    **`done` の数は、焼く側が死ぬかどうかと関係がありません** —— 焼く側は
    `Popen(start_new_session=True)` でもこの器の中に居るので、**回が終われば道連れ**です。
    09/04 07:40 の唯一の `done` も、回が 78分 居続けたから出たものでした。

    そして待つ側が要るのは「終わったことがあるか」ではなく **「あと何分 居ればいいか」**で、
    その数は `done` が出てから初めて本物（78.2分）になります。
    **いちばん要る回で消える**作りだったので、両方の枝で出します。
    """
    monkeypatch.setattr(ahead_sweep, "rebake_tally", lambda root=None: (22, 3))
    monkeypatch.setattr(ahead_sweep, "bake_minutes", lambda: (78.2, 1))
    monkeypatch.setattr(ahead_sweep, "rebake_plan_for",
                        lambda day, t, **kw: {"video_id": "V1", "do": False, "sha": "s",
                                              "topic": "t", "why": "焼いている最中"})
    monkeypatch.setattr(ahead_sweep, "_rebake_rows",
                        lambda root=None: [{"video_id": "V1", "sha": "s", "kind": "beat",
                                            "at": "2026-09-04T06:22:39+09:00"}])
    monkeypatch.setattr(ahead_sweep, "rebake_died", lambda *a, **k: False)
    out = "\n".join(next_slot.machine_rebake_lines("V1"))
    assert "22回 起きて、3回 終わっています" in out
    assert "終わるまで待つこと" in out
    # **何分 待てばいいか**は、`done` が在るときは帳面の実測から出すこと
    assert "78分 は要ります" in out
    assert "`data/rebake.jsonl` の `done` の実測" in out
    assert "下限" not in out


def test_done_が無い間は下限と断って出す(monkeypatch: pytest.MonkeyPatch) -> None:
    """**`done` が 0件 の間の数は下限です**（輪 ＋ 焼き。読み照合の輪は 0 と置いてある）。

    実測は 2.1倍（37分 → 78.2分）でした。**断らずに出すと、待つ側が早く降ります。**
    """
    monkeypatch.setattr(ahead_sweep, "rebake_tally", lambda root=None: (22, 0))
    monkeypatch.setattr(ahead_sweep, "bake_minutes", lambda: (37.0, 2))
    monkeypatch.setattr(ahead_sweep, "rebake_plan_for",
                        lambda day, t, **kw: {"video_id": "V1", "do": False, "sha": "s",
                                              "topic": "t", "why": "焼いている最中"})
    monkeypatch.setattr(ahead_sweep, "_rebake_rows",
                        lambda root=None: [{"video_id": "V1", "sha": "s", "kind": "beat",
                                            "at": "2026-09-04T06:22:39+09:00"}])
    monkeypatch.setattr(ahead_sweep, "rebake_died", lambda *a, **k: False)
    out = "\n".join(next_slot.machine_rebake_lines("V1"))
    assert "37分 は要ります" in out
    assert "**下限**" in out
