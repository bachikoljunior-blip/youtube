# -*- coding: utf-8 -*-
"""**再生の数を日枠 0 の周でも読む口**（`pubcheck.shorts_views`・`cli.measure_public`）の検査
（2026-09-19 11:xx・optimizer・Fable 5.1・ultracode）。

**なぜ在るか**: 09/19 01:37 〜 16:00 の 14時間、日枠 403 で台帳に再生の行が入らず、その窓が ASP の 1枚
（クリック 11件）の**分母**の当の窓でした。公開ページの「ショート」の面は `accessibilityText` に
「<題>, <N>回視聴 - ショート動画を再生」を持ち、Data API 0単位 で本ごとの再生が読めます。

**陽性対照を先に置く**（`test_pubcheck_channel_public.py` と同じ形）:
    (1) 実物の写し（2026-09-19 10:5x に撃って取った字）から **8本** の再生が出ること（`0 回視聴` は 0、`1,046回視聴` は 1046）
    (2) 字を崩すと **`None`**（0本 ではない）
    (3) `measure_public` は **刻が台帳に在る本だけ**を行にし、likes は持ち回って `likes_carried` を立てること（0 と書かない）
"""
from __future__ import annotations

import datetime as dt

from studio import cli, pubcheck
from studio.common import JST

# 実物の写し（2026-09-19 10:5x・`https://www.youtube.com/channel/UChTXZzwkIJHqyL7L_fEtuqQ/shorts`）の骨だけ。
_ITEM = ('{"richItemRenderer":{"content":{"shortsLockupViewModel":{"entityId":"shorts-shelf-item-%s",'
         '"accessibilityText":"%s, %s回視聴 - ショート動画を再生","onTap":{}}}}}')
REAL_ITEMS = [
    ("oNiKmRKi4N4", "退職金2000万円 30年勤めた人の手取りは1959万4300円 税金は40万5700円 #Shorts", "0 "),
    ("o_c9fMHlIq4", "退職金1500万円 30年勤めた人の手取りは1500万円 税金は0円で1円も引かれない #Shorts", "709"),
    ("ktbvrdAeavA", "年金が毎月20万円の人の手取りは17万4000円 毎月2万6000円引かれて所得税もつく #Shorts", "1,046"),
    ("49Wa5jNNzOk", "年金が毎月18万円の人の手取りは16万円 所得税は0円なのに毎月2万円引かれる #Shorts", "802"),
    ("qqlUo148_cg", "年金が毎月12万円の人の手取りは11万5000円 税金は0円なのに毎月4600円引かれる #Shorts", "847"),
    ("2u22TXSLyno", "年金が毎月15万円の人の手取りは13万7000円 所得税は0円なのに毎月1万2800円引かれる #Shorts", "1,076"),
    ("tQPfODv61vg", "年金が毎月10万円の人の手取りは9万7000円 税金は0円なのに毎月3300円引かれる #Shorts", "1,165"),
    ("vum9GV8Sp6c", "国民年金が5年足りないと年金は一生 毎年10万5900円少ない #Shorts", "1,220"),
]
REAL = '{"contents":[' + ",".join(_ITEM % it for it in REAL_ITEMS) + "]}"


def test_陽性対照_実物の写しから8本の再生が出る():
    d = pubcheck.shorts_views("UCxxx", fetch=lambda url: REAL)
    assert d is not None and len(d) == 8
    assert d["oNiKmRKi4N4"]["views"] == 0            # 「0 回視聴」は 0（欄が在る 0）
    assert d["ktbvrdAeavA"]["views"] == 1046         # カンマ区切り
    assert d["tQPfODv61vg"]["views"] == 1165
    assert d["o_c9fMHlIq4"]["title"].startswith("退職金1500万円")
    assert "回視聴" not in d["o_c9fMHlIq4"]["title"]


def test_万の単位も解く():
    html = _ITEM % ("AAAAAAAAAAA", "題", "1.2万")
    d = pubcheck.shorts_views("UCxxx", fetch=lambda url: html)
    assert d == {"AAAAAAAAAAA": {"views": 12000, "title": "題"}}


def test_字が崩れたら_0本ではなくNone():
    broken = REAL.replace("回視聴", "回みた")
    assert pubcheck.shorts_views("UCxxx", fetch=lambda url: broken) is None
    assert pubcheck.shorts_views("UCxxx", fetch=lambda url: (_ for _ in ()).throw(OSError())) is None


def test_measure_public_は刻が台帳に在る本だけ_likesは持ち回る():
    now = dt.datetime(2026, 9, 19, 11, 0, tzinfo=JST)
    rows = [
        {"event": "scheduled", "video_id": "o_c9fMHlIq4", "publish_at": "2026-09-19T07:00+09:00", "id": "x"},
        {"event": "scheduled", "video_id": "ktbvrdAeavA", "publish_at": "2026-09-18T18:00+09:00", "id": "y"},
        {"event": "measured", "id": "ktbvrdAeavA", "views": 862, "likes": 3, "comments": 3,
         "age_h": 7.6, "at": "2026-09-19T01:37:00+09:00"},
        # 刻は measured の at - age_h からも戻せる（scheduled 行が無い本）
        {"event": "measured", "id": "vum9GV8Sp6c", "views": 1191, "likes": 5, "comments": 0,
         "age_h": 30.0, "at": "2026-09-17T16:00:00+09:00"},
    ]
    page = pubcheck.shorts_views("UCxxx", fetch=lambda url: REAL)
    made = {r["id"]: r for r in cli.measure_public(rows, page, now=now)}
    # 刻の分からない本（tQPfODv61vg など）は書かない
    assert set(made) == {"o_c9fMHlIq4", "ktbvrdAeavA", "vum9GV8Sp6c"}
    a = made["o_c9fMHlIq4"]
    assert a["views"] == 709 and a["age_h"] == 4.0 and a["src"] == "public_page"
    assert a["likes_absent"] is True and a["likes"] == 0 and "n_values" not in a
    b = made["ktbvrdAeavA"]
    assert b["views"] == 1046 and b["likes"] == 3 and b["comments"] == 3 and b["likes_carried"] is True
    assert b["age_h"] == 17.0
    c = made["vum9GV8Sp6c"]
    assert c["age_h"] == 73.0 and c["views"] == 1220


def test_measure_public_は7日を越えた本を書かない():
    now = dt.datetime(2026, 9, 30, 11, 0, tzinfo=JST)
    rows = [{"event": "scheduled", "video_id": "o_c9fMHlIq4", "publish_at": "2026-09-19T07:00+09:00", "id": "x"}]
    page = pubcheck.shorts_views("UCxxx", fetch=lambda url: REAL)
    assert cli.measure_public(rows, page, now=now) == []
    assert cli.measure_public(rows, None, now=now) == []
