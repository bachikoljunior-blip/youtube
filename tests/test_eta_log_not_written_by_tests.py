"""**検査は、本物の `data/eta.jsonl` に点を積まないこと**（2026-09-01 に測って足した）。

## なぜ要るか（実測）

`tests/conftest.py` の冒頭（2026-08-17）は、この repo が**通算7回**踏んだ形として
**「検査は、本物の台帳に書かないこと」**と書いています。
**`data/eta.jsonl` は、その自動の掛かりに入っていませんでした。**

実測 2026-09-01 —— `tests/test_long_surface_ceiling_named.py` を**1件**走らせると、
本物の `data/eta.jsonl` が **1点 増えます**（20:27・20:28 の2点 ＝ 993点目まで）。
あの検査は `eta.py` の `main()` を通すので、末尾の「積みました」がそのまま走ります。

## ここが壊れると何が起きるか（**統計の汚れでは済みません**）

この台帳は「**予測日が前の回から動いたか**」を出す唯一の資料です:

    `run_marker.py --ship` の `moves` の裏取り        ← 隣り合う2点の差
    `eta.py --reflect`「この回で動いた入力」          ← 隣り合う2点の差
    `scripts/trajectory.py` / `src/levers.py` の腕    ← 後ろから読む

検査の点が挟まると、**その回の作業の成績が、検査の成績に化けます。**
つまり「最適化されてんの？」に答える当の数が汚れます ——
`data/runs.jsonl` の `eta_days` は、ここから引いています。

## なぜ「呼ぶ側で気をつける」ではないのか

`scripts/run_marker.py` は 2026-08-20 に同じ形を踏み、`YT_SKIP_REFLECT` で
**反映の道だけ**塞ぎました。塞がっていないのは**予測そのものを撃つ道**で、
そちらは `eta.py` の `main()` を呼ぶ検査すべてが通ります。
`src/upload_cap._write_path` の註が同じ結論を書いています ——
**「関係のない検査に『台帳に気をつけろ』と約束させるのは無理なので、
書く側を機械で閉じます」。同じ傘に入れました**（`eta._log_path`）。

## 覆る条件

本物の台帳へ**わざと**積む検査が要るなら `YT_ETA_LOG_WRITE=1`。
そのときは理由を `docs/JOURNAL.md` に。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def eta():
    """`scripts/eta.py` は package の外なので、場所から読みます。"""
    spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_検査の中では本物の台帳を指さないこと(eta):
    """**この検査自身が `pytest` の中**なので、そのまま呼べば `None` のはず。"""
    assert os.environ.get("PYTEST_CURRENT_TEST"), "この検査は pytest の中で走ります"
    assert eta._log_path() is None, (
        "**検査が本物の `data/eta.jsonl` を指しています。**"
        " 1件 走らせるたびに点が1つ増え、`moves` の裏取りと `--reflect` の"
        "「動いた入力」が、検査の成績に化けます。")


def test_逃げ道を立てれば書けること(eta, monkeypatch):
    """**わざと積む道は残すこと。** 使った回は理由を JOURNAL に。"""
    monkeypatch.setenv(eta.ETA_LOG_WRITE_ENV, "1")
    assert eta._log_path() == eta.LOG


def test_tmpへ差し替えた検査は今までどおり書けること(eta, monkeypatch, tmp_path):
    """**既存の検査を壊さないこと。** `LOG` を差し替えた検査はそのまま通ります
    （本物の場所と一致しないので、門は当たりません）。"""
    target = tmp_path / "eta.jsonl"
    monkeypatch.setattr(eta, "LOG", target)
    assert eta._log_path() == target


def test_門が見ているのは_import時に固めた本物の場所であること(eta):
    """`ROOT` ごと差し替えられても効くこと —— 比べる先は定数です。"""
    assert eta._REPO_LOG == ROOT / "data" / "eta.jsonl"


def test_書き込みの口が二つとも門を通っていること():
    """**入口ごとに1回ずつ。1つ抜けると、そこから全部 積まれます。**

    実測 2026-09-01 の木には口が2つあります（`main()` の末尾 ＝ 予測の点、
    `--reflect` の側 ＝ `kind="reflect"` の点）。**数え上げにしておけば、
    3つ目が生えた日にここが落ちて教えます。**
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    opens = src.count('LOG.open("a"')
    assert opens == 0, (
        f"`LOG.open(\"a\")` が {opens}件 残っています ——"
        " 追記は `_log_path()` の返りに対して行うこと（`None` なら書かない）。")
    assert src.count("_log.open(\"a\"") >= 2, (
        "追記の口が2つ未満です。`_log_path()` を通さない口が生えていないか、"
        " 書き方が変わったなら**この検査のほうを直すこと** ——"
        " **見つからないことを『口が無い』と読まないこと。**")
