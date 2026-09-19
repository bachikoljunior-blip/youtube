"""`studio/topics.py` の「うちの実測」側（2026-09-19 21:xx・optimizer・Opus 5・1周 1体）。

**なぜ在るか**: `topics.line()` は「**次の台本の題材は、ここの上から採ること**」と言っていて、
その段は **corpus ＝ よその本の、検索の上位**でした。この周に台帳で照らしたら、
うちの実測は corpus と**逆を向いていました**:

    `遺族年金 いくら 計算`  corpus 中央 59,469（`dense`）  **うちのショート 9回**（1本）
    `加給年金 いくら`       corpus 中央 78,824（`lottery`） **うちのショート 970回**（1本）

この 4つ を門にします（どれも、この周に**実物で踏んだ**形です）:

 1. **形を混ぜない** —— 長尺を入れると `加給年金 いくら` は 970 → **中央 8回** に化けます
 2. **齢の門** —— 予約ずみ・公開直後の 0回 を入れると `退職金 税金 いくら` が **中央 0回** に化けます
 3. **台本ごとに いちばん大きい再生** —— 置き直した本の 0回 を採らない
 4. **頭の錨は長いほうが勝つ** —— `遺族厚生年金` の本が `年金 手取り いくら` に化けない
"""
from __future__ import annotations

import datetime as dt
import json

from studio import topics

JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 19, 21, 0, tzinfo=JST)

#: corpus の代わり（`by_query` は `MIN_BOOKS`=5 本 以上の語だけ段にする）。
_CORPUS = [
    # 中央が大きい総称の段（頭は `年金` の 2字）
    *[{"id": f"a{i}", "q": "年金 手取り いくら", "views": 600_000} for i in range(5)],
    # 中央が小さい specific な段（頭は `遺族年金` の 4字）
    *[{"id": f"b{i}", "q": "遺族年金 いくら 計算", "views": 50_000} for i in range(5)],
    # 頭が specific で、`いくら` しか持たない段（`hits` が 1 になりやすい側）
    *[{"id": f"c{i}", "q": "加給年金 いくら", "views": 70_000} for i in range(5)],
]


def _corpus(tmp_path):
    p = tmp_path / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in _CORPUS), encoding="utf-8")
    return p


def _ledger(tmp_path, rows):
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return p


def _scripts(tmp_path, books):
    d = tmp_path / "scripts"
    d.mkdir()
    for sid, body in books.items():
        json.dump(body, open(d / f"{sid}.json", "w"), ensure_ascii=False)
    return d


def _sched(vid, sid, title, publish_at):
    return {"event": "scheduled", "video_id": vid, "id": sid,
            "title": title, "publish_at": publish_at}


def test_頭の錨は長いほうが勝つ(tmp_path):
    """`遺族厚生年金` の本が、中央の大きい `年金 手取り いくら` に化けないこと。

    どちらも `hits` は 2（`年金`＋`いくら` ／ `遺族年金`＋`いくら`）＝ **hits では割れません**。
    """
    c = _corpus(tmp_path)
    text = "夫が亡くなると妻の年金はいくら減るか 遺族厚生年金は4分の3 #Shorts 年金 遺族年金 厚生年金"
    t = topics.tier_of(text, c)
    assert t is not None
    assert t["q"] == "遺族年金 いくら 計算", t
    assert t["head"] == "遺族年金"


def test_形を混ぜない(tmp_path):
    """長尺を入れると、ショート 970回 の族が中央 8回 に化ける（この周に踏んだ実物の形）。"""
    c = _corpus(tmp_path)
    old = "2026-09-09T10:00+09:00"
    rows = [
        _sched("v-short", "s-short", "配偶者が年下だと年金が年42万3700円ふえる 加給年金 #Shorts", old),
        {"video_id": "v-short", "views": 970},
        _sched("v-long", "s-long", "年金を70歳まで遅らせた人が失うお金3つ 加給年金 いくら", old),
        {"video_id": "v-long", "views": 13},
    ]
    led = _ledger(tmp_path, rows)
    sc = _scripts(tmp_path, {
        "s-short": {"tags": ["加給年金"], "form": "short"},
        "s-long": {"tags": ["加給年金"], "form": "long"},
    })
    short = topics.mine_by_query(c, led, sc, form="short")
    assert short["加給年金 いくら"] == {"n": 1, "median": 970, "max": 970}, short
    mixed = topics.mine_by_query(c, led, sc, form=None)
    assert mixed["加給年金 いくら"]["median"] < 970, mixed
    assert mixed["加給年金 いくら"]["n"] == 2


def test_form_が無い古い本は題の_Shorts_で見る(tmp_path):
    """2026-09-10 までの台本は `form` を持ちません（実測）。題の `#Shorts` が代わりです。"""
    sc = _scripts(tmp_path, {"old": {"tags": []}})
    assert topics._form_of({"id": "old", "title": "…加給年金 #Shorts"}, sc) == "short"
    assert topics._form_of({"id": "old", "title": "…加給年金の話"}, sc) == "long"


def test_出たばかりの本は数えない(tmp_path):
    """予約ずみ・公開直後の 0回 を入れると、族の中央が 0回 に化ける（この周に踏んだ実物の形）。"""
    c = _corpus(tmp_path)
    rows = [
        _sched("v-old", "s-old", "退職金の税金 加給年金 いくら #Shorts", "2026-09-10T10:00+09:00"),
        {"video_id": "v-old", "views": 879},
        # きょう出したばかり（齢 0時間）＝ まだ 0回
        _sched("v-new", "s-new", "加給年金 いくら 別の本 #Shorts", "2026-09-19T21:00+09:00"),
        {"video_id": "v-new", "views": 0},
    ]
    led = _ledger(tmp_path, rows)
    sc = _scripts(tmp_path, {"s-old": {"tags": [], "form": "short"},
                             "s-new": {"tags": [], "form": "short"}})
    got = topics.mine_by_query(c, led, sc)
    assert got["加給年金 いくら"] == {"n": 1, "median": 879, "max": 879}, got


def test_置き直した本の0回を採らない(tmp_path):
    """1つ の台本が 2つ 以上の `video_id` を持つことが在ります（`schedule --replace`）。"""
    c = _corpus(tmp_path)
    old = "2026-09-10T10:00+09:00"
    rows = [
        _sched("v-dead", "s1", "加給年金 いくら #Shorts", old),
        _sched("v-live", "s1", "加給年金 いくら #Shorts", old),
        {"video_id": "v-dead", "views": 0},
        {"video_id": "v-live", "views": 1220},
    ]
    led = _ledger(tmp_path, rows)
    sc = _scripts(tmp_path, {"s1": {"tags": [], "form": "short"}})
    got = topics.mine_by_query(c, led, sc)
    assert got["加給年金 いくら"] == {"n": 1, "median": 1220, "max": 1220}, got


def test_line_は_corpus_だけで族を選べとは言わない(tmp_path):
    """`line()` の締めが「ここの上から採ること」に戻っていないこと（この周に直した所）。"""
    c = _corpus(tmp_path)
    s = topics.line(c)
    assert "corpus（よその本の検索の上位）で、うちの配りではありません" in s
    assert "次の台本の題材は、ここの上から採ること" not in s
