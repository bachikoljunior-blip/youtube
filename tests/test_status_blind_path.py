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
    """**回を止めないこと。** `main` は 0 を返し、手元の節を出す。

    **2026-08-18 に1件足しました**（`analytics`）。ここは長らく
    `["local", "recap"]` だけを期待していて、**その期待どおりに動くことが
    欠陥そのもの**でした（下の検査の註）。
    """
    _patch(monkeypatch, ledger=[])
    called: list[str] = []
    monkeypatch.setattr(status, "print_analytics_sections",
                        lambda *a, **k: called.append("analytics"))
    monkeypatch.setattr(status, "print_local_sections", lambda: called.append("local"))
    monkeypatch.setattr(status, "_print_analytics_recap", lambda: called.append("recap"))

    assert status.main() == 0
    assert called == ["analytics", "local", "recap"]


def test_日枠が落ちた回でも_Analytics_の節を出す(monkeypatch, capsys):
    """**枠は2つあり、別々に閉じます**（2026-08-18 01:3x に実測して足した）。

        Data API（`youtube/v3`）  10,000単位/日  → 読みが 403
        YouTube Analytics（`v2`） **別枠**      → **403 のあいだも通る**

    受け皿は長らく「**チャンネル側の数字はこの回では出ません**」と言って
    `print_local_sections` だけを呼んでいました。**Data API の日枠は
    太平洋時間の0時に戻る＝1日のうち十数時間がこの状態**で、
    その間の子は全部「チャンネルは読めない回」として回っています。

    実測（日枠が 403 の最中に叩いた）: `fetch_traffic` **通る** ／
    `scan.collect` **通る** ／ `fetch_subscribers` **通る**。
    落ちたのは `fetch_report` だけで、理由は中身ではなく**題名**
    （`videos.list` ＝ Data API で引いている）。

    **文言のほうも検査します。** 数字が出るようになっても、
    「出ません」と書いてあれば次の子は読みにいきません
    （**値は正しいのに字が嘘、の3件目**）。
    """
    _patch(monkeypatch, ledger=[])
    monkeypatch.setattr(status, "print_analytics_sections",
                        lambda *a, **k: print("=== 流入経路（テスト） ==="))
    monkeypatch.setattr(status, "print_local_sections", lambda: None)
    monkeypatch.setattr(status, "_print_analytics_recap", lambda: None)

    assert status.main() == 0
    out = capsys.readouterr().out
    assert "=== 流入経路（テスト） ===" in out
    assert "チャンネル側の数字はこの回では出ません" not in out
    assert "Analytics は別枠" in out


def test_節の一覧は1か所にしかない(monkeypatch, capsys):
    """**成功する回も、落ちた回も、同じ関数を呼ぶこと。**

    節の一覧を2か所に書くと、次に節を足した回が**片方だけ書き忘れます**
    （このリポジトリで通算11回起きている形）。だから
    `_channel_main` は自分で並べず、`print_analytics_sections` を**呼ぶだけ**。

    ここで見ているのは「呼んだかどうか」です。**中身を写した検査にしないこと** ——
    写すと、この検査そのものが3か所目になります。
    """
    _patch(monkeypatch, ledger=[{"id": "aaa"}])
    called: list[str] = []
    monkeypatch.setattr(status, "print_analytics_sections",
                        lambda *a, **k: called.append("analytics"))
    monkeypatch.setattr(status, "print_local_sections", lambda **k: called.append("local"))

    # 控えで `ids` が埋まると `videos().list()` へ進み、この口は持っていないので落ちます。
    # **そこまで進めば十分**（この検査の主題は、その手前の並べ方ではありません）。
    with pytest.raises(Exception):
        status._channel_main()

    # 落ちる場所より後ろなので呼ばれていなくてよい。
    # **見たいのは「`_channel_main` が自分で節を並べていない」ことのほう**です。
    import inspect
    # **`inspect.getsource` を直に呼ばないこと**（2026-08-27 に踏んだ）。
    #     20分の走りの最中に同じ木へ `git merge` を撃つと、ファイルが下へずれ、
    #     **import 時の行番号で別の場所を切り出します** —— この検査が
    #     **コードは無傷のまま赤くなります**（実測: 兄弟が `scripts/status.py` に
    #     60行 入れた回。単体では緑なので「気まぐれ」と読まれます）。
    #     `conftest.source_of()` が、そのときは**そう言って**落とします。
    from conftest import source_of
    src = source_of(status._channel_main, "_channel_main")
    assert "print_analytics_sections" in src
    assert "fetch_traffic" not in src, "節の中身が `_channel_main` に写っています（2か所目）"
    assert "print_where_watched" not in src, "節の一覧が `_channel_main` に写っています（2か所目）"


def test_維持率が落ちても他の節を巻き込まない(monkeypatch, capsys):
    """**`fetch_report` だけは日枠で落ちます**（題名を `videos.list` で引くため）。

    その1本が、同じ関数の中の**他の4節を道連れにしないこと。**
    道連れになると、直した意味が半分消えます（走査も流入経路も出ない）。
    """
    def _boom(*a, **k):
        raise RuntimeError("403 quotaExceeded")

    monkeypatch.setattr(status, "print_retention", _boom)
    monkeypatch.setattr(status, "print_channel_signals", lambda *a, **k: print("=== 日次 ==="))
    monkeypatch.setattr(status, "print_where_watched", lambda *a, **k: print("=== 場所 ==="))

    import src.analytics as _an
    monkeypatch.setattr(_an, "fetch_traffic", lambda d: [
        {"insightTrafficSourceType": "SHORTS", "views": 5, "estimatedMinutesWatched": 1}])
    import src.scan as _scan
    monkeypatch.setattr(_scan, "collect", lambda: {"at": "x", "values": {}})
    monkeypatch.setattr(_scan, "report", lambda *a, **k: print("=== 全走査 ==="))
    monkeypatch.setattr(_scan, "save", lambda *a, **k: None)

    status.print_analytics_sections(7)

    out = capsys.readouterr().out
    assert "=== 流入経路" in out, "維持率より前の節が出ていません"
    assert "=== 日次 ===" in out, "維持率が後ろの節を道連れにしています"
    assert "=== 場所 ===" in out, "維持率が後ろの節を道連れにしています"
    assert "=== 全走査 ===" in out, "維持率が走査を道連れにしています"
    assert "維持率が落ちました" in out, "落ちたことが黙って消えています"
