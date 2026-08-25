"""**前提として名前を出した量の値が、画面に出ているか。**

2026-08-15 の独立評価が、**2本続けて同じ欠け**を指した。3体とも独立に:

> 手取り率が何パーセントなのか、最後まで画面に出ない。だから31か月を検算できない。

`docs/JOURNAL.md` の申し送りは、塞ぎ方まで指定していた ——
**「落ちた数字を1つずつ追う」のではなく「結論の数字を作った入力が、
どこかのコマに出ているか」を機械で見る側**。ここはその検査。

**故障注入を先に書いてある。** 実物（`5SEWUmEzxcs`）の読み上げをそのまま入れて、
**いまの検査が本当にそれを落とすか**を見る。検査を足したのに実物が通る、は
このリポジトリで通算11回起きている（`docs/trigger_main.md` §5）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import verify


def _script(*segs):
    """(読み上げ, 画面) の組を並べて台本にする。"""
    return {"segments": [{"narration": n, "visual": v} for n, v in segs]}


# ------------------------------------------------------------ 実物での故障注入

def test_実物_5SEWUmEzxcs_の前提が落ちる():
    """**この検査を足した理由そのもの。** 通ったら足した意味が無い。

    読み上げは `data/critique_queue/5SEWUmEzxcs.json` の実物。
    画面には結論（31か月・86歳10か月）は出ているが、
    **手取り率の値だけが最後まで無い。**
    """
    s = _script(
        ("年金の繰下げ、分岐点が31か月ずれます",
         {"kind": "stat", "headline": "繰下げの分岐点", "stat": "31か月",
          "formula": "31か月 ＝ 89歳5か月 − 86歳10か月"}),
        ("額面は86歳10か月、手取りは89歳5か月",
         {"kind": "chart", "headline": "額面と手取りの分岐点",
          "bars": [{"label": "額面", "value_label": "86歳10か月"},
                   {"label": "手取り", "value_label": "89歳5か月"}]}),
        ("手取り率は制度の値ではなく、この計算での仮定です",
         {"kind": "stat", "headline": "この計算の前提", "note": "制度の値ではありません"}),
    )
    problems = verify._check_assumption_value_shown(s)
    assert any("手取り率" in p for p in problems), problems


def test_値を画面に出せば通る():
    """**直し方が実在すること。** 落とすだけで直せない検査は歩留まりを削るだけ。"""
    s = _script(
        ("年金の繰下げ、分岐点が31か月ずれます",
         {"kind": "stat", "headline": "繰下げの分岐点", "stat": "31か月",
          "formula": "31か月 ＝ 89歳5か月 − 86歳10か月"}),
        ("手取り率は制度の値ではなく、この計算での仮定です",
         {"kind": "stat", "headline": "この計算の前提", "stat": "手取り率 83.7%",
          "note": "額が上がるほど下がるものとして置いています"}),
    )
    assert verify._check_assumption_value_shown(s) == []


def test_値は別のコマにあってもよい():
    """視聴者は動画を通して見るので、同じコマである必要は無い。"""
    s = _script(
        ("手取り率は、この計算での仮定です",
         {"kind": "stat", "headline": "この計算の前提", "note": "制度の値ではありません"}),
        ("額面が上がるほど手取り率は下がります",
         {"kind": "table", "headline": "使った手取り率",
          "headers": ["年金額", "手取り率"],
          "rows": [["180万円", "86.9%"], ["300万円", "83.7%"]]}),
    )
    assert verify._check_assumption_value_shown(s) == []


# -------------------------------------------------------- 拾いすぎていないか

def test_前提と名乗っていないコマは見ない():
    """**結論の言い換えまで拾うと、直しようのない指摘が増える。**

    「あなたの手取り率次第で」は視聴者への問いかけであって、前提の宣言ではない。
    """
    s = _script(
        ("あなたの手取り率次第で、この差は開くことも縮むこともあります",
         {"kind": "stat", "headline": "あなたの場合", "stat": "31か月"}),
    )
    assert verify._check_assumption_value_shown(s) == []


def test_量の名前が出ていない前提は落とさない():
    """前提を言うこと自体は正しい。**値の要る量を名乗ったときだけ**見る。"""
    s = _script(
        ("賞与のない月給だけで計算しています",
         {"kind": "stat", "headline": "この計算の前提", "note": "賞与は含みません"}),
    )
    assert verify._check_assumption_value_shown(s) == []


def test_読み上げだけの数字では通さない():
    """**3体が突いたのは「画面に出ない」ほう。**

    音で言われた率は、視聴者が止めて確かめられない。画面を見る。
    """
    s = _script(
        ("手取り率は83.7パーセントと仮定しています",
         {"kind": "stat", "headline": "この計算の前提", "note": "制度の値ではありません"}),
    )
    problems = verify._check_assumption_value_shown(s)
    assert any("手取り率" in p for p in problems), problems


def test_離れた場所の数字は値とみなさない():
    """**同じ画面に数字があれば通る、にはしない。**

    `手取り率` と `31か月` が同じコマに並んでいるだけでは、
    その率の値にはならない。近さで見る。
    """
    s = _script(
        ("手取り率は、この計算での仮定です",
         {"kind": "stat", "headline": "この計算の前提", "stat": "31か月",
          "note": "分岐点はこれだけ後ろへずれます。手取り率は制度の値ではありません"}),
    )
    problems = verify._check_assumption_value_shown(s)
    assert any("手取り率" in p for p in problems), problems


# ------------------------------------------------------ 語尾で拾っていること

def test_一覧に無い量にも当たる():
    """**語の一覧にしていない理由。** 次に書かれる calc の量を数え上げられない。"""
    s = _script(
        ("支給日数は、この計算での仮定として置いています",
         {"kind": "stat", "headline": "この計算の前提", "note": "実際は人により違います"}),
    )
    problems = verify._check_assumption_value_shown(s)
    assert any("支給日数" in p for p in problems), problems


def test_同じ量を2回言っても指摘は1件():
    s = _script(
        ("手取り率は仮定です",
         {"kind": "stat", "headline": "この計算の前提", "note": "制度の値ではありません"}),
        ("手取り率は、としています",
         {"kind": "stat", "headline": "前提のつづき", "note": "人により違います"}),
    )
    problems = verify._check_assumption_value_shown(s)
    assert len([p for p in problems if "手取り率" in p]) == 1, problems


def test_助詞まで拾わない():
    """**2026-08-16 の初回生成で実際に出た形。**

    `前提は所得税率` と拾い、直し方の例が
    『前提は所得税率 ＝ 〇〇』という日本語にならない形で生成側へ渡っていた。
    **落とす判定は当たっていたが、渡す直し方のほうが壊れていた。**
    """
    s = _script(
        ("前提は所得税率です。この計算での仮定として置いています",
         {"kind": "stat", "headline": "この計算の前提", "note": "人により違います"}),
    )
    problems = verify._check_assumption_value_shown(s)
    assert any("『所得税率』" in p for p in problems), problems
    assert not any("前提は所得税率" in p for p in problems), problems


def test_台本が無くても落ちない():
    assert verify._check_assumption_value_shown(None) == []
    assert verify._check_assumption_value_shown({"segments": []}) == []


# ------------------------------------------------- 生成中の輪に入っていること

def test_生成中の検査から呼ばれている():
    """**レンダリングの後で落とすと1本まるごと捨てになる**（歩留まり33%の原因）。

    台本だけで判定できるので、`short_script_problems` の側にも入っていること。
    """
    src = (Path(__file__).resolve().parent.parent / "src" / "script_writer.py").read_text(
        encoding="utf-8")
    assert "_check_assumption_value_shown" in src


def test_投稿前の砦にも入っている():
    src = (Path(__file__).resolve().parent.parent / "src" / "verify.py").read_text(
        encoding="utf-8")
    assert src.count("_check_assumption_value_shown") >= 2


# --- 欄の継ぎ目（2026-08-24 に踏んだ） -------------------------------------
#
# `_visual_texts` は**欄ごと・セルごと**に返す。継ぎ目なしで繋ぐと、
# 隣り合わない字が1語に見えて、**存在しない量の名前**が生まれる。
# 実物（`s-tousan-one-month-172`）: headers `["前提の項目","内容"]` と
# rows の `"使った割合"` が繋がって **『項目内容使った割合』**。
# そんな量はどこにも無いので、**画面に出しようがなく必ず落ちる**。


def _table_seg(headers, rows, headline="計算の前提"):
    return {"narration": "前提を置きます。",
            "visual": {"kind": "table", "headline": headline,
                       "headers": list(headers), "rows": [list(r) for r in rows]}}


def test_quantity_name_does_not_span_two_cells():
    """**セルをまたいで量の名前を作らない。** 実物そのままの形。"""
    script = {"segments": [
        _table_seg(["前提の項目", "内容"],
                   [["使った割合", "30%"], ["解約後の再加入", "2年は経費不可"]]),
    ]}
    problems = verify._check_assumption_value_shown(script)
    assert not any("項目内容使った割合" in p for p in problems), \
        "存在しない量の名前（欄の継ぎ目）で落としてはいけない"


def test_real_missing_value_still_caught_in_a_table():
    """**継ぎ目を切っても、本物の欠けは落とす。** 値の無い『使った割合』は残る。"""
    script = {"segments": [
        _table_seg(["前提の項目", "内容"],
                   [["使った割合", "任意解約"], ["解約後の再加入", "2年は経費不可"]]),
    ]}
    problems = verify._check_assumption_value_shown(script)
    assert any("『使った割合』" in p for p in problems), \
        "画面に数字の無い前提は、区切っても捕まえ続けること"


def test_narration_and_visual_do_not_splice():
    """読み上げの末尾と、画面の先頭も繋がない。"""
    script = {"segments": [{
        "narration": "前提として置いたのは次の項目",
        "visual": {"kind": "table", "headline": "前提", "headers": ["内容率"],
                   "rows": [["30%"]]},
    }]}
    problems = verify._check_assumption_value_shown(script)
    assert not any("項目内容率" in p for p in problems)
