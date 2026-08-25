"""**実物を動かしたのに、控えに書き戻していない口を、全部まとめて塞ぐ。**

2026-08-18 に実測で踏みました。`reschedule.py --move` を6本撃つと、
YouTube 側の `publishAt` は動くのに、控え（`data/uploaded.jsonl`）は
**6本とも 09/27 のまま**でした。`--compact` は控えだけを見るので、
次の回は**動かした後の姿を知らないまま**割り当てを組みます。

**同じ形が、これで3回目です。**

    8/18 16:0x  `--compact` が控えから予約を書き戻していた（実測8/10が復活）
    8/18 16:0x  `unschedule` が控えに書き戻していなかった
    8/18 16:3x  `--move` と `reschedule.py --unschedule` が書き戻していなかった ← ここ

1件ずつ塞いでも、**素通りさせている側**が同じなら次も出ます。
だからここでは「この呼び出しが在るか」ではなく、
**`_update()` を呼ぶ場所は必ず `dupes.retime()` も呼ぶ**という形そのものを見ます。
新しく口を足した回も、この検査に当たります。
"""
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "reschedule.py"


def _calls(body: list[ast.stmt]) -> set[str]:
    """このブロックが直接呼んでいる名前（入れ子の関数定義には入らない）。"""
    names: set[str] = set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    names.add(f.id)
                elif isinstance(f, ast.Attribute):
                    base = f.value
                    if isinstance(base, ast.Name):
                        names.add(f"{base.id}.{f.attr}")
    return names


def test_実物を動かす場所は必ず控えにも書き戻している():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == "_update":
            continue          # 定義そのものは対象外
        names = _calls(body)
        if "_update" in names and "dupes.retime" not in names:
            bad.append(getattr(node, "lineno", "?"))
    assert not bad, (
        f"scripts/reschedule.py の {bad} 行目のブロックが `_update()` を呼ぶのに "
        "`dupes.retime()` を呼んでいません。**実物だけ動いて控えが古いまま**になり、"
        "`--compact` が次の回に古い時刻で割り当てを組みます")


def test_move_と_unschedule_の両方に書き戻しがある():
    """**片方だけ直す**が3回続いているので、両方あることを名指しで見る。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "dupes.retime(vid, iso)" in src, \
        "--move が控えに書き戻していない"
    assert "dupes.retime(args.unschedule, None)" in src, \
        "reschedule.py --unschedule が控えに書き戻していない"


# --- **検査は速さを見ません**（2026-08-18 に踏んだ） -----------------------
#
# `src/calc/inshi.py` の `zeinuki_limit()` を1円ずつの数え上げで書いたところ、
# **答えは全部合っていて `check_tables()` も緑**でしたが、第17号の10億円の境目で
# 約1億回まわり、**節を数える `tests/test_topic_stock.py` が9分を超え**、
# 掃引を抜いた検査全体が 900秒で終わらなくなりました。
#
# **値の検査（`_checks`）は、この壊れ方を1つも捕まえません。**
# だから、節を数える側の入口に「速さ」の検査を1つ置きます。

def test_節を数えるのに使う関数が速いこと():
    """`src/calc/` の表を1回ずつ回すのに、目に見える時間がかからないこと。

    **上限は「人が待てる時間」ではなく、`test_topic_stock` が回る前提**です。
    1本あたり1秒を超える表があると、48本で1分を超え、
    それを何度も呼ぶ検査が分単位になります。
    """
    import importlib
    import time
    from pathlib import Path

    calc_dir = Path(__file__).resolve().parent.parent / "src" / "calc"
    slow = []
    for path in sorted(calc_dir.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        mod = importlib.import_module(f"src.calc.{path.stem}")
        check = getattr(mod, "check_tables", None)
        if check is None:
            continue
        # **壁時計ではなく、この処理が使った CPU 時間で見ること**（2026-08-26）。
        # `time.monotonic()` は**同じ機械で他が走っているだけで伸びます。**
        # 実測: このコンテナはきょうだいの検査と同時に回るので、3本 並んだ回に
        # `nenkin` が 1.0秒 を超えて落ちました。**単独で測ると 0.51秒**で、
        # 63本の合計でも 1.5秒 です。**遅い表は1つもありませんでした。**
        #
        # 落ちる理由が「隣が忙しい」なら、**この門は乱数**です。
        # 乱数の門は、常時赤と同じ壊れ方をします —— 鳴っても誰も見に行かなくなる。
        #
        # `time.process_time()` は**自分が使った CPU だけ**を数えるので、
        # 隣の忙しさでは動きません。そして、この検査が本当に捕まえたいもの
        # （上の註の「1円ずつ数え上げて約1億回まわる」）は **CPU を焼く**ので、
        # measure の向きは変わりません。**取りこぼすのは I/O 待ちで遅い表**ですが、
        # `src/calc/` は外を叩きません（叩いたらそれ自体が別の欠陥）。
        start = time.process_time()
        check()
        took = time.process_time() - start
        if took > 1.0:
            slow.append((path.stem, round(took, 2)))
    assert not slow, (
        f"check_tables() に1秒より長くかかる表があります: {slow}。"
        "値は合っていても、節を数える検査が分単位になります"
    )
