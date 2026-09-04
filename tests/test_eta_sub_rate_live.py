"""**`eta.py` の `sub_rate` の手は、べた書きにしないこと。**

## なぜ在るか（2026-09-04・最適化の回）

`scripts/eta.py` は、回がその周に引く腕を決めるために**最初に読む画面**です。
そこに `sub_rate` の手として、こう**べた書き**されていました ——

    「登録の依頼はいま**最後のセグメントの音声1文**だけ（`src/script_writer.py`）。
      画面（全時間）・`first_comment`・説明欄の先頭に同じ依頼を置くのは、次の1本で試せて…」

**その3面は 2026-09-03 21:00 JST に全部 入りました。** それでも上の文は
1文字も変わらず刷られ続け、回は「済んだ仕事」を名指しされ続けました。
実測の帰結は、**同じ画面の2行 上**に出ています ——
「直近 7日 の ship: `per_video` 130件 ／ `sub_rate` 13件」。

この検査は、その1文が戻ってこないことだけを見ます。
**覆る条件**: `sub_rate` の面を実物から引かない形に戻したくなったら、
この検査を消すのではなく、**なぜ実物から引けないのかを `docs/JOURNAL.md` に書くこと。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _eta():
    spec = importlib.util.spec_from_file_location("etamod", ROOT / "scripts" / "eta.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_no_hardcoded_stale_sub_rate_claim():
    """「いま音声1文だけ」を、`eta.py` が**印字する側**に持たないこと。

    註（なぜ「ファイルに無いこと」ではないか）: この欠陥を直した回の説明が、
    同じ語を `_sub_rate_move()` の docstring で引用しています。**引用は害が無い**
    —— 害があるのは、その語が**画面に出る**ことだけなので、そちらだけを見ます。
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    bad = [
        ln for ln in src.splitlines()
        if "最後のセグメントの音声1文" in ln
        and ("out.append" in ln or "bar}" in ln or 'f"' in ln)
    ]
    assert not bad, (
        "`sub_rate` の手をべた書きに戻しています（印字する側に在ります）。"
        "面が乗っているかは `src/sub_ask.py`／`src/visuals.py` から引くこと"
        f"（`_sub_rate_surfaces()`）: {bad}"
    )
    m = _eta()
    assert "最後のセグメントの音声1文" not in "\n".join(m._sub_rate_move("#"))


def test_surfaces_come_from_the_repo():
    """面の生き死には、実物の定数から出ていること（空にすれば「空いている」に戻る）。"""
    m = _eta()
    surf = m._sub_rate_surfaces()
    assert surf, "面が1つも出ていません"
    names = [n for n, _, _ in surf]
    assert any("説明欄" in n for n in names)
    assert any("first_comment" in n for n in names)
    assert any("画面" in n for n in names)

    from src import sub_ask
    live = {n: ok for n, ok, _ in surf}
    head_name = next(n for n in names if "説明欄" in n)
    assert live[head_name] == bool(sub_ask.HEAD.strip()), (
        "`sub_ask.HEAD` を空にしても『乗っている』と出ています ＝ 実物から引いていません"
    )


def test_line_names_the_open_side_not_the_closed_one():
    """全部 乗っているときは、『置け』ではなく『もう空いていない』と言うこと。"""
    m = _eta()
    surf = m._sub_rate_surfaces()
    text = "\n".join(m._sub_rate_move("#"))
    if all(ok for _, ok, _ in surf):
        assert "もう空いていません" in text
        assert "空いています" not in text.replace("もう空いていません", "")
    else:
        assert "空いています" in text
