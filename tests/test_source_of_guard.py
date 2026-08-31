"""`conftest.source_of()` が、**ファイルが動いた回に本当に鳴るか**（2026-08-27）。

## なぜ要るか

`source_of` は「20分の走りの最中に `git merge` でファイルがずれた回」を
名指しするための包みです。**鳴らない包みは、素の `inspect.getsource` と同じ**で、
次の回はまた「気まぐれな赤2件」を読むことになります。

だから**故障を注入して**、鳴ることを見ます。

実測 2026-08-27 の壊れ方（この検査が再現しているもの）:

    走り1（マージしながら）  2件 赤
    走り2（マージしながら）  **同じ2件** 赤
    走り3（木を動かさず）    **3736 passed / 0 failed**

**同じ2件が2回とも赤**なので「気まぐれ」ではありません。
**木を動かしたかどうか**が効いていました。
"""
from __future__ import annotations

import importlib.util
import sys

import pytest

from conftest import source_of


def _rewrite_moved(p):
    """関数の**上**に 60行 入れ、**mtime も進める**。

    **同じ秒に2回 書くと `linecache.checkcache()` が気づきません**（mtime が同値）。
    実物のマージは分 単位で離れているので、そこは実物に合わせます ——
    合わせないと、**この検査だけが通って実物では鳴らない**包みになります
    （2026-08-27、最初にそう書いて `DID NOT RAISE` で落ちました）。
    """
    import os

    st = p.stat()
    p.write_text("x = 1\n" * 60 + "def target():\n    return '目印A'\n",
                 encoding="utf-8")
    os.utime(p, (st.st_atime + 120, st.st_mtime + 120))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_動いていなければ黙って中身を返すこと(tmp_path):
    p = tmp_path / "m_ok.py"
    p.write_text("def target():\n    return '目印A'\n", encoding="utf-8")
    mod = _load(p, "m_ok")
    src = source_of(mod.target, "target")
    assert "目印A" in src and src.lstrip().startswith("def target")


def test_ファイルが下へずれたら名指しして落ちること(tmp_path):
    """**素の `inspect.getsource` なら、黙って別の中身を返します。**"""
    p = tmp_path / "m_moved.py"
    p.write_text("def target():\n    return '目印A'\n", encoding="utf-8")
    mod = _load(p, "m_moved")

    # 兄弟の回が、この関数の**上**に行を入れたのと同じこと。
    _rewrite_moved(p)

    with pytest.raises(AssertionError) as e:
        source_of(mod.target, "target")
    msg = str(e.value)
    assert "読み込み後にファイルが動いています" in msg, msg
    assert "撃ち直すこと" in msg, msg
    assert "この検査は壊れていません" in msg, (
        "**赤の読み方を言っていません。** これが無いと、次の回は"
        "「検査が壊れた」と読んで検査のほうを直します:\n" + msg)


def test_素のgetsourceは黙って別の中身を返すこと(tmp_path):
    """**包みが要る理由そのもの。** ここが緑なら、包みを外してはいけません。"""
    import inspect

    p = tmp_path / "m_raw.py"
    p.write_text("def target():\n    return '目印A'\n", encoding="utf-8")
    mod = _load(p, "m_raw")
    _rewrite_moved(p)

    import linecache
    linecache.checkcache(str(p))
    try:
        raw = inspect.getsource(mod.target)
    except Exception:
        return  # 例外で落ちるならそれでよい（黙って嘘を返してはいない）
    assert not raw.lstrip().startswith("def target"), (
        "素の `getsource` が正しく返しました。**包みは要らないかもしれません** ——"
        " `conftest.source_of` の『覆る条件』を読んで、外すか決めること")
