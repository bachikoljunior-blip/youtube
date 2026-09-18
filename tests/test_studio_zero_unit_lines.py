"""**日枠が尽きた周の `status` が、台帳だけで出る行を落としていた**（2026-09-19 04:xx・optimizer・Opus・1周1体）。

踏んだ形: `cmd_status` は `yt.channel()` が 403（quotaExceeded）で落ちると **その場で `return`** していた。
註は「ここから先はどの行も Data API を引くので」と書いていたが、**7行 は自分の註に「API 0単位」と書いてある**。
実測: この周の `status` は **13行** で畳まれ、在庫 8本 も 円/月 58倍 も 1行 も出なかった。
値段は「落ちる周 ＝ 日枠が戻る 16:00 JST までの丸ごと（この周から約12周）」で、
**その周こそが `shippable_line` の註が名指しした「窓が開く前に焼いておく周」**。

この検査が縛るのは **2方向**:
 (1) 落ちる枝が `zero_unit_lines` を呼んでいること（呼ばなくなったら落ちる）。
 (2) 本体（通る周）が印字している 0単位 の行と、`zero_unit_lines` の顔ぶれが**そろっていること**
     —— 片方だけ足すと、落ちる周が見落とす／二重に印字する。
"""
import inspect

from studio import cli

# **0単位 の行を出す関数**（見分けは各関数の註の「**API 0単位**」の字）。
# ここに足すときは `cli.zero_unit_lines` と `cmd_status` の本体の両方を見ること。
ZERO_UNIT_CALLS = [
    "trend.channel_line_short",
    "trend.yen_now_short",
    "trend.ungated_short",
    "trend.perf_short",
    "reporting.trial_reach_short",
    "reporting.watched_short",
]


def _status_src() -> str:
    return inspect.getsource(cli.cmd_status)


def test_落ちる枝が0単位の行を出してから畳む():
    """`yt.channel()` の except の中で `zero_unit_lines` を呼んでいること。"""
    src = _status_src()
    head, _, tail = src.partition("except Exception as e:")
    assert tail, "`cmd_status` の `yt.channel()` の except が見あたりません"
    branch = tail[: tail.index("vids = yt.all_videos()")] if "vids = yt.all_videos()" in tail else tail
    assert "zero_unit_lines(" in branch, (
        "日枠が尽きた周（`yt.channel()` が 403）の枝が、台帳だけで出る行を落としています ＝ "
        "その周は `status` 13行 で畳まれ、**出せる在庫**（METHOD §5 が最初に読めと言う行）が見えません")


def test_本体の0単位の行と顔ぶれがそろっている():
    """**両方向**: 本体に在ってヘルパに無い／ヘルパに在って本体に無い、のどちらでも落ちる。"""
    body = _status_src()
    helper = inspect.getsource(cli.zero_unit_lines)
    for name in ZERO_UNIT_CALLS:
        assert name + "(" in body, f"{name} が `cmd_status` の本体から消えています（一覧を直すこと）"
        short = name.split(".")[-1]
        assert short in helper, (
            f"{name} が `zero_unit_lines` にありません ＝ 日枠が尽きた周だけ この行が消えます")


def test_在庫の行は落ちる枝でも出る():
    """`shippable_line` は本体では「枠」の隣に置くので、ヘルパ側の既定が True であること。"""
    helper = inspect.getsource(cli.zero_unit_lines)
    assert "with_shippable: bool = True" in helper
    assert "shippable_line(rows)" in helper


def test_0単位の行だけを呼んでいる():
    """**陽性対照**: `yt.` を呼ぶ行をヘルパへ入れたら落ちる（入れたら日枠が尽きた周で例外になる）。"""
    helper = inspect.getsource(cli.zero_unit_lines)
    body = helper[helper.index('"""', helper.index('"""') + 3):]   # 註（docstring）は除く
    code = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))  # 行の註も除く
    assert "yt." not in code, "`zero_unit_lines` が Data API を引く口を呼んでいます"


def test_台帳が空でも落ちない():
    """報告の台帳や `trend` の中が空の回でも、`status` を止めないこと（各行は try で包む）。"""
    out = cli.zero_unit_lines([], with_shippable=False)
    assert isinstance(out, list)
