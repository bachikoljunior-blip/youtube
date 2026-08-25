"""**50単位の手が、1,600単位の投稿より先に撃たれること。**

## この検査が守っているもの（2026-08-26・最適化の回）

`scripts/batch_build.py` の `_push_thumbnails_first()` は、2026-08-17 に
**同じ穴**を塞いだものです ——

> `thumbnails.set` は 50単位しか要らないのに、**いつも投稿の後ろに並んでいた**ので
> 一度も順番が回ってきませんでした。**一覧が悪いのではありません。
> 押せる時刻に、押す手順が無かっただけです。**

`scripts/queue_lag.py --apply`（1回 50単位の `videos.update`）が、
**同じ所に立っていました。** ちがいは1つで、**そもそも手順が無い** ——
申し送りに「16時を過ぎたら撃つこと」と書くだけでした。
実測 2026-08-26 03:1x: **入れ替え 2,600単位 で判定が 8日 手前に倒れる**のに、
同じ窓で **投稿に 17,600単位** 使われ、403 を 22回 観測していました。

**ここが見るのは順番と、撃たない条件です:**

    順番        入れ替え → サムネイル → 投稿
    撃たない    日枠の 403 をこの窓で観測している
    撃たない    取り戻せる日数が 0（単位を捨てない）
    落ちても    投稿は続く（**逆にしないこと**）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import batch_build as B  # noqa: E402
from scripts import queue_lag as Q  # noqa: E402
from src import upload_cap  # noqa: E402


class _FakePlan:
    def __init__(self, swaps: int, days: int) -> None:
        self.swaps = [("a", "b")] * swaps
        self._days = days

    def improve(self, limit: int | None = None) -> None:  # noqa: ARG002
        pass

    def gain_days(self) -> int:
        return self._days


def _arm(monkeypatch, *, open_: bool, swaps: int, days: int) -> list:
    """撃たれたら記録する世界を作る。**本物の口は一度も呼ばれません。**"""
    fired: list = []
    monkeypatch.setattr(upload_cap, "day_quota",
                        lambda now=None: type("Q", (), {"open": open_})())
    monkeypatch.setattr(Q, "Plan", lambda *a, **k: _FakePlan(swaps, days))
    monkeypatch.setattr(Q, "main", lambda argv=None: fired.append(argv) or 0)
    return fired


def test_日枠が尽きていたら撃たない(monkeypatch):
    fired = _arm(monkeypatch, open_=False, swaps=26, days=8)
    B._pull_verdicts_first()
    assert fired == [], "**403 を観測した窓で撃っています。**止まるのは投稿のほうです"


def test_取り戻せる日数が0なら撃たない(monkeypatch):
    fired = _arm(monkeypatch, open_=True, swaps=26, days=0)
    B._pull_verdicts_first()
    assert fired == [], "**0日 の入れ替えに 2,600単位 使っています**"


def test_手が無ければ撃たない(monkeypatch):
    fired = _arm(monkeypatch, open_=True, swaps=0, days=0)
    B._pull_verdicts_first()
    assert fired == []


def test_日数が動くなら撃つ(monkeypatch):
    fired = _arm(monkeypatch, open_=True, swaps=26, days=8)
    B._pull_verdicts_first()
    assert fired == [["--apply"]], (
        "**撃っていません。**これが無いと、投稿が窓を空にしてから順番が回ります")


def test_落ちても投稿は止めない(monkeypatch):
    _arm(monkeypatch, open_=True, swaps=26, days=8)

    def boom(argv=None):
        raise RuntimeError("口が落ちた")

    monkeypatch.setattr(Q, "main", boom)
    B._pull_verdicts_first()   # 例外が外へ出たら、この行で落ちます


def test_投稿より先に呼ばれている():
    """**順番がすべてです。**（入れ替え → サムネイル → 投稿）"""
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    call = src.index("    _pull_verdicts_first()\n")
    thumb = src.index("    _push_thumbnails_first()\n")
    assert call < thumb, (
        "サムネイルより後ろに居ます。**同じ50単位なら、到達日を動かすほうが先**です")
    # 投稿は `pick()` のあと。ここより前に居ること
    assert call < src.index("    topics = pick("), \
        "**投稿より後ろに居ます。**窓を空にしてから順番が回ります"


def test_取り戻せる日数を2か所で数えていない():
    """引き算は `Plan.gains()` の1か所。**印字と門がずれると、撃たなくなります。**"""
    src = (ROOT / "scripts" / "queue_lag.py").read_text(encoding="utf-8")
    assert src.count("(b - a).days") == 1, (
        "**日数の引き算が2か所にあります。**`gains()` だけが数えること")
