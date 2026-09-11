"""輪（§4 (1)）の答えが、いまの本文のものか（2026-09-11 12:3x・hourly・Opus）。

実物で踏んだ形: 09/12 の本の 11:0x の回が コマ8・9・11 を直したあと read も critique も撃たずに
build → hear → sheet → crosscheck へ進み、METHOD §15 に「輪を開け直して閉じた」と書いた。
12:0x にその本文へ critique を当てたら real 2件（どちらも直した当の コマ11）。

**きょうの状態を不変条件に書かないこと**（§5 の教訓 6つ目）——
本も台帳もこの中で作る。実物の `data/` は 1行 も読まない。
"""
from __future__ import annotations

import pytest

from studio import cli, script


def _seg(say: str, show: str = "画面", sub: str = "", tag: str = "決まり", board=None):
    return script.Segment(say=say, show=show, sub=sub, tag=tag, board=board or ["いち"])


def _script(segs) -> script.Script:
    return script.Script(id="t-loop", date="2026-09-12", title="t", takeaway="t", segments=segs)


def _rows(vid: str, sig, event: str = "critique", at: str = "2026-09-11T10:58:51+09:00"):
    r = {"id": vid, "event": event, "at": at}
    if sig is not None:
        # 版を書かない呼び手は「いまの版の行」を指す（版そのものを試す検査だけ、明示で渡す）
        r["sig"] = sig if ":" in sig else f"{script.LOOP_SIG_VERSION}:{sig}"
    return [r]


def test_指紋は本文で決まる():
    a = _script([_seg("あいうえお。")])
    b = _script([_seg("あいうえお。")])
    assert a.loop_sig() == b.loop_sig()
    assert len(a.loop_sig()) == len(str(script.LOOP_SIG_VERSION)) + 1 + 12


@pytest.mark.parametrize("kw", [
    {"say": "かきくけこ。"}, {"show": "ちがう"}, {"sub": "ちがう"}, {"tag": "結論"}, {"board": ["に"]},
])
def test_輪が読む物が動けば指紋も動く(kw):
    base = _script([_seg("あいうえお。")])
    other = _script([_seg(**{"say": "あいうえお。", **kw})])
    assert base.loop_sig() != other.loop_sig(), kw


def test_輪に渡らない所では指紋は動かない():
    """notes / description は critique にも cold_read にも渡らない（`critic.critique_screen`）。
    ここで動くと、§4 (0) の説明欄の直しのたびに「輪が古い」と鳴る ＝ 狼少年になる。"""
    base = _script([_seg("あいうえお。")])
    other = base.model_copy(update={"notes": "出典を足した", "description": "説明欄を直した"})
    assert base.loop_sig() == other.loop_sig()


def test_指紋が同じなら黙る():
    s = _script([_seg("あいうえお。")])
    assert cli.loop_stale("t-loop", s.loop_sig(), rows=_rows("t-loop", s.loop_sig())) == ""


def test_指紋がちがえば次の1手を名指しする():
    s = _script([_seg("あいうえお。")])
    line = cli.loop_stale("t-loop", s.loop_sig(), rows=_rows("t-loop", "ffffffffffff"))
    assert line, "本文が動いたのに黙った"
    assert "read" in line and "critique" in line, line
    # 印字が言うのは次の1手だけ（§5 の教訓 7つ目）。字数・秒数の門を混ぜない。
    assert "字" not in line and "秒" not in line, line


def test_輪を撃っていない本では黙る():
    s = _script([_seg("あいうえお。")])
    assert cli.loop_stale("t-loop", s.loop_sig(), rows=[]) == ""
    # ほかの本の行は、この本の答えではない
    assert cli.loop_stale("t-loop", s.loop_sig(), rows=_rows("ほかの本", "ffffffffffff")) == ""


def test_指紋を書く前の行では黙る():
    """2026-09-11 12:3x より前の `critique` / `cold_read` の行には `sig` が無い。
    「古い」とも「新しい」とも言えないので黙る —— 嘘の印字より安い。"""
    s = _script([_seg("あいうえお。")])
    assert cli.loop_stale("t-loop", s.loop_sig(), rows=_rows("t-loop", None)) == ""


def test_いちばん新しい行を見る():
    """輪は read → critique の順で撃つので、同じ本に 2行 並ぶ。見るのは末尾。"""
    s = _script([_seg("あいうえお。")])
    rows = (_rows("t-loop", "ffffffffffff", "cold_read", "2026-09-11T10:00:00+09:00")
            + _rows("t-loop", s.loop_sig(), "critique", "2026-09-11T10:05:00+09:00"))
    assert cli.loop_stale("t-loop", s.loop_sig(), rows=rows) == ""
    rows2 = (_rows("t-loop", s.loop_sig(), "cold_read", "2026-09-11T10:00:00+09:00")
             + _rows("t-loop", "ffffffffffff", "critique", "2026-09-11T10:05:00+09:00"))
    assert cli.loop_stale("t-loop", s.loop_sig(), rows=rows2)


def test_陽性対照_実物の形をそのまま通す():
    """09/12 の本で実際に起きた並び（直す前の指紋で輪を閉じ、そのあと 3コマ 直した）を組んで、
    印字が出ることを確かめる。**壊したら落ちるか**も同じ所で撃つ（下）。"""
    before = _script([_seg("決まりでは、1年にみたないはんぱは、1日でも1年とします。"),
                      _seg("たとえば、同じ1500万円を、20年はたらいてもらっていたら。", tag="前提")])
    after = _script([_seg("決まりでは、1年にとどかない日数も、1年ぶんです。"),
                     _seg("たとえば、20年でやめていたらどうなるか。", tag="前提")])
    rows = _rows("t-loop", before.loop_sig())
    assert cli.loop_stale("t-loop", after.loop_sig(), rows=rows), "直したのに黙った"
    # 陽性対照: 直していなければ鳴らない（＝ この印字は「本文が動いたこと」だけを見ている）
    assert cli.loop_stale("t-loop", before.loop_sig(), rows=rows) == ""


def test_板の行を割り直しただけでは指紋は動かない():
    """2026-09-11 13:1x に `loop_sig` の覆る条件 (1) を実物で引いた ——
    コマ11 の板 ['1年にとどかない日数', 'も1年ぶんになる'] は**語の途中で折れて**おり
    （sheet で見えた）、直したのは行の割り方だけ。`critique_screen` に渡るのは板の中身なので、
    ここで指紋が動くと「輪を撃ち直せ」が鳴らない回に鳴る（狼少年）。"""
    a = _script([_seg("あいうえお。", board=["1年にとどかない日数", "も1年ぶんになる"])])
    b = _script([_seg("あいうえお。", board=["1年にとどかない日数も", "1年ぶんになる"])])
    assert a.loop_sig() == b.loop_sig()


def test_板の中身が変われば指紋は動く():
    """陽性対照: 継いで署名しても、**中身**の直しは拾う（継ぎで全部 潰していないこと）。"""
    a = _script([_seg("あいうえお。", board=["1年にとどかない日数も"])])
    b = _script([_seg("あいうえお。", board=["1年をこえた日数も"])])
    assert a.loop_sig() != b.loop_sig()


def test_指紋は版を頭に持つ():
    s = _script([_seg("あいうえお。")])
    assert s.loop_sig().startswith(f"{script.LOOP_SIG_VERSION}:")


def test_版が違う行とは本文を比べない():
    """作り方を変えた回は、台帳の指紋が全部 合わなくなる。そのまま鳴らすと
    「本文が動いた」と嘘をつく（2026-09-11 13:2x に 1度 そう出た）。"""
    s = _script([_seg("あいうえお。")])
    line = cli.loop_stale("t-loop", s.loop_sig(), rows=_rows("t-loop", "1:ffffffffffff"))
    assert "作り方" in line and "本文が動いたとは言えません" in line, line
    # 版が同じで中身が違う行は、これまでどおり「撃ち直せ」
    same_ver = f"{script.LOOP_SIG_VERSION}:ffffffffffff"
    other = cli.loop_stale("t-loop", s.loop_sig(), rows=_rows("t-loop", same_ver))
    assert "read" in other and "作り方" not in other, other
