"""**`eta.py` の `[!]` は、頭と尾だけ読む手順では1本も読まれない。**

`CLAUDE.md`: 「読むのは、出力の最初と最後に同じ字で出る3行だけです」。
実測 2026-08-26 —— 出力 297行・`[!]` 10本（80〜289行目）・頭にも尾にも **0本**。
そのうち1本は直す先を名指ししていた（「09/06〜09/18 の 13日 は長尺の予約が0本。
直す先はサムネでも題でもなく、その 13日 に長尺を置くこと」）。**どの回も読んでいない。**

`headline()` は 08-20 に同じ欠陥を**日付について**直している（「その日付が、
出力の 200行目あたりにあった」）。**運んだのは日付だけで、警告は置いてきた。**
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scripts.eta as eta  # noqa: E402


def test_本文の_bang_を尾へ運ぶ():
    said = [
        "### **月20万の到達予測（軌跡）: 2026-12-20**",
        "  ふつうの行",
        "  [!] **2026-09-06〜2026-09-18 の 13日 は長尺の予約が0本**です。",
        "  べつの行",
        "        [!] **この日付は条件つきの「最早」です**（合格点が立っていない）",
    ]
    out = eta.flagged(said)
    assert out, "`[!]` があるのに尾へ運んでいない"
    assert "2件" in out[0]
    body = "\n".join(out)
    assert "13日 は長尺の予約が0本" in body
    assert "最早" in body


def test_bang_が無ければ何も足さない():
    assert eta.flagged(["ふつうの行", "もう1行"]) == []


def test_同じ行に_bang_が2つあっても両方運ぶ():
    said = ["  [!] 前の話です。 [!] **後ろの話です**"]
    out = eta.flagged(said)
    assert "2件" in out[0]
    body = "\n".join(out)
    assert "前の話" in body and "後ろの話" in body


def test_同じ警告は1回だけ():
    said = ["  [!] おなじ警告がここに出ます", "  [!] おなじ警告がここに出ます"]
    assert "1件" in eta.flagged(said)[0]


def test_長い行は切り詰めるが件数は数える():
    said = [f"  [!] {'あ' * 400}", "  [!] みじかい"]
    out = eta.flagged(said)
    assert "2件" in out[0]
    assert all(len(l) < 200 for l in out), "尾が長すぎると、尾も読まれなくなる"


def test_上限を超えたら残りの件数を言う():
    said = [f"  [!] 警告 {i} 番目の中身" for i in range(eta.FLAG_LIMIT + 5)]
    out = eta.flagged(said)
    assert f"{eta.FLAG_LIMIT + 5}件" in out[0]
    assert "ほか 5件" in out[-1]


def test_main_が尾で_flagged_を呼んでいる():
    """**呼び出しが消えたら、この検査が落ちること。**

    `flagged()` だけ在って `main()` が呼ばなければ、出力は 08-26 以前に戻る。
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    m = re.search(r"def main\(\).*", src, re.S)
    assert m
    body = m.group(0)
    assert "for line in flagged(said):" in body, "`main()` が `flagged` を呼んでいない"
    # **尾の `headline` より後ろにあること**（前に置くと、尾3行を読む側に届かない）
    assert body.index("for line in flagged(said):") > body.rindex("for line in headline(pl, prev, tr):")


def test_say_が印字を1行も落としていない():
    """**`say()` は控えるだけで、出る中身も順番も変えない。**"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    body = re.search(r"def main\(\).*", src, re.S).group(0)
    # `report`/`_drift`/`_reflect_recap`/`levers.report`/`_report_levers`/
    # `_report_trajectory`/`_report_plan` の7つは、控える側（say）に通すこと
    for name in ["report(m, a)", "_drift(row)", "_reflect_recap()",
                 "levers.report(", "_report_levers(pl)",
                 "_report_trajectory(tr, pl)", "_report_plan(m, a, pl)"]:
        i = body.index(name)
        chunk = body[i:i + 200]
        assert "say(line)" in chunk, f"{name} の行が控えに入っていない"
