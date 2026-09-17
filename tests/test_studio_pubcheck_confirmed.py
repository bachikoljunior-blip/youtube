"""**`videos.list part=status` が public と言った本は、二度と「出ていない」と鳴らさない。**

（2026-09-17 16:1x・optimizer・Fable 5.1・ultracode）

## 踏んだ当のもの

`FLLHpj27v7s`（刻を 41.8時間 超過）と `4MpH3QliNi4`（26.8時間 超過）は、
**oEmbed では 401** が返り、`pubcheck.missing()` が **2日 のあいだ**
「本 1本 と 枠 1つ が黙って消えています」と鳴らし続けていました。

**日枠が戻った窓で `videos.list part=status` を撃ったら、2本 とも
`privacy: public`・`publishAt: None`** ＝ **刻は消えておらず、本は出ていました。**
＝ **oEmbed は public を public と言わないことが在ります。1単位 の口のほうが本当。**

## この検査が固定するもの

    1. `ready_checked` が `privacy: public` と言った本は `missing()` に出ない
    2. **その後 private に戻された本は、覚えを捨てる**（陽性対照）
    3. `privacy` を持たない古い行は、覚えに数えない（陽性対照）
    4. 覚えを外せば同じ本が鳴る（＝ 覚えが効いていることの陽性対照）

**覆る条件**: oEmbed の側が直ったら、この覚えは要りません（`confirmed_public` の註）。
"""
from __future__ import annotations

import datetime as dt

import studio.pubcheck as pc

JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 17, 16, 0, tzinfo=JST)
PAST = (NOW - dt.timedelta(hours=40)).isoformat()


def _rows(extra=None):
    rows = [{"event": "scheduled", "id": "s1", "video_id": "V1", "publish_at": PAST,
             "title": "t", "at": PAST}]
    return rows + (extra or [])


def test_publicと言われた本は鳴らない():
    rows = _rows([{"event": "ready_checked", "id": "V1", "privacy": "public", "at": PAST}])
    assert pc.confirmed_public(rows) == {"V1"}
    assert [m["video_id"] for m in pc.missing(rows, NOW, probe_fn=lambda v: 401)] == []


def test_覚えが無ければ鳴る():
    """**陽性対照 1**: 覚えを外すと、同じ本が鳴ること（覚えが効いている）。"""
    rows = _rows()
    assert [m["video_id"] for m in pc.missing(rows, NOW, probe_fn=lambda v: 401)] == ["V1"]


def test_privateに戻されたら覚えを捨てる():
    """**陽性対照 2**: `unscheduled` が後に在れば、public の覚えは効かないこと。"""
    rows = _rows([{"event": "ready_checked", "id": "V1", "privacy": "public", "at": PAST},
                  {"event": "unscheduled", "id": "V1", "at": PAST}])
    assert pc.confirmed_public(rows) == set()
    # **`missing()` までは見ません** —— `unscheduled` は `live_schedule` から刻ごと落とすので、
    # そちらでも鳴りません（この検査が固定するのは「覚えを捨てる」ことだけ）。


def test_privacyを持たない古い行は数えない():
    """**陽性対照 3**: この回より前の `ready_checked` は `privacy` を持ちません。"""
    rows = _rows([{"event": "ready_checked", "id": "V1", "ok": True, "at": PAST}])
    assert pc.confirmed_public(rows) == set()
