"""**長尺の詰め直しが、その回の投稿を止めないこと**（2026-08-26 に踏んで足した）。

## 何を踏んだか

`batch_build._pack_long_form()` は `reschedule._update` を呼びます。
あれは**日枠の 403 で `SystemExit` を上げます** —— `SystemExit` は
`BaseException` なので、**`except Exception` を素通り**します。

最初の実装は `except Exception` しか持っていませんでした。つまり
**更新の袋が閉じている窓では、この段から `batch_build` の外まで抜けて、
その回は1本も作らずに終わります。**

`docs/GOAL.md`（と `CLAUDE.md` の「4. 投稿を途切れさせないこと」）は
**投稿が途切れるのが最大の損失**と書いています。
**詰め直しは「あれば良いもの」で、投稿を止める権利はありません。**

実際、`tests/test_upload_cap_window.py` の
`test_batch_build_refuses_to_generate_when_the_window_is_closed` が
これを捕まえました（`batch_build.main()` が 1 を返さず `SystemExit` で落ちた）。

## 隣も数えました（**1件で終わらせない**）

同じ形を持ちうる隣の段を全部 見ました:

    scripts/live_slots.py:434        `except SystemExit` **あり**
    scripts/queue_lag.py:927         `except SystemExit` **あり**
    scripts/refresh_thumbnail.py     `push_missing()` を直接 呼ぶので上げない

**穴があったのはこの段だけ**でした（隣は先の回が既に塞いでいます）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("bb_pack", ROOT / "scripts" / "batch_build.py")
bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bb)


def _one_move(monkeypatch):
    """詰める本が1本ある状態にして、`_update` だけを差し替えられるようにする。"""
    from datetime import datetime, timedelta, timezone
    JST = timezone(timedelta(hours=9))
    plan = [{"id": "V1", "topic": "t",
             "old": datetime(2026, 9, 30, 20, 0, tzinfo=JST),
             "new": datetime(2026, 9, 1, 20, 0, tzinfo=JST)}]
    from scripts import reschedule
    monkeypatch.setattr(reschedule, "long_pack_plan", lambda *a, **k: plan)
    from src import uploader
    monkeypatch.setattr(uploader, "_service", lambda *a, **k: object())
    monkeypatch.setattr(uploader, "base_status", lambda *a, **k: {})
    return reschedule


def test_system_exit_from_update_does_not_escape(monkeypatch, capsys):
    """**日枠切れの `SystemExit` を、この段の外へ出さないこと。**"""
    reschedule = _one_move(monkeypatch)

    def boom(*a, **k):
        raise SystemExit("**V1 の予約は、いま外せません（日枠切れ）。**")

    monkeypatch.setattr(reschedule, "_update", boom)
    bb._pack_long_form()                       # 例外が漏れたらこの検査が落ちます
    assert "止めます" in capsys.readouterr().out


def test_ordinary_exception_does_not_escape_either(monkeypatch, capsys):
    """ふつうの例外でも同じ（**投稿は続けること**）。"""
    reschedule = _one_move(monkeypatch)
    monkeypatch.setattr(reschedule, "_update",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("網が切れた")))
    bb._pack_long_form()
    assert "止めます" in capsys.readouterr().out


def test_no_plan_means_no_service_call(monkeypatch):
    """**動かす本が0本なら、口を1回も叩かないこと**（単位を捨てないため）。"""
    from scripts import reschedule
    from src import uploader
    monkeypatch.setattr(reschedule, "long_pack_plan", lambda *a, **k: [])
    called = []
    monkeypatch.setattr(uploader, "_service", lambda *a, **k: called.append(1))
    bb._pack_long_form()
    assert called == [], "計画が空なのに口を叩いています"
