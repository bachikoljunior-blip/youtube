"""`src/arg_gaps.py` —— **節から届く道が無い引数**を拾えているか。

**故障注入を両向きに掛けます。** 当たりを見つけることと、
**届いているものを鳴らさないこと**は別の性質で、片方だけでは
「全部鳴らす検査」と区別がつきません（`docs/JOURNAL.md` 2026-08-16）。
"""
from src import arg_gaps

# **実物そのもの**（2026-08-18 23:0x に直す前の `shobyo`）。
# `premiums` は率を受け取れるのに、`net_month` が渡していなかった。
BLOCKED = '''
def premiums(pay, care=False, health_rate=0.05, pension_rate=0.0915):
    return {"total": int(pay * health_rate) + int(pay * pension_rate)}


def net_month(pay, care=False, resident_tax=0):
    return {"net": pay - premiums(pay, care)["total"] - resident_tax}


if __name__ == "__main__":
    print(net_month(300_000))
'''

# **直したあと。** 呼ぶ側が同じ名前の引数を持ったので、節から届く。
REACHABLE = BLOCKED.replace(
    "def net_month(pay, care=False, resident_tax=0):",
    "def net_month(pay, care=False, resident_tax=0, health_rate=0.05,"
    " pension_rate=0.0915):").replace(
    "premiums(pay, care)", "premiums(pay, care, health_rate, pension_rate)")


def _args(source: str) -> set[str]:
    return {r["arg"] for r in arg_gaps.scan_source(source)}


def test_塞がっている引数を拾う():
    assert _args(BLOCKED) == {"health_rate", "pension_rate"}
    # `care` は鳴りません —— `net_month` が同じ名前で受けて渡しているので、
    # **節からはそこ経由で届きます。**


def test_道を繋いだら鳴らない():
    """**偽陽性の側。** 呼ぶ側が同名の引数を持てば、節から届く。"""
    got = _args(REACHABLE)
    assert "health_rate" not in got and "pension_rate" not in got


def test_節が直に呼ぶ関数は鳴らない():
    """`__main__` が直接呼んでいれば、節がその場で渡せる。"""
    src = '''
def grid(pay, care=False):
    return [pay, care]


if __name__ == "__main__":
    print(grid(300_000))
'''
    assert _args(src) == set()


def test_check_tables_は節に数えない():
    """**ここを節と数えると本物が消えます**（実物で消えました）。

    `check_tables()` は制度の値の検査で、節を1つも出しません。
    """
    src = '''
def inner(pay, rate=0.05):
    return pay * rate


def check_tables():
    assert inner(100, rate=0.06)


def outer(pay):
    return inner(pay)


if __name__ == "__main__":
    print(outer(100))
'''
    assert "rate" in _args(src)


def test_既定値の無い引数は鳴らない():
    """既定値が無ければ、呼ぶ側は必ず渡しています（省ける軸ではない）。"""
    src = '''
def inner(pay, rate):
    return pay * rate


def outer(pay):
    return inner(pay, 0.05)


if __name__ == "__main__":
    print(outer(100))
'''
    assert _args(src) == set()


def test_誰にも呼ばれない関数は鳴らない():
    """呼ばれていない関数は、**引数の話ではなく死んだ関数**です。"""
    src = '''
def orphan(pay, rate=0.05):
    return pay * rate


if __name__ == "__main__":
    print(1)
'''
    assert _args(src) == set()


def test_実物で当たりが出る():
    """**故障注入ではなく実データ。** 空振りでないことを見ます。"""
    rows = arg_gaps.scan_all()
    assert len(rows) >= 20, len(rows)
    tables = {r["calc"] for r in rows}
    assert len(tables) >= 10, tables
    # 全部の表が鳴っていたら「全部鳴らす検査」と区別がつかない
    assert len(tables) < 54, tables
