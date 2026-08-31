"""**止まっているあいだ、群は「作る速さ」では埋まらない。**

## この検査が守っているもの（2026-08-30・最適化の回に実測して足した）

`scripts/deadline_check.py` の `_project_nth()` は、群が床に満たないとき
**「いまの作る速さが続いたら」**で N本目の公開日を出します。
その docstring 自身が、言えないこととして次を挙げています。

> **作る速さが落ちれば伸びます。** この推定は「いまの速さが続いたら」です

**2026-08-30 から、作る速さは 0 です。** `src/pause_guard` が生成も投稿も
塞いでいて、`AUTOMATION_PAUSED.md` が在るあいだ **1本も増えません。**
それでも `_project_nth()` は**停止前に作った本**から率を読み、延ばしていました
（実測 2026-08-30 15:3x、`python scripts/deadline_check.py`）::

    opening_motion（腕 per_video）  対照(動きなし) あと **2本**
                                   → 「0.86本/日」で 8本目 09/15 → 判定 **09-22**
    request_form  （腕 sub_rate）   終端のみ あと **32本** ／ 途中あり あと **47本**
                                   → 「10.00本/日」「6.25本/日」→ 判定 **10-11**

**合わせて 81本。** どれも解除するまで作れません。それでも機械は日付を出し、
`src/arm_speed.forward()` の予定表 θ に**閉じる見込みとして数えられていました**
（実測: 30日窓 0.700 → 0.667 ／ 60日窓 0.400 → 0.367。塞いだぶん下がった）。

`request_form` は **`sub_rate` の唯一 走っている A/B** です
（`sub_rate` の閉じた前提は 2件 ＝ `arm_speed.MIN_N` 未満）。

## 形は `_ans_accrual` の `zero_means_never` と同じです

「待てば来る」（`warming`）ではなく、**「こちらが解除しないかぎり来ない」**。
`Verdict.unreachable` の docstring が言うとおり、**直し方が正反対**なので
札を分ける必要があります。さらにこの3つ目は
**収益化の審査（こちらでは起こせない）とも違い、この機械の作業で動きます** ——
だから `Answer.paused_short` / `deadline_check.paused_claims()` で別に数え、
`scripts/eta.py` の頭が **門を1日 早く閉じることの値段**として印字します。

## 固定するのは4つ

1. 止まっているあいだ、床に足りない群は**日付を出さない**（`unreachable`）
2. その `Answer` は**あと何本 要るか**を持つ（`paused_short`）——
   本数が無いと、値段が言えません
3. **止まっていなければ、今までどおり推定の日付が出る**（平時に壊さない）
4. `scripts/eta.py` の頭の行は、止まっていなければ**自分で黙る**

## 覆る条件

`AUTOMATION_PAUSED.md` が消えたら 1・2・4 は自分で黙ります。
`_project_nth()` の側を「停止中は 0本/日」に書き換える設計へ移すなら、
**この検査ごと差し替えること**（日付が出ないことは同じでも、理由の欄が変わります）。
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


D = _load("paused_supply_deadline_check", ROOT / "scripts" / "deadline_check.py")


# --- 1・2: 止まっているあいだは日付を出さず、本数を持つ -----------------------

def test_paused_supply_returns_unreachable_with_shortfall(monkeypatch):
    """**あと N本 が要る群は、停止中は日付を出さない。**そして N を持つ。"""
    monkeypatch.setattr(D, "_paused_supply", D._paused_supply)   # 触っていないことの明示
    import src.pause_guard as PG

    monkeypatch.setattr(PG, "is_paused", lambda: True)
    ans = D._paused_supply("本文", 7)
    assert ans is not None, "止まっているのに、打ち切っていない"
    assert ans.ready is None, "止まっているのに、判定できる日を出している"
    assert ans.unreachable is True, "`warming`（待てば来る）に見えてはいけない"
    assert ans.paused_short == 7, "あと何本 要るかを持っていない（値段が言えません）"
    assert "1本も増えません" in ans.why, "なぜ来ないのかが `why` に無い"


def test_not_paused_is_silent(monkeypatch):
    """**平時は何もしない。** `None` を返して、今までどおりの推定へ通す。"""
    import src.pause_guard as PG

    monkeypatch.setattr(PG, "is_paused", lambda: False)
    assert D._paused_supply("本文", 7) is None


# --- 3: 平時の推定を壊していないこと -----------------------------------------

def _rows(n: int, start: str = "2026-08-01") -> list[dict]:
    """作った日と公開日を持つ控え（`_project_nth` が読む形）。"""
    d0 = date.fromisoformat(start)
    out = []
    for i in range(n):
        made = d0.replace(day=d0.day + (i % 5))
        out.append({"built_at": made.isoformat(),
                    "at": (made.replace(day=made.day + 2)).isoformat() + "T09:00:00+09:00"})
    return out


def test_projection_still_dates_when_running(monkeypatch):
    """**止まっていなければ、床に足りない群にも日付が出ること。**

    `_project_nth()` が `None` を返すようになると
    `src/arm_speed.forward()` の `undated` に落ち、**腕が丸ごと凍ります**
    （あちらの docstring の実測）。平時にそれを起こさないこと。
    """
    import src.pause_guard as PG

    monkeypatch.setattr(PG, "is_paused", lambda: False)
    rows = _rows(8)
    pub = sorted(str(r["at"])[:10] for r in rows)
    got = D._project_nth(rows, pub, 16, "2026-08-01", date(2026, 8, 30))
    assert got is not None, "平時なのに日が出ていない（腕が凍ります）"
    assert isinstance(got[0], date)


# --- 4: eta の頭の行 ----------------------------------------------------------

ETA = _load("paused_supply_eta", ROOT / "scripts" / "eta.py")


def test_eta_line_is_silent_when_not_paused(monkeypatch):
    """**止まっていなければ、この行は出ないこと。**（平時に雑音を足さない）"""
    monkeypatch.setattr(ETA.pause_guard, "is_paused", lambda: False)
    assert ETA.paused_premise_line() is None


def test_eta_line_names_the_price_when_paused(monkeypatch):
    """**止まっている間は、件数・本数・腕・「値段」が同じ行に出ること。**

    出さないと、読み手は「腕が引けない」と「腕の実験が進まない」を
    同じ損だと読みます。**別の損です** —— 後者は解除の遅れに比例して増えます。
    """
    monkeypatch.setattr(ETA.pause_guard, "is_paused", lambda: True)
    monkeypatch.setattr(
        ETA, "_deadline_check_mod",
        lambda: type("M", (), {"paused_claims": staticmethod(lambda: {"ある前提": 79})}),
    )
    line = ETA.paused_premise_line()
    assert line is not None, "止まっているのに、凍った前提を言っていない"
    assert "1件" in line and "79本" in line, f"件数か本数が出ていない: {line}"
    assert "値段" in line, "「門を1日 早く閉じることの値段」だと言っていない"


def test_eta_line_says_so_when_it_cannot_read(monkeypatch):
    """**読めなかったときは、黙らずに『読めなかった』と言うこと。**

    黙ると「凍っている前提は無い」と読めます。`arm_speed.forward()` の
    「**黙って 0 にしないこと**」と同じ扱い。
    """
    monkeypatch.setattr(ETA.pause_guard, "is_paused", lambda: True)

    def _boom():
        raise RuntimeError("読めません")

    monkeypatch.setattr(ETA, "_deadline_check_mod", _boom)
    line = ETA.paused_premise_line()
    assert line and "確かめられませんでした" in line


# --- 呼び口が増えたときに落ちること ------------------------------------------

def test_every_projection_call_is_guarded():
    """**`_project_nth()` を呼ぶ所は、全部 `_paused_supply()` の後ろにあること。**

    2026-08-30 の実測で、呼び口は **2か所**でした
    （`_ans_published_group` と `_ans_group_key`）。3か所目を足した回が
    門を付け忘れると、**その道だけ停止中に偽の日付を出します** ——
    この repo が「同じことを2か所が別々に言っていて、片方しか読まれていない」と
    12回 書いている、まさにその形です。

    **覆る条件**: 門を `_project_nth()` の内側へ移したら、この検査は要りません
    （そのときは `_paused_supply()` が `Answer` を返せなくなるので、
    設計ごと差し替えること）。
    """
    src = (ROOT / "scripts" / "deadline_check.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    # **呼び口の目印は `= _project_nth(`**（代入）。docstring の言及と分けるため ——
    # 素朴に `_project_nth(` で拾うと、470行目の註（`arm_speed.throughput()` と
    # 並べた表）まで「呼び口」に数えます。**実際に踏みました。**
    calls = [i for i, ln in enumerate(lines) if "= _project_nth(" in ln]
    assert calls, "`_project_nth()` の呼び口が1つも見つかりません（検査が空回りしています）"
    for i in calls:
        # **窓は「その呼び口を囲む関数の頭から」**（固定の行数ではありません）。
        # `_ans_group_key` の門と呼び口のあいだには 12行 あります ——
        # 10行 で切ると、門が付いているのに落ちました（2026-08-30 に踏んだ）。
        start = next((j for j in range(i, -1, -1)
                      if lines[j].startswith("def ")), 0)
        window = "\n".join(lines[start:i])
        assert "_paused_supply(" in window, (
            f"{i + 1}行目の `_project_nth()` に、停止の門が付いていません: "
            f"{lines[i].strip()}")


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
