"""`status._channel_main` が「空で正常に返る」道を塞いだことの検査（2026-08-17）。

## なぜ検査するか（**この回が実際に踏んでいます**）

`_channel_main` には長らく、`channel_video_ids` の直後にこう書いてありました:

    ids = channel_video_ids(youtube, uploads)
    if not ids:
        print("動画がありません")
        return 0

**控えで補うブロックは、その1行下**にありました。つまり **`ids` が空のとき、
控えは構造上いちども走れません。** 控えを足した理由が「2つの口が同時に欠ける
ことがある」なのに、**本当に両方欠けた回だけ、その控えに手が届かない。**

そして `return 0` が道連れにするのは表ではありません。`print_local_sections()`
はこの関数の下のほうで呼ばれるので、**手段の台帳・期限の来た前提・テーマ在庫・
警告の当たり率・消費の速さが丸ごと消えます。** 2026-08-17 06:4x の実測で、
`status.py` の出力は **191行 → 10行**でした。

2026-08-16 11:5x の回は `main` 側に `try` を入れてこれを塞いだつもりでしたが、
**塞がったのは「例外で落ちる道」だけ**です。**「空で正常に返る道」は残りました** ——
同じ節の中で片方だけ、の9回目。

## 検査していること

1. **控えに行があれば、口が両方空でも `ids` は空にならない**（控えが効く）
2. **口も控えも空なら、黙って 0 を返さず例外にする** ——
   `main` 側の `except` が拾い、手元の節を全部出す道に入るため
3. **`main` は、その例外を握って手元の節を出し、0 を返す**（回を止めない）

**故障注入は両向き**: 控えが読めない回（例外を投げる `ledger_rows`）も通します。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import status  # noqa: E402


class _Youtube:
    """`channels().list()` だけ答える最小の口。**動画は1本も返しません。**"""

    def channels(self):
        return self

    def list(self, **kw):
        return self

    def execute(self):
        return {"items": [{
            "snippet": {"title": "テスト"},
            "statistics": {"subscriberCount": "9", "viewCount": "14300"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}},
        }]}


def _patch(monkeypatch, *, ledger, ids=()):
    """口を「空」に、控えを `ledger` に差し替える。"""
    import src.history as history
    import src.dupes as dupes

    monkeypatch.setattr(status, "_service", lambda: _Youtube())
    monkeypatch.setattr(history, "channel_video_ids", lambda *a, **k: list(ids))
    if isinstance(ledger, Exception):
        def _boom():
            raise ledger
        monkeypatch.setattr(dupes, "ledger_rows", _boom)
    else:
        monkeypatch.setattr(dupes, "ledger_rows", lambda: list(ledger))


def test_口が空でも控えがあれば拾う(monkeypatch, capsys):
    """**控えのブロックが、`ids` が空のときに実際に走ること。**

    ここが本体です。以前は `return 0` が上にあったので走りませんでした。
    """
    _patch(monkeypatch, ledger=[{"id": "aaa"}, {"id": "bbb"}])

    # 控えで `ids` が埋まると、次は `videos().list()` に進みます。
    # この口はそれを持っていないので `AttributeError` で落ちる ——
    # **「動画がありません」で 0 を返す道には入っていない**ことの証拠です。
    with pytest.raises(Exception) as got:
        status._channel_main()

    out = capsys.readouterr().out
    assert "[控え] 口から返らなかった 2本を足しました" in out
    assert "動画がありません" not in out
    assert "RuntimeError" not in type(got.value).__name__ or "控えも空" not in str(got.value)


def test_口も控えも空なら例外にする(monkeypatch, capsys):
    """**黙って 0 を返さないこと。** 返すと `main` の `except` に入れません。"""
    _patch(monkeypatch, ledger=[])

    with pytest.raises(RuntimeError) as got:
        status._channel_main()

    assert "控えも空" in str(got.value)


def test_控えが読めない回も例外にする(monkeypatch, capsys):
    """**故障注入。** 控え側が壊れていても、0 を返して黙らないこと。"""
    _patch(monkeypatch, ledger=OSError("控えが壊れています"))

    with pytest.raises(RuntimeError):
        status._channel_main()

    assert "[控え] 読めませんでした" in capsys.readouterr().out


def test_main_は例外を握って手元の節を出す(monkeypatch, capsys):
    """**回を止めないこと。** `main` は 0 を返し、手元の節を出す。"""
    _patch(monkeypatch, ledger=[])
    called: list[str] = []
    monkeypatch.setattr(status, "print_local_sections", lambda: called.append("local"))
    monkeypatch.setattr(status, "_print_analytics_recap", lambda: called.append("recap"))

    assert status.main() == 0
    assert called == ["local", "recap"]
    assert "外の口が落ちました" in capsys.readouterr().out
