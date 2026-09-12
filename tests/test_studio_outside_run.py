"""`trend.outside_checks` / `outside_runs` / `outside_line`
—— **§4 (0-c) の「外を1回 引く」の連を、本で数える口**。

2026-09-12 20:0x JST・optimizer・Opus。**`hourly` が §16 の申し送り (8) で渡した口**
（§5「申し送りに書いた欠陥は、書いた時点で相手の物」）。

**族の 4例目**（`blind_run` 16:0x／`reporting_empty_run` 18:4x／`late_run` 04:3x と同じ ——
「N本 続いたら」と覆る条件に書きながら、**N を数える物が無い**）。
§4 (0-c) の覆る条件 (1) の単位は **本** ですが、それまで数えていたのは **引きの回数**で、
09/09 の本の 3回 が「2本 ＋ 1本目の 0」と書かれていました（**全部 同じ 1本**）。

**前半（公表ページ）と後半（改正）は別の連**（§4 19:4x の決め）——
09/13 の本は公表ページを 4回 引きながら、改正の側は 1度も引かれていませんでした。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**）。この回に動かして確かめた
（`.pyc` を毎回 消してから・11つ目）:
  * 2つ の連を 1つ にする（`reform_run` を `page_run` で返す）→ **3件**
    （`test_出たで連は切れる`・`test_側は別に数える`・`test_片側だけが門に届く`）
  * `sec < 9` の門を外す → **6件**（`test_手順の節の例は拾わない` ほか ＝ §4 が本の 1本 に化ける）。
    **1度目の対照は落ちませんでした** —— 検査のデータが §4 に**書き方の例**（`出た/0`）しか
    持っておらず、**その形は正規表現と一致しません**（＝ 門を外しても拾う物が無い）。
    **緑だったのは道具ではなく、検査のデータのほう**でした（§5 教訓の形 3つ目・4つ目）。
    **埋まった形の例を §4 に置いてから、落ちました。**
  * 連を「新しいほうから」ではなく全部の 0 の数にする → **1件**（`test_出たで連は切れる`）
  * 行の無い本を `0` として数える → **4件**（`test_行の無い本は数えない`・`test_出たで連は切れる`・
    `test_側は別に数える`・`test_片側だけが門に届く` ＝ **本の数はほとんどの行に出ます**）
  * `trend` の並びから外す → **1件**（`test_trendの並びに出る`）
**ファイル単独でも撃ちました**（§5 教訓の形 11つ目）。
"""
from studio import trend


def _doc(*secs: str) -> str:
    return "\n".join(secs)


SEC4 = """## 4. 毎本の出口
    (0-c) **ファイルの外を1回 引く**
        **手**: その本の節に 1行 —— `(0-c) 公表ページ: 出た/0 ・改正: 出た/0`
        例（**手順の節に在る ＝ 本の 1行 ではない**）: `(0-c) 公表ページ: 0 ・改正: 0`
"""


def _book(n: int, page: str | None = None, reform: str | None = None) -> str:
    head = f"## {n}. {n - 8}本目（2026-09-{n:02d}・`x`）"
    if page is None:
        return head + "\n本文だけ。\n"
    return head + f"\n**`(0-c) 公表ページ: {page} ・改正: {reform}`**（この本の 1行）。\n"


def _write(tmp_path, *parts: str):
    p = tmp_path / "METHOD.md"
    p.write_text(_doc(*parts), encoding="utf-8")
    return p


def test_本の節の1行を拾う(tmp_path):
    p = _write(tmp_path, SEC4, _book(16, "0", "0"))
    rows = trend.outside_checks(p)
    assert [(r["sec"], r["page"], r["reform"]) for r in rows] == [(16, "0", "0")]


def test_手順の節の例は拾わない(tmp_path):
    """§4 (0-c) の本文に在る**書き方の例**（`出た/0`）を、本の 1行 と読まないこと。"""
    p = _write(tmp_path, SEC4)
    assert trend.outside_checks(p) == []


def test_行の無い本は数えない(tmp_path):
    """§14・§15 には行が無い ＝ **そこは復元せずに §16 から数え始める**（§4 19:4x）。"""
    p = _write(tmp_path, SEC4, _book(14), _book(15), _book(16, "0", "0"))
    o = trend.outside_runs(p)
    assert o["books"] == 1 and o["page_run"] == 1 and o["reform_run"] == 1


def test_出たで連は切れる(tmp_path):
    """連は**新しいほうから**。古い 0 は、あとの「出た」で切れる。"""
    p = _write(tmp_path, SEC4, _book(14, "0", "0"), _book(15, "出た", "0"),
               _book(16, "0", "0"))
    o = trend.outside_runs(p)
    assert o["books"] == 3 and o["page_run"] == 1 and o["reform_run"] == 3


def test_側は別に数える(tmp_path):
    """**前半が済むと後半も済んだことになる**のが、この抜けの口（§4 19:4x）。"""
    p = _write(tmp_path, SEC4, _book(15, "出た", "0"), _book(16, "出た", "0"))
    o = trend.outside_runs(p)
    assert o["page_run"] == 0 and o["reform_run"] == 2


def test_片側だけが門に届く(tmp_path):
    """門に届いた側だけを名指しし、**縮める判定は `hourly`** と言うこと（§5）。"""
    p = _write(tmp_path, SEC4, _book(14, "出た", "0"), _book(15, "出た", "0"),
               _book(16, "出た", "0"))
    s = trend.outside_line(p)
    assert "改正 の側は門に届きました" in s and "判定は `hourly`" in s
    assert "公表ページ 0 が 0本" in s


def test_門の下では黙る(tmp_path):
    p = _write(tmp_path, SEC4, _book(16, "0", "0"))
    s = trend.outside_line(p)
    assert "門に届きました" not in s and "門 3本" in s


def test_0本は引いていないと読ませない(tmp_path):
    """`§4 (0-b)` の族（0件 を「大丈夫」と読まない）。この 0 は**記録の形が無い**の 0。"""
    p = _write(tmp_path, SEC4)
    s = trend.outside_line(p)
    assert "記録の形が無い" in s


def test_trendの並びに出る():
    """毎周 印字されること —— 次の回が前の回の端末の出力を覚えていなくてよい。"""
    body = "\n".join(trend.lines([]))
    assert "(0-c) の外の引き" in body


def test_実物のMETHODから読める():
    """**実物の形で拾えること**（§5 教訓の形 4つ目 ＝ 手で作った検査データだけで閉じない）。"""
    rows = trend.outside_checks()
    assert rows and rows[-1]["sec"] >= 16
    assert rows[-1]["page"] in ("0", "出た")
