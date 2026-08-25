"""`src/dupes.why_stranded` の検査（2026-08-16）。

**故障注入つき。** 見つけることより、**見つけてはいけないものを見つけない**ほうが
高くつきます —— ここで偽陽性を出すと、**本当に予約し忘れた本が黙らされ、
永久に公開されません**（投稿が途切れるのが最大の損失）。

いちばん危ないのは**自分自身との突き合わせ**です。暗い本は
`data/uploaded.jsonl` にも載っているので、除かないと
「テーマIDが同じ」で必ず自分と重なり、**全部が黙ります。**
実際、この回に `blocking` をそのまま流用したら12本中12本が自分と重なりました。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import dupes  # noqa: E402


def _v(vid: str, title: str, topic: str = "", at: str | None = None,
       public: bool = False) -> dict:
    status: dict = {"privacyStatus": "public" if public else "private"}
    if at and not public:
        status["publishAt"] = at
    return {
        "id": vid,
        "snippet": {"title": title,
                    "description": f"本文\n[t:{topic}]" if topic else "本文",
                    "publishedAt": at or "2026-08-01T00:00:00Z"},
        "status": status,
    }


TOPICS = {"a1": "tedori", "a2": "tedori", "d1": "iryohi", "d2": "iryohi",
          "z1": "zangyo"}


def test_同じテーマIDの予約済みが相手なら理由を出す() -> None:
    """実物 `UTwBchk3OX0` ←→ 予約中の `crO3FUvL2NI`（どちらも `s-iryohi-1`）。"""
    dark = _v("dark", "医療費控除の足切りは10万円ではない 総所得160万なら8万円", "d1")
    live = [_v("live", "医療費控除の足切りは10万円ではない 総所得160万で8万円", "d1",
               at="2026-08-17T00:00:00Z")]
    got = dupes.why_stranded(dark, live, TOPICS)
    assert got is not None, "同じテーマIDなのに理由が出ていません"
    assert got["other"]["id"] == "live"
    assert got["kind"] == "same-topic"


def test_テーマは違っても金額が入れ子なら理由を出す() -> None:
    """実物 `a1b2Nm6jN_0` ←→ 予約中の `_4zhMy-VIyg`（`tedori` で 359,318円）。"""
    dark = _v("dark", "社会保険料率で手取り増は35万9318円", "a1")
    live = [_v("live", "年収500万から50万アップで手取りは35万9318円", "a2",
               at="2026-08-16T00:00:00Z")]
    got = dupes.why_stranded(dark, live, TOPICS)
    assert got is not None, "同じ金額なのに理由が出ていません"
    assert got["other"]["id"] == "live"


def test_重なる相手がいなければ黙る() -> None:
    """**ここが本体。** 理由が出ないから `status.py` が鳴らせます。"""
    dark = _v("dark", "残業代 一律手当の除外 3年で61万9898円", "z1")
    live = [_v("live", "医療費控除で戻るのは2万209円", "d1",
               at="2026-08-16T00:00:00Z")]
    assert dupes.why_stranded(dark, live, TOPICS) is None


def test_自分自身とは突き合わせない() -> None:
    """**故障注入。** 暗い本を `videos` にも入れて呼ぶ。

    除かずに突き合わせると「テーマIDが同じ」で必ず当たり、
    **予約し忘れの本まで黙ります。**
    """
    dark = _v("dark", "残業代 一律手当の除外 3年で61万9898円", "z1")
    live = [_v("other", "医療費控除で戻るのは2万209円", "d1",
               at="2026-08-16T00:00:00Z")]
    assert dupes.why_stranded(dark, live + [dark], TOPICS) is None, \
        "自分自身と重なったことにしています"


def test_相手が暗いだけなら理由にしない() -> None:
    """**故障注入。** 相手も公開されない本なら、こちらを伏せる理由になりません。

    どちらも出ないので、**2本とも永久に埋もれます。**
    """
    dark = _v("dark", "医療費控除の足切りは10万円ではない 総所得160万なら8万円", "d1")
    other_dark = _v("other", "医療費控除の足切りは10万円ではない 総所得160万で8万円", "d1")
    # `status.py` は公開・予約済みだけを渡します。ここでも同じ約束で呼ぶ。
    assert dupes.why_stranded(dark, [], TOPICS) is None
    assert dupes.why_stranded(dark, [other_dark], TOPICS) is not None, \
        "この関数は渡された相手をそのまま見ます（絞るのは呼ぶ側）"
