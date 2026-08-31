"""**族をそろえた比**（`deep_short.by_family`）が、`measure()` と同じ群で解いているか。

2026-08-31 にこの前提を閉じた回が足した。`next_if_false` は
「次に疑うのは族」と言っており、その答えを**同じ回のうちに**出すのがこの関数。

**ここが見ているのは数そのものではありません**（実データは毎日 動く）。
見ているのは **`measure()` と群の作り方が割れていないこと** ——
2か所が別々に同じ問いを解きはじめるのが、`src/deep_short.py` の冒頭が
名指ししている壊れ方（門と手順が別の母集団を数えていた）。
"""
from __future__ import annotations

import inspect
import statistics

from src import deep_short as D


def test_同じ3条件で選んでいる():
    """`measure()` の3条件（ショート・齢48時間の読み・生きた帯）と同じか。"""
    src = inspect.getsource(D.by_family)
    assert 'forms.get(vid) != "ショート"' in src
    assert "vid not in readings or vid not in live" in src
    # 処置／対照の割り方も `measure()` と同じ（`s-` で始まるかどうか）
    assert 'startswith("s-")' in src


def test_合格点はmeasureと同じ1か所から来ている():
    assert D.by_family()["bar"] == D.BAR


def test_両群がそろう族だけを数える():
    f = D.by_family()
    for fam, s in f["per_family"].items():
        assert fam, "族名が空の本は数えないこと（テーマIDから族が引けなかった本）"
        assert s["処置"] and s["対照"], f"{fam}: 片群しか居ない族が混ざっている"
        assert statistics.fmean(s["対照"]) > 0, f"{fam}: 対照が0再生だと比が出せない"


def test_中央値は比の中央値():
    f = D.by_family()
    if f["ratios"]:
        assert f["median"] == statistics.median(f["ratios"].values())
        assert f["families"] == len(f["ratios"])
    else:
        assert f["median"] is None


def test_族ごとの比は処置平均わる対照平均():
    f = D.by_family()
    for fam, r in f["ratios"].items():
        s = f["per_family"][fam]
        assert r == statistics.fmean(s["処置"]) / statistics.fmean(s["対照"])


def test_覆る条件がdocstringに書いてある():
    """**書いていない結論は、次の回が判断できない。**"""
    doc = D.by_family.__doc__ or ""
    assert "覆る条件" in doc


def test_外れたときにCLIが族の答えまで出す():
    """`next_if_false` を**印字するだけ**に戻さないこと。

    2026-08-31 まで、ここは「次に疑うのは族」という**文**を出して終わりでした。
    `src/followup.py` の実測は、そうやって書かれた 31手 の実行が **0件**。
    """
    import scripts.deep_short_verdict as CLI

    src = inspect.getsource(CLI.render)
    assert "by_family" in src, "外れたときに族の答えを出す配線が外れている"
    f = D.by_family()
    lines = "\n".join(CLI.render_family(f))
    if f["ratios"]:
        assert "族をそろえた比" in lines
        for fam in f["ratios"]:
            assert fam in lines
