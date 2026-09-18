"""`scripts/for_owner.py` の `HEAD_RE` —— **見出しのダッシュは 1つ でも 2つ でも通すこと**。

**2026-09-19 00:4x・optimizer・opus。** derivation は `docs/JOURNAL.md` 同刻 §3。

**なぜこの検査が在るか（実測）**: 09/18 23:xx の回が
`### 出す 2026-09-19 08:00〜09:00 JST —— **1行だけ貼ってください…**` と書いた。
`HEAD_RE` は **`—`（1つ）**のあとしか飾りを認めていなかったので、
**その窓は 1つも登録されず、`--list` にも出ず、親も出しませんでした** ——
消えたのは「**これが通るまで動画が1本も作れません**」の窓です。
repo の見出しはほぼ全部 `——`（2つ）なので、1つ だけを通す形は
**この file だけが repo と違う字を要求する罠**でした。

**陽性対照つき**（落ちるまで撃つ）: 飾りの無い見出し・1つ・2つ が通り、
**日付や刻が壊れた見出しは通らないこと**まで見ます。
"""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "for_owner", Path(__file__).resolve().parent.parent / "scripts/for_owner.py")
for_owner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(for_owner)

HEAD = "### 出す 2026-09-19 08:00〜09:00 JST"


def _m(line: str):
    return for_owner.HEAD_RE.match(line)


def test_飾りの無い見出しは通る():
    m = _m(HEAD)
    assert m and m.group(1) == "2026-09-19" and m.group(2) == "08:00" and m.group(3) == "09:00"


def test_ダッシュ1つは通る():
    assert _m(f"{HEAD} — 見出し")


def test_ダッシュ2つも通る():
    """**これが 09/18 23:xx に消えた当の形**（窓が 1つ 丸ごと黙った）。"""
    m = _m(f"{HEAD} —— **1行だけ貼ってください（15秒）**")
    assert m and m.group(4) == "**1行だけ貼ってください（15秒）**"


def test_ダッシュ3つは通さない():
    """**緩めるのは 2つ まで** —— 字を足す競争にしないこと（関数の註の覆る条件 (2)）。"""
    assert _m(f"{HEAD} ——— 見出し") is None


def test_ダッシュなしで飾りだけは通さない():
    assert _m(f"{HEAD} 見出し") is None


def test_刻や日付が壊れた見出しは通さない():
    assert _m("### 出す 2026-09-19 08:00〜09:00") is None          # JST が無い
    assert _m("### 出す 2026-9-19 08:00〜09:00 JST") is None       # 日が 1桁
    assert _m("### 出した 2026-09-19 08:00〜09:00 JST") is None    # 記録の側


def test_いまの_FOR_OWNER_は全部の窓が当たる():
    """**回帰** —— `--check` が黙るのと同じこと（書いた回が撃たなくても、ここで落ちます）。"""
    doc = (Path(__file__).resolve().parent.parent / "docs/FOR_OWNER.md").read_text(encoding="utf-8")
    heads = [ln for ln in doc.splitlines() if ln.startswith("### 出す ")]
    assert heads, "窓が 1つ も無い（節の名が変わった？）"
    assert [h for h in heads if not _m(h)] == []
