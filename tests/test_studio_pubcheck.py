"""`studio/pubcheck.py` —— **刻が過ぎたのに public でない本**を API 0単位 で見つける口。

2026-09-16 23:3x に踏んだ形（`FLLHpj27v7s` 26.6時間・`4MpH3QliNi4` 11.6時間）を、
台帳の形のまま盤に置いてある。**陽性対照**は「鳴るはずの物を鳴らす」側と
「鳴ってはいけない物で鳴らない」側の両方（`test_陽性対照_*`）。
"""
from __future__ import annotations

import datetime as dt

import pytest

from studio import pubcheck
from studio.common import JST

NOW = dt.datetime(2026, 9, 16, 23, 30, tzinfo=JST)


def row(event, vid, **kw):
    return {"event": event, "id": kw.pop("script", "s"), "at": "2026-09-15T14:27:20+09:00", **kw,
            **({"video_id": vid} if vid else {})}


def sched(vid, at, script="s", replaced=None, moved_from=None, title="題"):
    return {"event": "scheduled", "id": script, "at": "2026-09-15T14:27:20+09:00",
            "video_id": vid, "publish_at": at, "replaced": replaced,
            **({"moved_from": moved_from} if moved_from else {}), "title": title}


# 09/15〜09/16 の実測の形（出た 5本・出ていない 2本・まだ刻の前 3本）
ROWS = [
    sched("Ws32ZrBAuFQ", "2026-09-15T10:00+09:00", "iryohi"),
    sched("PyVf22V74Ks", "2026-09-15T19:00+09:00", "kurisage"),
    sched("_BzD21AUZqw", "2026-09-18T19:00+09:00", "minou"),
    sched("FLLHpj27v7s", "2026-09-18T19:00+09:00", "minou", replaced="_BzD21AUZqw"),
    sched("FLLHpj27v7s", "2026-09-15T21:00+09:00", "minou", moved_from="2026-09-18T19:00+09:00"),
    sched("4MpH3QliNi4", "2026-09-16T12:00+09:00", "tedori", moved_from="2026-09-19T19:00+09:00"),
    sched("vum9GV8Sp6c", "2026-09-16T10:00+09:00", "ninni"),
    sched("uc0SceBfoxQ", "2026-09-16T19:00+09:00", "kuriage"),
    sched("BzWoZR1Y4ZI", "2026-09-16T21:00+09:00", "hokenryo"),
    sched("xyMsBJxaj4M", "2026-09-17T19:00+09:00", "gake"),
]
CODES = {"Ws32ZrBAuFQ": 200, "PyVf22V74Ks": 200, "vum9GV8Sp6c": 200, "uc0SceBfoxQ": 200,
         "BzWoZR1Y4ZI": 200, "FLLHpj27v7s": 401, "4MpH3QliNi4": 401, "xyMsBJxaj4M": 403,
         "_BzD21AUZqw": 401}


def fake(vid):
    return CODES[vid]


def test_上げ直された前の版は名簿から落ちる():
    """`replaced` に名が出た video は「予約」ではない（落とさないと 401 で誤って鳴る）。"""
    assert "_BzD21AUZqw" not in pubcheck.live_schedule(ROWS)


def test_刻だけ動かした本は最後の刻が勝つ():
    _, at, _ = pubcheck.live_schedule(ROWS)["FLLHpj27v7s"]
    assert at == dt.datetime(2026, 9, 15, 21, 0, tzinfo=JST)


def test_出ていない2本を名指しする():
    bad = pubcheck.missing(ROWS, NOW, probe_fn=fake)
    assert [b["video_id"] for b in bad] == ["FLLHpj27v7s", "4MpH3QliNi4"]
    assert bad[0]["late_h"] == pytest.approx(26.5, abs=0.1)
    assert bad[1]["late_h"] == pytest.approx(11.5, abs=0.1)


def test_まだ刻の前の本は鳴らさない():
    """`xyMsBJxaj4M`（09/17 19:00・403）は刻の前 ＝ 名簿にも上がらない。"""
    assert "xyMsBJxaj4M" not in [v for v, *_ in pubcheck.overdue(ROWS, NOW)]
    assert "xyMsBJxaj4M" not in [b["video_id"] for b in pubcheck.missing(ROWS, NOW, probe_fn=fake)]


def test_出た本は鳴らさない():
    out = {b["video_id"] for b in pubcheck.missing(ROWS, NOW, probe_fn=fake)}
    assert out.isdisjoint({"Ws32ZrBAuFQ", "PyVf22V74Ks", "vum9GV8Sp6c", "uc0SceBfoxQ", "BzWoZR1Y4ZI"})


def test_届かない周は鳴らさない():
    """網が落ちて 0 が返る周に毎回 鳴るのは誤報の側（`probe` の註）。"""
    assert pubcheck.missing(ROWS, NOW, probe_fn=lambda v: 0) == []


def test_猶予の中は鳴らさない():
    """刻ちょうどでは鳴らない（YouTube の予約は刻ちょうどに出ない）。"""
    just = dt.datetime(2026, 9, 16, 12, 10, tzinfo=JST)   # 09/16 12:00 の 10分 後・猶予 25分 の中
    assert "4MpH3QliNi4" not in [b["video_id"] for b in pubcheck.missing(ROWS, just, probe_fn=fake)]


def test_privateへ戻した本は名簿から落ちる():
    rows = ROWS + [{"event": "unscheduled", "id": "minou", "at": "2026-09-16T00:00+09:00",
                    "video_id": "FLLHpj27v7s"}]
    assert "FLLHpj27v7s" not in pubcheck.live_schedule(rows)


def test_行は本と枠の値段を言う():
    s = pubcheck.line(ROWS, NOW, probe_fn=fake)
    assert s.startswith("!!")
    assert "FLLHpj27v7s" in s and "4MpH3QliNi4" in s
    assert "1,650単位" in s          # 見落とした 1本 の値段が行に在ること
    assert "reschedule" in s         # 潰し方が行に在ること


def test_座っている刻は台帳から作る():
    """**API 0単位** —— 鳴っている周は日枠が尽きていることが多く、`yt.all_videos()` が引けない。"""
    taken = pubcheck.taken_slots(ROWS, NOW)
    assert dt.datetime(2026, 9, 17, 19, 0, tzinfo=JST) in taken     # まだ刻の前の予約は座っている
    assert dt.datetime(2026, 9, 16, 21, 0, tzinfo=JST) in taken     # **出た本も座っている**（下の註）
    # 1日 より前の刻は落とす（`next_long_slots` は先しか見ないので、持っていても使わない）
    assert dt.datetime(2026, 9, 15, 10, 0, tzinfo=JST) not in taken
    # 上げ直された前の版（`replaced`）は座らない
    assert dt.datetime(2026, 9, 18, 19, 0, tzinfo=JST) not in taken


def test_題を直した本は新しい題で名指しする():
    """`retitled` の `id` は **video_id**（`scheduled` の `id` は台本 id）。混ぜると誰も名指しできない。"""
    rows = ROWS + [{"event": "retitled", "id": "4MpH3QliNi4", "at": "2026-09-16T01:00+09:00",
                    "old_title": "題", "new_title": "【年金15万円】手取りは13万7000円"}]
    assert pubcheck.live_schedule(rows)["4MpH3QliNi4"][2] == "【年金15万円】手取りは13万7000円"
    # 直していない本は、そのまま
    assert pubcheck.live_schedule(rows)["FLLHpj27v7s"][2] == "題"


def test_出た本の刻を空き枠に数えない():
    """**撃って落とした形**（2026-09-16 23:5x）: 「刻を過ぎた」だけで外すと、

    `BzWoZR1Y4ZI`（09/16 21:00 に**刻どおり出た**）まで空き枠に数えてしまう。
    出ていない本の刻を外しても得は 0（`LONG_SLOT_LEAD_H` より先しか候補にならない）。
    """
    assert dt.datetime(2026, 9, 16, 21, 0, tzinfo=JST) in pubcheck.taken_slots(ROWS, NOW)


def test_行は打ち直す先の枠を言う():
    """「どこへ」まで書いていないと、次の回がもう一度 数え直す。"""
    slots = [dt.datetime(2026, 9, 18, 12, 0, tzinfo=JST), dt.datetime(2026, 9, 18, 19, 0, tzinfo=JST),
             dt.datetime(2026, 9, 18, 21, 0, tzinfo=JST)]
    s = pubcheck.line(ROWS, NOW, probe_fn=fake, slots=slots)
    assert "空いている枠: 09/18 12:00 / 09/18 19:00 / 09/18 21:00" in s


def test_鳴っていない周は1行でおわる():
    s = pubcheck.line(ROWS, NOW, probe_fn=lambda v: 200)
    assert "\n" not in s and "全部 public" in s


def test_陽性対照_出た本を401にすると鳴る():
    """**鳴るはずの物**: 出ている本の番号を 401 に振ると、その本が名指しされる。"""
    codes = dict(CODES, vum9GV8Sp6c=401)
    bad = [b["video_id"] for b in pubcheck.missing(ROWS, NOW, probe_fn=codes.__getitem__)]
    assert "vum9GV8Sp6c" in bad


def test_陽性対照_番号ではなく刻で決めている():
    """**判定は 401/403 の読み分けに依っていない**（`pubcheck` の覆る条件 (2)）。

    出ていない 2本 の番号を 403（「まだ刻の前」の見立て）に振っても、**刻は過ぎているので鳴る**。
    """
    codes = dict(CODES, FLLHpj27v7s=403, **{"4MpH3QliNi4": 403})
    bad = [b["video_id"] for b in pubcheck.missing(ROWS, NOW, probe_fn=codes.__getitem__)]
    assert bad == ["FLLHpj27v7s", "4MpH3QliNi4"]
