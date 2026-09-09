"""`status` は **未返信の行を必ず印字する**こと（`studio.cli.comments_to_show`）。

2026-09-10 01:4x JST（optimizer・Opus）に足した。**この回に踏んだ実物**:
`status` は「**未返信 3件**」と数を出しながら、行のほうを新しい順に 3件 で切っており、
出た 3行 は どれも `[返信ずみ]` でした ＝ **未返信の 3件 は 1行も出ていません**。
その 3件 は 08/21・08/29×2 の古い行で、中に**このチャンネルが受け取った唯一の批評**
（「ＡＩナレーショングダグダ」）が在ります —— §7 の 20:4x の行が
「ここに出し続けること」と書いている当のものが、`status` からは消えていました。

**向きが逆であることが要点**: 新しい順の窓は、**放置が長い行ほど深く隠します**。

**陽性対照つき**（`test_陽性対照_*`）: 未返信を「必ず出す」側から外すと落ちること。
"""
from __future__ import annotations

import studio.cli as cli


def _c(cid, at, answered):
    return {"id": cid, "at": at, "video_id": "v1", "author": "@viewer",
            "text": "t", "answered": answered, "answered_at": at if answered else None}


def _cs():
    """実物と同じ形: 新しい 3件 は返信ずみ・古い 3件 が未返信。"""
    return [_c("n1", "2026-09-09T15:04:00Z", True),
            _c("n2", "2026-09-08T09:41:00Z", True),
            _c("n3", "2026-09-08T03:38:00Z", True),
            _c("o1", "2026-08-29T10:08:00Z", False),
            _c("o2", "2026-08-29T10:08:01Z", False),
            _c("o3", "2026-08-21T05:48:00Z", False)]


def test_未返信の行は全部出る():
    ids = [c["id"] for c in cli.comments_to_show(_cs(), [])]
    assert {"o1", "o2", "o3"} <= set(ids)


def test_数と行が食い違わない():
    """印字する「未返信 n件」と、実際に出る未返信の行数が同じであること（この回の欠陥そのもの）。"""
    cs = _cs()
    shown = cli.comments_to_show(cs, [])
    assert sum(1 for c in shown if not c["answered"]) == sum(1 for c in cs if not c["answered"])


def test_新着も必ず出る():
    """04:2x に決めた「新着は 3件で切って隠さない」を退化させないこと。"""
    cs = _cs()
    fresh = [cs[-1]]
    assert cs[-1]["id"] in [c["id"] for c in cli.comments_to_show(cs, fresh)]


def test_新着と未返信が重なっても_1度しか出ない():
    cs = _cs()
    ids = [c["id"] for c in cli.comments_to_show(cs, [cs[3]])]
    assert ids.count("o1") == 1


def test_返信ずみは新しい順に3件で切る():
    """全部を出すのではない（未返信が 0件 のときに `status` が伸びない）。"""
    cs = _cs()
    shown = cli.comments_to_show(cs, [], keep=2)
    assert [c["id"] for c in shown if c["answered"]] == ["n1", "n2"]


def test_未返信が0件なら3件のまま():
    cs = [_c(f"n{i}", f"2026-09-0{i}T00:00:00Z", True) for i in range(1, 6)]
    assert len(cli.comments_to_show(cs, [])) == 3


def test_陽性対照_未返信を必ず出す側から外すと_数と行が食い違う():
    """この検査が捕まえている当の欠陥（新しい順に 3件 で切るだけの形）を、ここで再現する。"""
    cs = _cs()
    before = (lambda c, f, keep=3: (f + [x for x in c if x not in f])[:keep + len(f)])(cs, [])
    assert sum(1 for c in before if not c["answered"]) == 0
    assert sum(1 for c in cs if not c["answered"]) == 3
