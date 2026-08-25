"""**50単位の手が、1,600単位の投稿より先に撃たれること。**

## この検査が守っているもの（2026-08-26・最適化の回）

`scripts/batch_build.py` の `_push_thumbnails_first()` は、2026-08-17 に
**同じ穴**を塞いだものです ——

> `thumbnails.set` は 50単位しか要らないのに、**いつも投稿の後ろに並んでいた**ので
> 一度も順番が回ってきませんでした。**一覧が悪いのではありません。
> 押せる時刻に、押す手順が無かっただけです。**

`videos.update`（同じ50単位）を撃つ道具が **2つとも同じ所に立っていました。**
ちがいは1つで、**そもそも手順が無い** —— 申し送りに
「**16:00 JST を過ぎたら撃つこと**」と書いてあるだけでした。
**申し送りでは直りません**（次に起きた回が16時をまたぐとは限らず、
またいでも投稿のほうが先に窓を空にします）。実測 2026-08-26 03:1x:

    live_slots  **6手 ＝ 300単位**   `stat_split 処置(後)` 13本 → **16本（要16）**
    queue_lag   **26手 ＝ 2,600単位** 判定が **合計8日** 手前へ
    同じ窓で投稿に **17,600単位**、403 を **22回** 観測

**ここが見るのは順番と、撃たない条件です:**

    順番        死に枠の逃がし → 入れ替え → サムネイル → 投稿
    撃たない    日枠の 403 をこの窓で観測している
    撃たない    取り戻せる日数が 0 ／ 手が 0（単位を捨てない）
    落ちても    投稿は続く（**逆にしないこと**）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import batch_build as B  # noqa: E402
from scripts import live_slots as L  # noqa: E402
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


class _FakeBoard:
    def __init__(self, moves: int) -> None:
        self.moves = [("v", None)] * moves


def _arm(monkeypatch, *, open_: bool = True, swaps: int = 0, days: int = 0,
         rescues: int = 0) -> dict[str, list]:
    """撃たれたら記録する世界を作る。**本物の口は一度も呼ばれません。**"""
    fired: dict[str, list] = {"queue_lag": [], "live_slots": []}
    monkeypatch.setattr(upload_cap, "day_quota",
                        lambda now=None: type("Q", (), {"open": open_})())
    monkeypatch.setattr(Q, "Plan", lambda *a, **k: _FakePlan(swaps, days))
    monkeypatch.setattr(Q, "main",
                        lambda argv=None: fired["queue_lag"].append(argv) or 0)
    monkeypatch.setattr(L, "_rows", lambda: [])
    monkeypatch.setattr(L, "Board", lambda *a, **k: _FakeBoard(rescues))
    monkeypatch.setattr(L, "plan", lambda board: [])
    monkeypatch.setattr(L, "main",
                        lambda argv=None: fired["live_slots"].append(argv) or 0)
    return fired


# ---- 日枠の門 -------------------------------------------------------------

def test_日枠が尽きていたら_どちらも撃たない(monkeypatch):
    fired = _arm(monkeypatch, open_=False, swaps=26, days=8, rescues=6)
    B._pull_verdicts_first()
    assert fired == {"queue_lag": [], "live_slots": []}, \
        "**403 を観測した窓で撃っています。**止まるのは投稿のほうです"


# ---- (2) 入れ替え ---------------------------------------------------------

def test_取り戻せる日数が0なら撃たない(monkeypatch):
    fired = _arm(monkeypatch, swaps=26, days=0)
    B._pull_verdicts_first()
    assert fired["queue_lag"] == [], "**0日 の入れ替えに 2,600単位 使っています**"


def test_手が無ければ撃たない(monkeypatch):
    fired = _arm(monkeypatch, swaps=0, days=0)
    B._pull_verdicts_first()
    assert fired["queue_lag"] == []


def test_日数が動くなら撃つ(monkeypatch):
    fired = _arm(monkeypatch, swaps=26, days=8)
    B._pull_verdicts_first()
    assert fired["queue_lag"] == [["--apply"]], (
        "**撃っていません。**これが無いと、投稿が窓を空にしてから順番が回ります")


# ---- (1) 死に枠の逃がし ---------------------------------------------------

def test_逃がす本が無ければ撃たない(monkeypatch):
    fired = _arm(monkeypatch, rescues=0)
    B._pull_verdicts_first()
    assert fired["live_slots"] == []


def test_逃がす本があれば撃つ(monkeypatch):
    fired = _arm(monkeypatch, rescues=6)
    B._pull_verdicts_first()
    assert fired["live_slots"] == [["--apply"]], (
        "**撃っていません。**標本が足りない群は、判定できる日そのものが出ません")


def test_逃がしは_広い手を撃たない(monkeypatch):
    """`--all` は A/B に限らず全部を動かす広い手。**自動では撃たないこと。**"""
    fired = _arm(monkeypatch, rescues=6)
    B._pull_verdicts_first()
    assert all("--all" not in (a or []) for a in fired["live_slots"]), \
        "`--all` を自動で撃っています。**人が見て撃つ範囲です**"


def test_逃がしが先で_入れ替えが後(monkeypatch):
    """標本をそろえてからでないと、**手前へ倒す日付そのものが出ません。**"""
    order: list[str] = []
    _arm(monkeypatch, swaps=26, days=8, rescues=6)
    monkeypatch.setattr(L, "main",
                        lambda argv=None: order.append("live_slots") or 0)
    monkeypatch.setattr(Q, "main",
                        lambda argv=None: order.append("queue_lag") or 0)
    B._pull_verdicts_first()
    assert order == ["live_slots", "queue_lag"], f"順が違います: {order}"


# ---- 落ちても投稿は止めない -----------------------------------------------

def test_逃がしが落ちても_入れ替えは撃つ(monkeypatch):
    fired = _arm(monkeypatch, swaps=26, days=8, rescues=6)

    def boom(argv=None):
        raise RuntimeError("口が落ちた")

    monkeypatch.setattr(L, "main", boom)
    B._pull_verdicts_first()
    assert fired["queue_lag"] == [["--apply"]], \
        "**片方が落ちて、もう片方まで止まりました。**独立に撃つこと"


def test_落ちても投稿は止めない(monkeypatch):
    _arm(monkeypatch, swaps=26, days=8, rescues=6)

    def boom(argv=None):
        raise RuntimeError("口が落ちた")

    monkeypatch.setattr(Q, "main", boom)
    monkeypatch.setattr(L, "main", boom)
    B._pull_verdicts_first()   # 例外が外へ出たら、この行で落ちます


# ---- 順番（構造） ---------------------------------------------------------

def test_投稿より先に呼ばれている():
    """**順番がすべてです。**（逃がし → 入れ替え → サムネイル → 投稿）"""
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    call = src.index("    _pull_verdicts_first()\n")
    thumb = src.index("    _push_thumbnails_first()\n")
    assert call < thumb, (
        "サムネイルより後ろに居ます。**同じ50単位なら、到達日を動かすほうが先**です")
    # 投稿は `pick()` のあと。ここより前に居ること
    assert call < src.index("    topics = pick("), \
        "**投稿より後ろに居ます。**窓を空にしてから順番が回ります"


def test_投稿の本数枠で落ちても_50単位の手は撃たれる():
    """**枠は2つあります。**片方が閉じても、もう片方は開いています。

    `src/upload_cap.py` の頭:

        Data API の日枠   10,000単位  403 quotaExceeded     ← 50単位の手を止めるのはこちら
        投稿の本数枠      1日92本     429 rateLimitExceeded  ← `videos.insert` だけの枠

    ここは長らく `cap.remaining <= 0` の `return 1` の**後ろ**にありました ——
    つまり**「今日はもう92本 上げた」だけで、50単位の手まで丸ごと落ちて**いました。
    **`src/upload_cap.py` が「片方しか数えていませんでした」と書いた、その形です。**
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    call = src.index("    _pull_verdicts_first()\n")
    gate = src.index("        if cap.remaining <= 0:")
    assert call < gate, (
        "**投稿の本数枠（429）の `return` より後ろに居ます。**"
        "別の枠なので、ここで一緒に落ちてはいけません")


def test_取り戻せる日数を2か所で数えていない():
    """引き算は `Plan.gains()` の1か所。**印字と門がずれると、撃たなくなります。**"""
    src = (ROOT / "scripts" / "queue_lag.py").read_text(encoding="utf-8")
    assert src.count("(b - a).days") == 1, (
        "**日数の引き算が2か所にあります。**`gains()` だけが数えること")
