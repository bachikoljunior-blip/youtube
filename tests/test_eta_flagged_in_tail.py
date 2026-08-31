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
    # **区切りは全角空白**（`_gate2_surface_note` が composed な行を作るときの形）
    said = ["  [!] 前の話です。　[!] **後ろの話です**"]
    out = eta.flagged(said)
    assert "2件" in out[0]
    body = "\n".join(out)
    assert "前の話" in body and "後ろの話" in body


def test_文の途中の_bang_は拾わない():
    """**他人の文言の引き写しを、名指しされた欠陥として並べないこと。**

    実測 2026-08-26 夜（`flagged()` を入れた直後に踏んだ）——
    `levers.report()` は `data/runs.jsonl` の ship の1行をそのまま印字する。
    その回の ship が `"eta の [!] 11本 を尾へ運び…"` だったので、
    **自分の ship の文言が尾の「名指しされた欠陥」に並んだ。**
    """
    said = ["  この回の ship: eta の [!] 11本 を尾へ運んだ",
            "  [!] **これは本物の警告です**"]
    out = eta.flagged(said)
    assert "1件" in out[0]
    body = "\n".join(out)
    assert "本物の警告" in body
    assert "尾へ運んだ" not in body


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
    # **閉じ括弧まで当てないこと**（2026-08-29 に3件 まとめて赤くなった）。
    # `headline()` に引数を1つ足すだけで、この検査は落ちます —— 落ちても
    # 「頭と尾で2回 呼んでいるか」は1文字も変わっていません。**守りたいのは
    # 呼ぶ回数と場所であって、引数の並びではない。**
    assert body.index("for line in flagged(said):") > body.rindex("for line in headline(pl, prev, tr")


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


# --- **値札を、名前の隣に置く**（2026-08-31・最適化の回に実測して足した）--------
#
# この節（`flagged`）は欠陥を**名前つきで**並べます。同じ頭3行の中で、
# 到達日を動かす手（`verdict`）は 2026-08-31 の朝まで**日付と件数だけ**でした。
# **片方は名前つき、もう片方は名無し。** 実測（`data/runs.jsonl`・直近7日）:
#
#     ship 359件   `fix` **219件（61%）** ／ `verdict` **11件（3%）**
#     lever        `none` **147件（41%）** ／ `gate` 17件（5%）
#     `--moves`    **305件 が 0**（機械自身が「動かない」と申告して撃っている）
#     到達日        2027-01-02 → 2027-01-15（**+13日 遠のいた**。宣言は -55日）
#
# `eta.py` は「軌跡の腕が動くのは前提を1件 閉じたときだけ」と**200行 下**で
# 自分に言っています。**その1行は、名前の並びより 200行 遠い所にあります。**
#
# **これは「塞ぐな」ではありません。** 欠陥は本物で、実際に偽の合格を
# 何度も止めています。留めているのは **`--moves` が 0 だと同じ所に書いてある**
# ことだけです。
def test_欠陥の並びの隣にmovesが0だと書いてあること():
    eta = _load() if "_load" in globals() else None
    if eta is None:                                            # pragma: no cover
        import importlib.util
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("eta_mod", root / "scripts" / "eta.py")
        eta = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(eta)
    out = eta.flagged(["[!] 欠陥A の話です", "[!] 欠陥B の話です"])
    joined = "\n".join(out)
    assert "0日" in out[1], (
        "**値札が件数のすぐ下にありません。** 末尾へ置くと『ほか N件』と"
        "入れ替わり、しかも**数字から離れます**。値札は数字の隣にあるときだけ"
        "値札です: " + joined)
    assert "`--moves` は定義上 0日" in joined, (
        "**欠陥の名前の隣に、その値札がありません。** 名前つきの欠陥 18件 と、"
        "名無しの `verdict` 1件 が並ぶと、実測で 61% が名前のある側へ行きます:\n"
        + joined)
    assert "期日の来た前提" in joined, (
        "**代わりにどこを見ればよいか**を書いていません。"
        "値札だけを置くと、その回は何も撃たずに終わります: " + joined)
