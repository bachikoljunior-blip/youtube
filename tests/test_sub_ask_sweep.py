"""**登録の依頼が、既存の本にも掛かり続けることを見る**（`sub_rate` の腕）。

## なぜ要るか（2026-09-04・最適化の回）

`src/sub_ask.py` は 2026-09-03 に足され、`pipeline`／`uploader` から
**これから作る本**には掛かっていました。ところが**すでに上がっている本**へ掛ける
`apply_to_video()` は動画IDを手で1本ずつ渡す形しか無く、**repo のどこからも
呼ばれていませんでした。** 実測（2026-09-04）: 上がっている 249本 のうち再生が
動いている 36本 の**全部**に依頼が入っておらず、**いまの再生/日 の 100%** が
依頼の無い本から来ていました。

この検査が見ているのは2つだけです:

1. `rank_by_traffic()` が**総再生ではなく「いまの再生/日」**で並べること
   （実測で順が逆になる: 総再生 1,441回 の本が 0.9回/日、136回 の本が 67.0回/日）。
2. `ahead_sweep.main()` の**毎周の口**から `sub_ask_pending()` が呼ばれること。
   この輪で落ちるのは「回が憶えておく」形のほうなので、口が外れたら赤にします。

**覆る条件**: `sub_ask.HEAD` を空にして依頼そのものを畳んだとき
（前提が外れた後の姿）。そのときは `sweep()` が 0単位 で戻るので、
ここは 2. だけ残して 1. を消してよい。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import sub_ask  # noqa: E402


def test_rank_by_traffic_orders_by_current_speed_not_total(tmp_path):
    """総再生が多くても、**いま止まっている本**は後ろへ回ること。"""
    src = tmp_path / "views.jsonl"
    src.write_text(
        # 総再生 1000回 だが、24時間で 0回 しか増えていない本
        '{"at":"2026-09-01T00:00:00Z","id":"stale","views":1000}\n'
        '{"at":"2026-09-03T00:00:00Z","id":"stale","views":1000}\n'
        # 総再生 100回 だが、2日で 100回 増えている本
        '{"at":"2026-09-01T00:00:00Z","id":"hot","views":0}\n'
        '{"at":"2026-09-03T00:00:00Z","id":"hot","views":100}\n',
        encoding="utf-8",
    )
    ranked = sub_ask.rank_by_traffic(src)
    assert [vid for _, vid in ranked] == ["hot", "stale"], ranked
    assert ranked[0][0] == 50.0        # 100回 / 2日
    assert ranked[1][0] == 0.0


def test_rank_by_traffic_skips_videos_with_one_point(tmp_path):
    """点が1つの本は**測れない**ので入れないこと（0回/日 と嘘をつかない）。"""
    src = tmp_path / "views.jsonl"
    src.write_text('{"at":"2026-09-03T00:00:00Z","id":"only","views":5}\n',
                   encoding="utf-8")
    assert sub_ask.rank_by_traffic(src) == []


def test_with_head_is_idempotent():
    """何度掛けても増えないこと（毎周 掛かるので、ここが崩れると説明欄が伸び続ける）。"""
    once = sub_ask.with_head("本文")
    assert sub_ask.with_head(once) == once
    assert once.count(sub_ask.HEAD_MARK) == 1


def test_sweep_does_nothing_when_head_is_emptied(monkeypatch):
    """前提が外れて `HEAD` を空にしたら、**API を1単位も使わない**こと。"""
    monkeypatch.setattr(sub_ask, "HEAD", "")
    called = []
    monkeypatch.setattr(sub_ask, "rank_by_traffic",
                        lambda *a, **k: [(9.0, "vid1")])

    class Boom:
        def videos(self):                      # pragma: no cover - 呼ばれたら赤
            called.append(1)
            raise AssertionError("HEAD が空なのに API を撃ちました")

    assert sub_ask.sweep(service=Boom()) == 0
    assert not called


def test_ahead_sweep_calls_sub_ask_every_round():
    """**毎周の口から呼ばれること。** ここが外れると、掛け直しは回の裁量に戻ります。"""
    import ahead_sweep

    assert hasattr(ahead_sweep, "sub_ask_pending")
    body = (ROOT / "scripts" / "ahead_sweep.py").read_text(encoding="utf-8")
    main_src = body.split("def main(", 1)[1]
    assert "sub_ask_pending(now" in main_src, "main() が毎周 呼んでいません"


def test_sub_ask_pending_reports_when_quota_is_closed(monkeypatch):
    """日枠が尽きている回は、**撃たずに1行 残す**こと（次の窓の回が拾える形）。"""
    import ahead_sweep
    from src import upload_cap

    class Closed:
        open = False

    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: Closed())
    fired = []
    line = ahead_sweep.sub_ask_pending(sweep=lambda **k: fired.append(k))
    assert "日枠" in line
    assert not fired
