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
    assert got["B"] == {"views": 468, "views_min": 468, "n_values": 1}


def test_読み直しが1回だと揺れを捕まえられない(monkeypatch):
    """**陽性対照**: `reads` を 1 に落とすと、遅れている複製をそのまま書いてしまう。"""
    _svc(monkeypatch, {"A": [637, 823]})
    got = yt.settle_stats(["A"], reads=1)
    assert got["A"]["views"] == 637 and got["A"]["n_values"] == 1


def test_measure_は揺れた本の最大と下限を台帳に書く(monkeypatch, tmp_path):
    """`cmd_measure` の側 —— 齢の浅い本だけ読み直し、揺れた行にだけ `views_min` を残すこと。"""
    rows = []
    monkeypatch.setattr(cli, "ledger", lambda ev, i, **kw: rows.append({"event": ev, "id": i, **kw}))
    # 齢 9h（揺れる・読み直しの対象）と 200h（対象外）
    pub = [{"id": "A", "title": "伸び中", "views": 711, "likes": 4, "comments": 0,
            "publish_at": None, "published_at": "2026-09-09T01:00:00Z"},
           {"id": "OLD", "title": "古い", "views": 74, "likes": 0, "comments": 0,
            "publish_at": None, "published_at": "2026-09-01T01:00:00Z"}]
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
    pub = [_book("A", "2026-09-09T01:00:00Z"), _book("OLD", "2026-09-01T01:00:00Z")]
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
    pub = ([_book(f"N{i}", "2026-09-09T01:00:00Z") for i in range(cli.SETTLE_MAX_IDS)]
           + [_book("OLD", "2026-09-01T01:00:00Z")])
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
    # 「48h 未満の本」を見ることになり、旧の門でも通ってしまう（この回に踏んだ）。
    old_at = (cli.now_jst() - timedelta(hours=cli.SETTLE_WITHIN_H + 1))
    pub = [_book("GROWING_49H", old_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 views=534)]
    assert _measure_targets(monkeypatch, pub) == ["GROWING_49H"]
