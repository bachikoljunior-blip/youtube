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
    monkeypatch.setattr(yt, "settle_stats", lambda ids, **kw: {
        i: {"views": 823, "views_min": 637, "n_values": 2} for i in ids})
    cli.cmd_measure(None)
    got = {r["id"]: r for r in rows if r["event"] == "measured"}
    assert got["A"]["views"] == 823, "台帳には落ち着かせた最大を書くこと"
    assert got["A"]["views_min"] == 637 and got["A"]["n_values"] == 2
    assert "views_min" not in got["OLD"], "読み直していない本に下限の欄を作らないこと"
    assert got["OLD"]["views"] == 74


def test_読み直しは齢の浅い本だけ(monkeypatch):
    """**陽性対照**: 対象を全部に広げると単位が増える —— 渡した ID を数えて押さえる。"""
    seen = []
    pub = [{"id": "A", "title": "新", "views": 1, "likes": 0, "comments": 0,
            "publish_at": None, "published_at": "2026-09-09T01:00:00Z"},
           {"id": "OLD", "title": "古", "views": 74, "likes": 0, "comments": 0,
            "publish_at": None, "published_at": "2026-09-01T01:00:00Z"}]
    monkeypatch.setattr(cli, "ledger", lambda *a, **kw: None)
    monkeypatch.setattr(yt, "published", lambda h: pub)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [])

    def _settle(ids, **kw):
        seen.extend(ids)
        return {}
    monkeypatch.setattr(yt, "settle_stats", _settle)
    cli.cmd_measure(None)
    assert seen == ["A"], f"齢 {cli.SETTLE_WITHIN_H}h までの本だけを読み直すこと"
