"""**時間切れで落ちた焼き直しを「焼いた」に数えないこと。**

## なぜ要るか（2026-09-04 16:5x に踏んだ）

`rebake_run()` は、焼きの返り値 `rc` を**問わずに** `done` を帳面へ書いていました。
`rebake_attempted()` は `done` が1行 在れば True を返す（「同じ台本は二度 焼かない」）ので、
**時間切れで1回 落ちただけの台本が、二度と焼けなくなります。**

実測（この日の実物）::

    14:42  `Ec-j1-W4nqw`（sha ff6f012e56da）  rc=0    3325秒  → `O_lfBxB7S8Q` へ差し替え
    15:09  `O_lfBxB7S8Q`（sha acbf24ae7bfd）  rc=124  5400秒  → クリップ 5/83 で時間切れ

**同じ器で、同じ題材が 3325秒 で焼けています。** 時間切れは台本の欠陥ではなく、
**器の混み具合**（4コア）です。それでも `done` が残ったので、**台本が外の型の脚を
6つとも満たしているのに、その台本は永久に焼けない**状態になりました ——
オーナーが固定した規則3（「次の投稿予定までにそこで投稿する動画を改善し続ける」）と
正面から食い違います。

`late`（枠に間に合わなかった回は `done` にしない）という逃げ道は**既に在りました**が、
立つのは `rc == 0` の枝の中だけで、**時間切れには当たりませんでした。**

**上限は付けています**（`REBAKE_TIMEOUT_RETRIES`）—— 毎回 90分 を捨て続けないため。
超えたら「この器では焼き切れない台本」と読み、印を残して次の回に台本の側を直させます。

**覆る条件**: 時間切れが器の混み具合ではなく台本の長さで決まると実測で出たら、
retry ではなく**コマ数の側**を切ること（そのときこの検査は落として構いません）。
"""

from __future__ import annotations

import json

from datetime import datetime, timezone

from scripts import ahead_sweep


def _ledger(tmp_path, rows):
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / ahead_sweep.REBAKE_LEDGER).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return tmp_path


def _row(kind: str, rc: int, vid: str = "V1", sha: str = "s1") -> dict:
    return {"at": "2026-09-04T15:09:06+09:00", "kind": kind,
            "video_id": vid, "topic": "t", "sha": sha, "rc": rc}


def test_時間切れの回数を数える(tmp_path):
    _ledger(tmp_path, [_row("done", 124), _row("late", 124), _row("done", 0),
                       _row("done", 124, vid="V2")])
    assert ahead_sweep.rebake_timeouts("V1", "s1", root=tmp_path) == 2
    assert ahead_sweep.rebake_timeouts("V2", "s1", root=tmp_path) == 1
    assert ahead_sweep.rebake_timeouts("V9", "s1", root=tmp_path) == 0


def test_時間切れの_done_は焼いたに数えない(tmp_path, monkeypatch):
    """**この検査が本体。** 印が在って `done`(rc=124) が1行 でも、もう一度 焼けること。"""
    marks = tmp_path / "marks"
    marks.mkdir()
    (marks / "V1-s1").write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: marks)
    monkeypatch.setattr(ahead_sweep, "rebake_died", lambda *a, **k: False)
    _ledger(tmp_path, [_row("done", 124)])
    now = datetime.now(timezone.utc)
    assert ahead_sweep.rebake_attempted("V1", "s1", now=now, root=tmp_path) is False


def test_時間切れが上限まで続いたら焼いたに数える(tmp_path, monkeypatch):
    """**毎回 90分 を捨て続けないこと。** 上限を超えたら台本の側を直させる。"""
    marks = tmp_path / "marks"
    marks.mkdir()
    (marks / "V1-s1").write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: marks)
    monkeypatch.setattr(ahead_sweep, "rebake_died", lambda *a, **k: False)
    _ledger(tmp_path, [_row("done", 124)] * ahead_sweep.REBAKE_TIMEOUT_RETRIES)
    now = datetime.now(timezone.utc)
    assert ahead_sweep.rebake_attempted("V1", "s1", now=now, root=tmp_path) is True


def test_時間切れでない_done_は今までどおり焼いたに数える(tmp_path, monkeypatch):
    """**緩めていないこと。** verify の赤で落ちた回は、今までどおり二度 焼きません。"""
    marks = tmp_path / "marks"
    marks.mkdir()
    (marks / "V1-s1").write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: marks)
    monkeypatch.setattr(ahead_sweep, "rebake_died", lambda *a, **k: False)
    _ledger(tmp_path, [_row("done", 1)])
    now = datetime.now(timezone.utc)
    assert ahead_sweep.rebake_attempted("V1", "s1", now=now, root=tmp_path) is True


def test_時間切れの返り値は124のまま():
    """`_run_out()` が時間切れで返す値と、ここで見る値が**同じ所から来ていること**。"""
    src = (ahead_sweep.ROOT / "scripts" / "ahead_sweep.py").read_text(encoding="utf-8")
    assert "return 124, " in src, "`_run_out` の時間切れの返り値が変わりました"
    assert ahead_sweep.REBAKE_TIMEOUT_RC == 124
