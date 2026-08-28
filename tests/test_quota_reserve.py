"""**計測のぶんの単位を、書き込みが食い切らないこと**（2026-08-28 に足した）。

## なぜ要るか（実測）

窓 08/27 07:00Z（＝ **16:00 JST**）〜 の `data/day_quota.jsonl`:

    16:11 JST  最初の `videos.update`
    16:47 JST  **最初の 403**（通った 183回 ＝ 9,150単位・枠は 10,000）
    ↓
    **残りの 23.2時間、読みも書きも 403**（403 を 194回 観測）

`config/hypotheses.yaml` の 08-28 の前提が要る読みは
**「22:00 JST 以降に `python scripts/snapshot.py` を1回」＝ 4単位**です。
**9,150単位 を 47分 で焼いて、そのあと 4単位 が撃てません。**

`eta.py` は毎回「**軌跡の腕が動くのは、前提を1件閉じたときだけ**」と印字します。
つまり **到達日を動かす唯一の操作が、到達日を 0日 しか動かさない操作に
先を越されて、毎日 23時間 不可能になっていました**（実際に 08/27 夕・
08/28 未明 と **2回 続けて**、期限の来た前提が閉じずに終わっています）。

## この検査が見ているもの

1. **推測では止めないこと。** 枠の実測（`measured_budget()["floor"]`）が
   無い窓では、必ず `None`（＝撃ってよい）
2. 実測があり、残りが `RESERVE_UNITS` を切ったら止めること
3. **止めるのは書き込みだけ。** `videos.insert`（投稿）はこの枠を1単位も
   使わないので、**投稿は1本も減りません**（`UNIT_COST` の註）
4. 書き込みの入口（`reschedule._update` / `uploader._set_thumbnail`）が、
   撃つ前に必ずここを通ること

## 覆る条件

`videos.insert` が同じ 403 で落ちるようになったら（＝枠が1つに統合された）、
この関門は**投稿を減らす側に効きはじめます。**そのときは大きさを測り直すこと。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import upload_cap                                     # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_枠の実測が無い窓では止めない(monkeypatch):
    """**推測で書き込みを止めないこと。** 外す向きは、今までどおり 403 を見る側。"""
    monkeypatch.setattr(upload_cap, "measured_budget",
                        lambda now=None: {"floor": 0, "spent": 99_999, "left": 0})
    assert upload_cap.reserve_hold() is None


def test_残りが計測のぶんを切ったら止める(monkeypatch):
    monkeypatch.setattr(
        upload_cap, "measured_budget",
        lambda now=None: {"floor": 10_000,
                          "spent": 10_000 - upload_cap.RESERVE_UNITS, "left": 0})
    held = upload_cap.reserve_hold()
    assert held and "計測" in held


def test_まだ余っていれば止めない(monkeypatch):
    monkeypatch.setattr(
        upload_cap, "measured_budget",
        lambda now=None: {"floor": 10_000,
                          "spent": 10_000 - upload_cap.RESERVE_UNITS - 1, "left": 1})
    assert upload_cap.reserve_hold() is None


def test_外せること(monkeypatch):
    """**逃げ道は残すこと。** 使った回は理由を JOURNAL に。"""
    monkeypatch.setattr(upload_cap, "measured_budget",
                        lambda now=None: {"floor": 10_000, "spent": 10_000, "left": 0})
    monkeypatch.setenv("YT_NO_RESERVE", "1")
    assert upload_cap.reserve_hold() is None


#: **日枠を焼く書き込み**（`src/upload_cap.UNIT_COST` の 50単位 の2つ）。
#: `X.videos().update(...)` / `X.thumbnails().set(...)` の形で拾います。
WRITE_CALLS = {("videos", "update"), ("thumbnails", "set")}


def _write_sites() -> list[tuple[Path, int, ast.FunctionDef | None, str]]:
    """**木を歩いて、書き込みの入口を全部 数え上げる。**（`src/` と `scripts/`）

    返り: (ファイル, 行, 囲っている関数（無ければ None）, 呼び出しの名前)

    **手で並べないこと。** この検査は 2026-08-28 に、入口を2つ
    （`reschedule._update` / `uploader._set_thumbnail`）だけ字で並べていました。
    そのとき木には **5つ**あり、**残る3つは素通り**でした ——
    しかもそのうち `scripts/refresh_thumbnail.py` は
    `scripts/batch_build.py` が**毎周 直接 呼ぶ**、いちばん熱い入口です。
    自分の docstring は「**入口ごとに1回ずつ。どちらかが抜けると、
    そちらから全部 焼けます**」と書いてあり、**その「どちらか」が
    2つしか無いと決めていたのは、この検査自身**でした。

    数え上げにしておけば、**入口が6つ目になった日に、ここが落ちて教えます。**
    """
    out = []
    for base in ("src", "scripts"):
        for path in sorted((ROOT / base).glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                                # pragma: no cover
                continue
            funcs = [n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not isinstance(fn, ast.Attribute):
                    continue
                inner = fn.value
                if not (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Attribute)):
                    continue
                name = (inner.func.attr, fn.attr)
                if name not in WRITE_CALLS:
                    continue
                # **いちばん内側の関数**（入れ子は狭いほうが入口）
                owner = None
                for f in funcs:
                    if (f.lineno <= node.lineno
                            and node.lineno <= (f.end_lineno or f.lineno)
                            and (owner is None or f.lineno > owner.lineno)):
                        owner = f
                out.append((path, node.lineno, owner, f"{name[0]}.{name[1]}"))
    return out


def test_書き込みの入口を数え上げられること():
    """**空になったら、この検査は何も守っていません。**（呼び出しの形が変わった合図）"""
    sites = _write_sites()
    assert len(sites) >= 3, (
        f"`videos().update` / `thumbnails().set` が {len(sites)}件 しか見つかりません。"
        " 呼び出しの書き方が変わったなら `_write_sites()` を直すこと ——"
        " **見つからないことを『入口が無い』と読まないこと。**")


def test_書き込みの入口が全部_関門を通っていること():
    """**入口ごとに1回ずつ。1つ抜けると、そこから全部 焼けます。**

    実測（2026-08-28。この検査が2つだけ見ていたときの木）:

        scripts/reschedule.py        videos.update    ✓ 門あり
        src/uploader.py              thumbnails.set   ✓ 門あり
        scripts/refresh_thumbnail.py thumbnails.set   ✗ **`batch_build` が毎周 呼ぶ**
        scripts/link_longform.py     videos.update    ✗
        scripts/retitle.py           videos.update    ✗
    """
    bad = []
    for path, line, owner, name in _write_sites():
        if owner is None:                       # 段の外＝モジュールの字ぜんぶを見る
            body = path.read_text(encoding="utf-8")
        else:
            src = path.read_text(encoding="utf-8").splitlines()
            body = "\n".join(src[owner.lineno - 1:line])
        if "reserve_hold" not in body:
            bad.append(f"{path.relative_to(ROOT)}:{line} {name}"
                       f"（{owner.name if owner else '<module>'}）")
    assert not bad, (
        "**日枠を焼く書き込みが、`upload_cap.reserve_hold()` を見ずに撃っています**:\n  "
        + "\n  ".join(bad)
        + "\n\n残しているのは**前提を閉じる読み**です（`videos.list` は 1単位。"
          "`eta.py`: 軌跡の腕が動くのは前提を1件 閉じたときだけ）。"
          "\n**逃げ道は `YT_NO_RESERVE=1`** —— 門を外すのではなく、そちらを使うこと。")


def test_投稿そのものは止めないこと():
    """**`videos.insert` に関門を置かないこと** —— 別の枠から出ています
    （実測 08/17 以後3度）。置くと `docs/GOAL.md`「投稿が途切れるのが
    最大の損失」に真っ向から反します。
    """
    up = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
    for chunk in up.split("videos().insert(")[:-1]:
        tail = chunk.rsplit("def ", 1)[-1]
        assert "reserve_hold()" not in tail, (
            "`videos.insert` の手前で `reserve_hold()` を見ています。"
            "**投稿はこの枠を1単位も使いません**")
