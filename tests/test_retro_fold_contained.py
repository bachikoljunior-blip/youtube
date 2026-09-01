"""**同じ1件が複数の語に割れて、持ち越しが実際より長く見えていた**（2026-09-01）。

## 何を守っているか

`docs/trigger_main.md` §2.7 は「持ち越しが出ていたら、そこから選ぶのが既定」と
言っています。**この一覧は次の回の仕事を決めます。**

実測（2026-09-01 15:0x・23語の一覧）——

    7回  python scripts/pool_drain.py --apply
    4回  [pool] [!]
    3回  pool_drain.py --apply

**3語とも同じ1件**（22:00 公開の本のサムネイルを押す手）です。割れていると:

1. 一覧が長く見え、選ぶのに時間がかかる
   （直近の (a2) 問い1 は「何を出すか決めるところ」が4〜5割）
2. `worked_on()` の「実物に当たった回」が形ごとにばらける
3. `_sinks()` の枠待ちの印が**長い形にしか当たらない**
   —— 2026-09-01 11:5x の申し送り4 が、まさにこれを名指ししています

2026-09-01 の 10:2x と 11:5x の申し送りが、**2周 続けて同じ例を挙げて**
「直す先は `retro.quoted_tokens()` か `noise_tokens()`」と書いていました。

## 何を「同じ1件」と見るか

**部分文字列**であること、かつ**語の切れ目**で入っていること。
切れ目を見るのは `grid` が `guard_grid` を飲み込まないためです。
**日付の重なりは見ません** —— `--unschedule`（09:4x〜10:4x）と
`scripts/reschedule.py --unschedule <古い方>`（11:1x〜13:3x）は一度も
重なりませんが、同じ1件です（前半の回が短い形で書いただけ）。
"""
from __future__ import annotations

from scripts import retro


def test_短い形は長い形へ畳まれ_回数が足される():
    seen = {
        "python scripts/pool_drain.py --apply": ["2026-09-01 08:1x",
                                                 "2026-09-01 09:4x"],
        "pool_drain.py --apply": ["2026-09-01 10:2x"],
    }
    out, folded = retro.fold_contained(seen)
    assert "pool_drain.py --apply" not in out
    assert folded["pool_drain.py --apply"] == \
        "python scripts/pool_drain.py --apply"
    # **回数は畳んだ先へ足す。** 落とすと「3周 運ばれた」が「2周」に見えます。
    assert len(out["python scripts/pool_drain.py --apply"]) == 3


def test_日付が一度も重ならなくても畳む():
    # 実測の形。前半の回が短い形、後半の回が長い形で書いています。
    seen = {
        "--unschedule": ["2026-09-01 09:4x", "2026-09-01 10:2x",
                         "2026-09-01 10:4x"],
        "scripts/reschedule.py --unschedule <古い方>":
            ["2026-09-01 11:1x", "2026-09-01 11:5x", "2026-09-01 13:3x"],
    }
    out, folded = retro.fold_contained(seen)
    assert list(out) == ["scripts/reschedule.py --unschedule <古い方>"]
    assert len(out["scripts/reschedule.py --unschedule <古い方>"]) == 6


def test_語の切れ目でないところは畳まない():
    # `grid` は `guard_grid` の一部ですが、**別の語**です。
    seen = {"grid": ["a"], "guard_grid": ["b"]}
    out, folded = retro.fold_contained(seen)
    assert folded == {}
    assert set(out) == {"grid", "guard_grid"}


def test_畳んだ先がさらに畳まれても_鎖の先まで行く():
    seen = {"catchup_grid()": ["a"],
            "hendo.catchup_grid()": ["b"],
            "src/calc/hendo.catchup_grid()": ["c"]}
    out, folded = retro.fold_contained(seen)
    assert list(out) == ["src/calc/hendo.catchup_grid()"]
    assert len(out["src/calc/hendo.catchup_grid()"]) == 3


def test_角括弧だけの語は道具の印字():
    assert retro.is_tool_mark("[pool] [!]")
    assert retro.is_tool_mark("[marker]")
    # ファイルや関数を名指ししている語は、印字ではありません。
    assert not retro.is_tool_mark("pool_drain.py --apply")
    assert not retro.is_tool_mark("[!] 日枠が尽きています")


def test_種類の語は_畳む前に外す():
    """**外すのが先、畳むのが後**（この回に、逆に書いて踏んだ）。

    先に畳むと `fix`（種類として外す語）が長い語へ回数を持ち込み、
    **外したはずの4回が一覧の上位に戻ります**（実測）。
    """
    out, dropped = retro.carry_over()
    assert "fix" not in out
    folded = set(dropped.get("同じ1件", []))
    assert "fix" not in folded, \
        "種類の語が畳まれています（外すのが先、畳むのが後）"


def test_畳んだ語は語彙に残る():
    """`run_marker.py --closes` は `dropped` も語彙に使います。

    ここから落とすと、**短い形で `--closes` を打った回に
    「一覧に無い語」と鳴ります。**
    """
    out, dropped = retro.carry_over()
    for tok in dropped.get("同じ1件", []):
        assert any(tok in longer for longer in out), \
            f"{tok!r} の畳んだ先が一覧にありません"
