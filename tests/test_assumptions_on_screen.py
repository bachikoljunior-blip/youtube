"""**前提が画面に1枚も出ていない本を止める**（`verify._check_assumptions_on_screen`）。

見るのは **割った後のコマ**（`slides_plan.json`）です。`script.json` ではありません
（`_check_adjacent_frames` と同じ理由 —— 画面は割った後にしか存在しません）。

## 申し送りの数字を、そのまま採らなかった記録（2026-08-16 23:xx）

前の回は「**前提の表が1枚も無い本が 33/61**」と渡してきました。
`data/critique_queue/*.plan.json` の61本で数え直した結果:

    前提の名乗りが1枚も無い（見出しだけ見る）        **1 / 61**
    前提の名乗りが1枚も無い（画面の文字を全部見る）  **0 / 61**
    `kind == "table"` の前提コマが無い               **33 / 61**  ← 申し送りの数字

**33本は「前提が無い」ではなく「前提が表の形をしていない」でした。**
申し送りのとおり `table` を要求すると半分以上が落ち、**誤報は不投稿**です。
だから見るのは形ではなく「あるか」。**実測 61/61 が通ります。**
"""

import json

from src import verify


def _plan(tmp_path, plan):
    (tmp_path / "slides_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------ 落ちるべき形


def test_前提のコマが1枚も無ければ落ちる(tmp_path):
    work = _plan(tmp_path, [
        {"kind": "stat", "headline": "育児休業給付の手取り比", "stat": "84.9%"},
        {"kind": "table", "headline": "額面比と手取り比",
         "rows": [["額面比", "67.0%"], ["手取り比", "84.9%"]]},
        {"kind": "stat", "headline": "あなたはどこに入るか", "stat": "83.7〜86.9%"},
    ])
    problems = verify._check_assumptions_on_screen(work)
    assert problems and "画面に1枚も出ていません" in problems[0], problems


def test_前提を名乗っても値が無ければ落ちる(tmp_path):
    """「手取り率は仮定です」とだけ書いた形。**名前だけの前提は追試できません。**"""
    work = _plan(tmp_path, [
        {"kind": "stat", "headline": "結論", "stat": "84.9%"},
        {"kind": "steps", "headline": "この計算の前提",
         "items": ["手取り率は仮定です", "賞与は考えない"]},
    ])
    problems = verify._check_assumptions_on_screen(work)
    assert problems and "値が1つも出ていません" in problems[0], problems


# ------------------------------------------------------------ 通るべき形
#
# **ここが本体です。** 申し送りの「表を要求する」を入れていたら、
# 下の3つのうち table 以外の全部が落ちていました（実物で 33/61）。


def test_表で出していれば通る(tmp_path):
    work = _plan(tmp_path, [
        {"kind": "table", "headline": "計算の前提 令和6年度",
         "rows": [["月給", "300,000円"], ["支給率", "67%"]]},
    ])
    assert verify._check_assumptions_on_screen(work) == []


def test_stepsで出していても通る(tmp_path):
    """実物15本がこの形。**表でないというだけで落としません。**"""
    work = _plan(tmp_path, [
        {"kind": "steps", "headline": "この計算の前提",
         "items": ["月給30万円", "支給率67%", "30日ぶん"]},
    ])
    assert verify._check_assumptions_on_screen(work) == []


def test_注記に前提を書いていても通る(tmp_path):
    """実物 `_kUTXa1t9ZA` の形。**見出しだけを見た数え方では落ちていました。**

    視聴者は見出しも注記も同じ画面で見ます。**分ける理由がありません。**
    """
    work = _plan(tmp_path, [
        {"kind": "stat", "headline": "1か月の差", "stat": "35,709円",
         "note": "給付は非課税・社保免除・賞与なしの前提 月給30万円"},
    ])
    assert verify._check_assumptions_on_screen(work) == []


def test_コマの記録が無ければ何も言わない(tmp_path):
    """この直しより前に作った build と、長尺が落ちても意味がありません。"""
    assert verify._check_assumptions_on_screen(tmp_path) == []


# ------------------------------------------------------------ 故障注入
#
# **検査そのものが死んでいないか。** 実物を1つ持ってきて、
# 前提の名乗りを剥がすと落ち、戻すと通ること。


def _real_plan():
    return [
        {"kind": "stat", "headline": "育児休業給付の手取り比",
         "note": "月給30万円・支給率67%・30日ぶん", "stat": ""},
        {"kind": "stat", "headline": "1か月の差", "stat": "35,709円",
         "note": "給付は非課税・社保免除・賞与なしの前提"},
        {"kind": "chart", "headline": "月給別の手取り比", "bars": [1, 2, 3]},
    ]


def test_故障注入_前提の語を剥がすと落ちる(tmp_path):
    plan = _real_plan()
    assert verify._check_assumptions_on_screen(_plan(tmp_path, plan)) == []
    plan[1]["note"] = "給付は非課税・社保免除・賞与なし"     # 「前提」の2字だけ抜く
    problems = verify._check_assumptions_on_screen(_plan(tmp_path, plan))
    assert problems and "画面に1枚も出ていません" in problems[0], problems


def test_故障注入_前提コマから値を抜くと落ちる(tmp_path):
    plan = _real_plan()
    plan[1]["stat"] = ""
    plan[1]["headline"] = "ここで置いたもの"                # 見出しの「1か月」も値なので消す
    plan[1]["note"] = "給付は非課税という前提"
    plan[0]["note"] = "育休のはなし"                        # もう一方の前提も剥がす
    problems = verify._check_assumptions_on_screen(_plan(tmp_path, plan))
    assert problems and "値が1つも出ていません" in problems[0], problems


def test_ショートの検査に繋がっている():
    """**呼ばれていない検査は、緑のまま死ねます**（`unschedule.py` が実際にそうでした）。

    `check()` の本文を読んで、`portrait`（＝ショート）の枝から
    呼ばれていることを見る。呼び忘れは通算8回あります。
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(verify.check))
    called = {
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_check_assumptions_on_screen" in called
