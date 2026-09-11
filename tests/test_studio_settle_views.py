"""伸びている本の再生を、**読み直して落ち着かせてから**台帳に書くこと（`studio.yt.settle_stats`）。

2026-09-09 19:1x JST（optimizer・Opus）に足した。**実物で払った値段**:
`status`（19:08）が `gv1u7n_pCAQ` を **823回** と印字した 1分後に、`measure`（19:09）が
**637回** を台帳へ書き（前の行は 711回 ＝ **-74回**）、`trend` は「いちばん大きい減り -74回」と出した。

**同じ `videos.list`・同じ道**です。撃って確かめた（12回・3秒 おき・4本 同時）:

    gv1u7n_pCAQ（齢 9h・伸び中）  **637 が 6回・823 が 6回**（差 186回 ＝ 29%）
    lQHX9LJ80Sg（33h・平ら）      468 が 12回（差 0）
    nQbVxuWpWw8（57h）・PhQ2KvuQASQ（58h）  差 0

＝ **揺れるのは伸びている本だけ**。低い側の 637 は 2時間 前の台帳の値そのもの ＝ 遅れている複製。
真の再生は減らないので **最大がいちばん新しい**。

**陽性対照つき**（下の 2件）: 最大ではなく最後の読みを採る形・読み直しを 1回に落とした形の
どちらでも、この検査が赤くなります。
"""
from __future__ import annotations

import ast
import pathlib
import re
from datetime import timedelta, timezone

import studio.cli as cli
import studio.yt as yt


class _FlappingSvc:
    """`videos.list` を撃つたびに、遅れている複製と新しい複製を交互に返す（実物と同じ形）。"""

    def __init__(self, values: dict[str, list[int]]):
        self.values = values
        self.calls = 0

    def videos(self):
        return self

    def list(self, **kw):
        self.ids = [i for i in kw["id"].split(",") if i]
        return self

    def execute(self):
        n = self.calls
        self.calls += 1
        return {"items": [{"id": i,
                           "statistics": {"viewCount": str(self.values[i][n % len(self.values[i])])}}
                          for i in self.ids]}


def _svc(monkeypatch, values):
    s = _FlappingSvc(values)
    monkeypatch.setattr(yt, "svc", lambda: s)
    return s


def _ago_iso(hours: float) -> str:
    """**齢は「いま」から数える**（2026-09-11 10:4x・optimizer・Opus）。

    日付を焼き込むと、その本は日が経つほど古くなり、**`SETTLE_WITHIN_H` を越えた日に
    検査が黙って赤くなります**。実際に **09/11 10:00 JST（この周）に 3件 が同時に赤く**
    なりました —— 焼き込んであった `_young_iso()`（＝ 09/09 10:00 JST）が
    ちょうど齢 48h を越えた刻です。**壊れたのは道具ではなく検査のデータ**でした
    （§5「教訓の形 3つ目」の族）。

    09/10 06:1x に `test_伸びたまま48hを越えた本が読み直される` の中で同じ穴を 1つ 塞ぎ、
    そこに「日付を焼き込むと明日には別の本を見ることになる」と書いてありましたが、
    **同じファイルの残り 6か所は焼き込んだまま**でした ——
    §5「**教訓の形 2つ目**: 刻ずれを直したら、直した側にその穴の 2つ目の口が無いかを撃つこと」。
    下の `test_この検査は日付を焼き込まない` が、その口を機械で見張ります。
    """
    at = cli.now_jst() - timedelta(hours=hours)
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _young_iso() -> str:
    """`SETTLE_WITHIN_H` の**内側**（齢 47h）。**数ではなく門から引くこと。**"""
    return _ago_iso(cli.SETTLE_WITHIN_H - 1)


def _old_iso() -> str:
    """`SETTLE_WITHIN_H` の**外側**（齢 49h）。"""
    return _ago_iso(cli.SETTLE_WITHIN_H + 1)


def test_揺れる本は最大を採る(monkeypatch):
    s = _svc(monkeypatch, {"A": [637, 823]})
    got = yt.settle_stats(["A"], reads=3)
    assert got["A"]["views"] == 823, "遅れている複製の 637 を書いてはいけない"
    assert got["A"]["views_min"] == 637, "その時刻の下限も残すこと（§7 が下限で比べる）"
    assert got["A"]["n_values"] == 2
    assert s.calls == 3, "読み直しの回数がそのまま単位の数"


def test_落ち着いた本は差が出ない(monkeypatch):
    _svc(monkeypatch, {"B": [468]})
    got = yt.settle_stats(["B"], reads=3)
    # `views_absent` は 2026-09-10 14:2x に足した欄（`yt.views_of` の註）——
    # **欄が在って 0回** と **欄が無い** を分ける。落ち着いた本では立たない。
    assert got["B"] == {"views": 468, "views_min": 468, "n_values": 1,
                        "views_absent": False}


def test_読み直しが1回だと揺れを捕まえられない(monkeypatch):
    """**陽性対照**: `reads` を 1 に落とすと、遅れている複製をそのまま書いてしまう。"""
    _svc(monkeypatch, {"A": [637, 823]})
    got = yt.settle_stats(["A"], reads=1)
    assert got["A"]["views"] == 637 and got["A"]["n_values"] == 1


def test_measure_は揺れた本の最大と下限を台帳に書く(monkeypatch, tmp_path):
    """`cmd_measure` の側 —— 齢の浅い本だけ読み直し、揺れた行にだけ `views_min` を残すこと。"""
    rows = []
    monkeypatch.setattr(cli, "ledger", lambda ev, i, **kw: rows.append({"event": ev, "id": i, **kw}))
    # 齢 47h（束に入る・読み直しの対象）と 49h（束を越えた回は落ちる側）——
    # **どちらも `SETTLE_WITHIN_H` から引く**（`_ago_iso` の註）。
    pub = [{"id": "A", "title": "伸び中", "views": 711, "likes": 4, "comments": 0,
            "publish_at": None, "published_at": _young_iso()},
           {"id": "OLD", "title": "古い", "views": 74, "likes": 0, "comments": 0,
            "publish_at": None, "published_at": _old_iso()}]
    monkeypatch.setattr(yt, "published", lambda h: pub)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [])
    # **揺れるのは伸びている本だけ** —— 落ち着いた本は 3回 とも同じ値を返す（実測 17/17）。
    # 2026-09-10 06:3x から古い本も読み直すので、stub も本ごとに分ける。
    monkeypatch.setattr(yt, "settle_stats", lambda ids, **kw: {
        "A": {"views": 823, "views_min": 637, "n_values": 2},
        "OLD": {"views": 74, "views_min": 74, "n_values": 1}})
    cli.cmd_measure(None)
    got = {r["id"]: r for r in rows if r["event"] == "measured"}
    assert got["A"]["views"] == 823, "台帳には落ち着かせた最大を書くこと"
    assert got["A"]["views_min"] == 637 and got["A"]["n_values"] == 2
    assert "views_min" not in got["OLD"], "**揺れなかった**行に下限の欄を作らないこと"
    assert got["OLD"]["views"] == 74


def _measure_targets(monkeypatch, pub):
    """`cmd_measure` が `settle_stats` に渡した ID を返す（台帳と予約は黙らせる）。"""
    seen = []
    monkeypatch.setattr(cli, "ledger", lambda *a, **kw: None)
    monkeypatch.setattr(yt, "published", lambda h: pub)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [])

    def _settle(ids, **kw):
        seen.extend(ids)
        return {}
    monkeypatch.setattr(yt, "settle_stats", _settle)
    cli.cmd_measure(None)
    return seen


def _book(i, published_at, views=1):
    return {"id": i, "title": i, "views": views, "likes": 0, "comments": 0,
            "publish_at": None, "published_at": published_at}


def test_束に入るなら齢で絞らない(monkeypatch):
    """**2026-09-10 06:3x に広げた** —— 48h を越えた本も読み直すこと。

    もとは「齢 48h まで」で、その註の**覆る条件**は「48h を越えた本で `n_values > 1` の行が
    出たら伸ばす」でした。**その門が在るかぎり、その行は永久に出ません**（渡らない本の
    `n_values` は作られない）。**見えない側を「差が無い」と読む形**なので、門のほうを外した。
    """
    pub = [_book("A", _young_iso()), _book("OLD", _old_iso())]
    assert _measure_targets(monkeypatch, pub) == ["A", "OLD"]


def test_広げても単位は増えない(monkeypatch):
    """**陽性対照の置き換え**（旧「対象を全部に広げると単位が増える」は**外れ**でした）。

    `settle_stats` は ID を 50件ずつ束ねるので、**1件 でも 50件 でも 1回の読みは 1単位**。
    撃って数える —— 束ねを数えないと、広げる手がここで止まります。
    """
    s = _svc(monkeypatch, {f"id{i}": [10] for i in range(50)})
    yt.settle_stats([f"id{i}" for i in range(50)], reads=3)
    assert s.calls == 3, "50件 でも 3回（＝ 1件 のときと同じ単位）"

    s2 = _svc(monkeypatch, {"one": [10]})
    yt.settle_stats(["one"], reads=3)
    assert s2.calls == 3, "1件 でも 3回 ＝ 広げても値段は動かない"


def test_束に入らない回だけ齢で絞る(monkeypatch):
    """**上限は束の大きさ**（`SETTLE_MAX_IDS`）。越えた回は齢の浅い側を採る。"""
    pub = ([_book(f"N{i}", _young_iso()) for i in range(cli.SETTLE_MAX_IDS)]
           + [_book("OLD", _old_iso())])
    got = _measure_targets(monkeypatch, pub)
    assert "OLD" not in got, f"{cli.SETTLE_MAX_IDS} を越えた回は齢 {cli.SETTLE_WITHIN_H}h までへ落とすこと"
    assert len(got) == cli.SETTLE_MAX_IDS


def test_伸びたまま48hを越えた本が読み直される(monkeypatch):
    """**踏んだ実物の形**（2026-09-10 06:1x）: `lQHX9LJ80Sg` は齢 44.2h で **+2回/0.7h** と
    伸びており、48h を越えるのは 09/10 10:02 JST。§7 の「次に見る所 (a)」が読む点はそこ。

    **揺れるのは伸びている本**で、齢はその代理でしかない —— 代理が外れるのがこの本です。
    旧の門では、判定の刻の1点だけが素読みになり、遅れている複製（実測 -28%）を引くと
    包絡が上がらず「平ら」と出ます。
    """
    # **齢は「いま」から数える** —— 日付を焼き込むと、この検査は明日には
    # 「48h 未満の本」を見ることになり、旧の門でも通ってしまう（09/10 06:1x に踏んだ）。
    # **この註は 09/11 10:4x まで、このファイルの中でこの 1件 にしか当たっていませんでした**
    # （`_ago_iso` の註）。
    pub = [_book("GROWING_49H", _old_iso(), views=534)]
    assert _measure_targets(monkeypatch, pub) == ["GROWING_49H"]


def _measure_rows(monkeypatch, pub, settled):
    """`cmd_measure` が台帳へ書いた `measured` の行を、ID 引きで返す。"""
    rows = []
    monkeypatch.setattr(cli, "ledger", lambda ev, i, **kw: rows.append({"event": ev, "id": i, **kw}))
    monkeypatch.setattr(yt, "published", lambda h: pub)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [])
    monkeypatch.setattr(yt, "settle_stats", lambda ids, **kw: {i: settled[i] for i in ids})
    cli.cmd_measure(None)
    return {r["id"]: r for r in rows if r["event"] == "measured"}


def test_読んで揺れなかった行にも_n_values_を書く(monkeypatch):
    """**2026-09-10 07:0x（optimizer・Opus）**: 「揺れた回だけ」だと、**読んで揺れなかった行**と
    **1度も読まれていない行**が台帳の上で見分けられない（どちらも欄が無い）。

    §7 の (h)「48h を越えた本で `n_values > 1` が出るか・**3本 続けて 0件** なら落ち着いている
    と数えてよい」は、**その 0件 の分母**を台帳から数える必要があります。06:3x が門を齢から束へ
    移したのは「渡っていない本を『差が無い』と読む形」を外すためで、**分子だけ直して分母が
    見えないまま**でした（§4 (0-b) の族）。

    **陽性対照**: `extra` を「`n_values > 1` のときだけ」に戻すと、この検査が落ちます。
    """
    pub = [_book("A", _young_iso(), views=711),
           _book("OLD", _old_iso(), views=74)]
    got = _measure_rows(monkeypatch, pub, {
        "A": {"views": 823, "views_min": 637, "n_values": 2},
        "OLD": {"views": 74, "views_min": 74, "n_values": 1}})
    assert got["OLD"]["n_values"] == 1, "**読んだ上で揺れなかった**ことが、台帳に残ること"
    assert "views_min" not in got["OLD"], "下限の欄は、揺れた行だけ（19:1x の決めは変えない）"
    assert got["A"]["n_values"] == 2 and got["A"]["views_min"] == 637


def test_読まれていない行には_n_values_の欄が無い(monkeypatch):
    """**分けられることが、この欄の存在理由**（上の検査の対）。

    束 50件 を越えた回は齢で絞るので、48h 超の本は `settle_stats` に渡りません。
    その行に `n_values` が付いてしまうと、「読んで揺れなかった」と区別できなくなります。
    """
    pub = ([_book(f"N{i}", _young_iso()) for i in range(cli.SETTLE_MAX_IDS)]
           + [_book("OLD", _old_iso())])
    got = _measure_rows(monkeypatch, pub,
                        {b["id"]: {"views": 1, "views_min": 1, "n_values": 1} for b in pub})
    assert "n_values" not in got["OLD"], "**渡っていない本**に欄を作らないこと（＝ 0件 の分母から外れる）"
    assert got["N0"]["n_values"] == 1


def test_measure_は48h超を何本読んだかを印字する(monkeypatch, capsys):
    """**次の回が撃つだけで §7 (h) を読めること**（`wake_placed` を毎周 書き写したのと同じ形・§7 (d)）。

    印字が無いと、(h) を読む回は毎回 台帳を自分で数え直すことになります（この回がそうした）。
    """
    pub = [_book("YOUNG", _young_iso()), _book("OLD1", _old_iso()), _book("OLD2", _old_iso())]
    monkeypatch.setattr(cli.trend, "pair_gap_line", lambda rows: "")
    _measure_rows(monkeypatch, pub, {
        "YOUNG": {"views": 1, "views_min": 1, "n_values": 2},
        "OLD1": {"views": 1, "views_min": 1, "n_values": 1},
        "OLD2": {"views": 1, "views_min": 1, "n_values": 1}})
    out = capsys.readouterr().out
    assert "落ち着かせた: 3本" in out
    assert f"齢 {cli.SETTLE_WITHIN_H}h 超 **2本**" in out, "**分母**（(h) が数える側）を出すこと"
    assert "揺れた **1本**（YOUNG）" in out, "**分子**を、ID つきで出すこと"
    # **揺れた本のうち 48h 超が何本か** ＝ 覆る条件 (3) の分子（2026-09-10 09:2x）。
    # YOUNG は齢が浅いので 0本 —— **ここが 1本 以上 になったら第3の口**。
    assert f"揺れた **1本**（YOUNG）・うち齢 {cli.SETTLE_WITHIN_H}h 超 **0本**" in out


def test_measure_の札は数え直しの道を指さない(monkeypatch, capsys):
    """**道具が古い道を指し続けると、次の回はそれを読んで書きます**（2026-09-10 09:2x・optimizer・Opus）。

    07:0x はこの数を「§7 (h) の分母と分子」と呼びましたが、**08:0x に (h) の道は移りました** ——
    数え直しは周と周のあいだに起き、同じ周の 3回 読みは秒しか離れていない。
    **この印字から「数え直しは 0件」を読んではいけません。**

    **【2026-09-10 10:2x に門を書き換えた】**09:2x の札は「齢 48h 超で割れたら第3の口」と
    名乗っていましたが、**この回に実際に 1本 出て、それは遅れた複製でした**
    （`EkNqtkK49Bw` 96.3h・142 対 141・低いほうは 41分 前の台帳の値）。
    札のままなら次の回は「中央値へ」と読み、**いちばん新しい値を捨てます**。
    いまの札は **(1) 齢で読むなと言い (2) 分子の在り処（`trend.shakes`）を指す**こと。
    """
    old_at = cli.now_jst() - timedelta(hours=cli.SETTLE_WITHIN_H + 1)
    old_iso = old_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pub = [_book("OLD1", old_iso)]
    monkeypatch.setattr(cli.trend, "pair_gap_line", lambda rows: "")
    _measure_rows(monkeypatch, pub, {"OLD1": {"views": 1, "views_min": 1, "n_values": 1}})
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if ln.startswith("落ち着かせた:"))
    assert "覆る条件 (3)" in line, "この数が本当に見張っている物を名指しすること"
    assert "trend.recounts" in line, "数え直しを見る先（`trend.recounts`）を指すこと"
    # **齢で読むな**と言うこと ——09:2x の札はここで「48h 超 ＝ 第3の口」と読ませていた
    assert "「齢 48h 超」を (3) の分子として読まないこと" in line
    # **分子の在り処**を指すこと（指さないと、次の回はこの数を分子として使う）
    assert "trend.shakes" in line, "(3) の分子を数える先を指すこと"


def test_この検査は日付を焼き込まない():
    """**穴の口を機械で見張る**（2026-09-11 10:4x・optimizer・Opus）。

    このファイルの本は `SETTLE_WITHIN_H`（48h）の**内か外か**だけで役が決まります。
    日付を焼き込むと、その本は日が経つほど古くなり、**書いた人が知らない日に内から外へ
    渡って**検査が赤くなります（09/11 10:00 JST に 3件 が同時に赤くなった実物）。

    **手で「もう焼き込まない」と決めても、次に検査を足す回が忘れます** ——
    `studio/livetests.py` の規則A（import で引く ＝ 腐らない）と同じ形で、
    **口のほうを機械で引きます**。

    **陽性対照**: このファイルのどこかに `"2026-09-09T01:00:00Z"` を書き戻すと、この検査が赤くなる。
    """
    tree = ast.parse(pathlib.Path(__file__).read_text())
    # **註と docstring は当たりません** —— 当たるのは「**値として書いた**日付」だけ。
    # （註を外すと、この検査は自分の陽性対照の1行で赤くなります。09/11 10:4x に踏んだ）
    docs = {id(n) for p_ in ast.walk(tree)
            if isinstance(p_, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and (n := (p_.body[0].value if p_.body and isinstance(p_.body[0], ast.Expr)
                       and isinstance(p_.body[0].value, ast.Constant)
                       and isinstance(p_.body[0].value.value, str) else None)) is not None}
    baked = [n.value for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and id(n) not in docs and re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", n.value)]
    assert baked == [], (
        "齢は `_ago_iso`（＝ `cli.SETTLE_WITHIN_H` から引く）で作ること。"
        f"焼き込まれた日付: {baked}")
