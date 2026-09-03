"""焼き直しの子の出力を、**終わってからではなく その場で** log へ流すこと。

実測 2026-09-03: `capture_output=True` だったので、25分 かかる焼き直しのあいだ
`data/rebake.log` に在るのは `$ …` の1行だけ。**器ごと回収されると出力は永久に消え**、
きょう死んだ2本（13:12・15:00）はどこまで進んだかを1文字も残していない。
註は `ahead_sweep._run_out()`。
"""
from __future__ import annotations

import sys

from scripts import ahead_sweep


def test_子の出力が全文_返る() -> None:
    rc, out = ahead_sweep._run_out(
        [sys.executable, "-c", "print('あ'); print('い')"], "test", 60)
    assert rc == 0
    assert out.splitlines() == ["あ", "い"]


def test_stderr_も落とさない(capsys) -> None:
    """前は末尾 20行 に切っていて、途中で落ちた回の手がかりがそこで消えていた。"""
    rc, out = ahead_sweep._run_out(
        [sys.executable, "-c",
         "import sys; [print('e%d' % i, file=sys.stderr) for i in range(30)]"],
        "test", 60)
    assert rc == 0
    assert "e0" in out and "e29" in out


def test_終わる前に流れている() -> None:
    """**その場で刷ること。** 子が終わってからまとめて刷る形だと、死んだ回に何も残らない。

    子に「1行 出してから 3秒 眠る」をやらせ、**眠っている 1.5秒 の時点で**
    その行が親の標準出力へ届いているかを見る。
    """
    import io                                                  # noqa: PLC0415
    import sys as _sys                                         # noqa: PLC0415
    import threading                                           # noqa: PLC0415

    code = ("import time\n"
            "print('さき', flush=True)\n"
            "time.sleep(3)\n"
            "print('あと', flush=True)\n")
    buf = io.StringIO()
    seen: list[str] = []

    def _peek() -> None:
        seen.append(buf.getvalue())

    t = threading.Timer(1.5, _peek)
    t.daemon = True
    t.start()
    old_out = _sys.stdout
    _sys.stdout = buf
    try:
        rc, out = ahead_sweep._run_out([_sys.executable, "-c", code], "test", 60)
    finally:
        _sys.stdout = old_out
        t.cancel()
    assert rc == 0
    assert out.splitlines() == ["さき", "あと"]
    assert seen, "覗く前に子が終わってしまった（この検査の組み立てのほう）"
    # **`$ …` の行に子の source がまるごと乗る**ので、素の字で索かないこと
    #     （`print('あと')` の中の「あと」を拾って、この検査が一度 落ちました）。
    assert "[sweep]   さき" in seen[0], "子が終わる前に、最初の行が刷られていない"
    assert "[sweep]   あと" not in seen[0], "この時点でまだ出ていないはずの行が出ている"


def test_黙って固まる子を殺せる() -> None:
    """**1行も来ない子**を取り逃がさないこと（行が来たときだけ見る形の穴）。"""
    rc, _ = ahead_sweep._run_out(
        [sys.executable, "-c", "import time; time.sleep(30)"], "test", 2)
    assert rc == 124


def test_起きなかった子は_127() -> None:
    rc, out = ahead_sweep._run_out(["/nonexistent/binary-xyz"], "test", 5)
    assert rc == 127
    assert out == ""
