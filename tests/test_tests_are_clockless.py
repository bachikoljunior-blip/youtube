"""**日を数える検査が、器の時計を読まないこと。**（2026-09-05 05:4x に実測して足した）

## なぜ要るか（**毎晩 9時間、赤かった**）

`src/rule_per_video.staleness()` と `src.judgeable.Floor.ready_at_rule` は
**JST** で「今日」を数えます（規則1「1日1本」の日境は JST）。ところがその検査は
**`date.today()`** ＝ **その器の時計**（この器は **UTC**）で作った日を渡していました。

    器の UTC 15:00〜24:00  ＝ **JST 00:00〜09:00** → UTC の日付が 1日 若い

    tests/test_rule_per_video_staleness.py  注入した「15日前」が 16日前 に見える
                                            → `assert s["age_days"] == 15` が赤
    tests/test_ready_at_rule.py             `got 2026-09-22 <= latest 2026-09-21` が赤

**＝ この2件は、毎晩 JST 00:00〜09:00 の 9時間 だけ 赤くなります。**
**そして この輪が走るのは、まさにその時間帯です**（実測 2026-09-05 05:2x の回が
両方を赤で受け取り、自分の変更が壊したのかを切り分けるところから始めた）。

**毎晩の赤は、本物の赤を隠します。** `docs/GOAL.md`「発火したことのない検査は
検査ではない」の裏側 —— **毎晩 発火する検査も、検査ではありません。**

## 直し方（時計を JST へ揃えるのではありません）

**検査が時計を持たないようにします** —— 模組の側に継ぎ目（`_today_jst()`）を1つ置き、
検査は `monkeypatch.setattr(<模組>, "_today_jst", lambda: FIXED_TODAY)` で
**固定の日**を挿します。時計を JST へ揃えるだけの直しは、器の時計が変わった日に
同じ形で戻ります。

## この検査が見ていないもの

`tests/` には素の `date.today()` を使う検査が **他にもあります**
（2026-09-05 の実測で 12ファイル）。**全部は止めていません** —— 日を数えない
（`date.today()` を「いまより後か」程度にしか使わない）検査まで巻き込むからです。
**赤くなった実物だけを、この一覧に足していくこと。**

**覆る条件**: この器の時計が JST になったら、上の 9時間 は消えます。
それでも**この検査は残すこと** —— 消すと、次に器が変わった日に同じ晩を繰り返します。
"""
from __future__ import annotations

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: **実際に毎晩 赤くなった検査**（足すのは、実物が赤くなったときだけ）。
CLOCKLESS = (
    "test_rule_per_video_staleness.py",
    "test_ready_at_rule.py",
)

#: 註とドキュメンテーション文字列の中は数えません（**なぜ駄目かを書けなくなる**ので）。
_BARE = re.compile(r"(?<![\w.])date\.today\(\)|datetime\.today\(\)")


def _code_lines(src: str) -> list[tuple[int, str]]:
    """`#` で始まる行と、三重引用符の塊を落とす（雑でよい —— 見たいのは代入だけ）。"""
    out: list[tuple[int, str]] = []
    in_doc = False
    quote = ""
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if in_doc:
            if quote in line:
                in_doc = False
            continue
        for q in ('"""', "'''"):
            if stripped.startswith(q) and not (stripped.endswith(q) and len(stripped) > 5):
                in_doc, quote = True, q
                break
        if in_doc or stripped.startswith("#"):
            continue
        out.append((i, line))
    return out


def test_日を数える検査は器の時計を読まない():
    bad: list[str] = []
    for name in CLOCKLESS:
        path = TESTS / name
        assert path.exists(), f"{name} が在りません（名前が変わったなら、この一覧も直すこと）"
        for lineno, line in _code_lines(path.read_text(encoding="utf-8")):
            if _BARE.search(line):
                bad.append(f"{name}:{lineno}  {line.strip()[:70]}")
    assert not bad, (
        "**器の時計（この器は UTC）を読んでいます。** 数える側は JST なので、"
        "JST 00:00〜09:00 のあいだ 1日 ずれて **毎晩 赤くなります**。"
        " 固定の日を `monkeypatch.setattr(<模組>, \"_today_jst\", …)` で挿すこと:\n  "
        + "\n  ".join(bad)
    )


def test_継ぎ目そのものが在る():
    """**継ぎ目を消さないこと。** 消すと検査が時計を持ち直します。"""
    from src import judgeable, rule_per_video

    for mod in (rule_per_video, judgeable):
        fn = getattr(mod, "_today_jst", None)
        assert callable(fn), f"{mod.__name__}._today_jst() が在りません"
        assert fn() is not None
