# -*- coding: utf-8 -*-
"""`hear.near_quiet` —— `[!]`（`near_repeats` の名指し）の**反証**を数える所。

規則と覆る条件は `studio/hear.near_quiet` の註。

**陽性対照**（壊すと、どれが落ちるか）:
  - `near_quiet` の `if exp_char not in (r.get("exp") or ""): continue` を外すと
    `test_その字を持たないコマは数えない` が落ちる
  - `if any(p[0] == exp_char ...)` の枝を外すと `test_崩れたコマは反証に数えない` が落ちる
  - 空文字の早戻りを外すと `test_差し込み型は測れない` が落ちる

実物（2026-09-12 01:4x・09/13 の本 `2026-09-13-fuka-nenkin-400en`）:
  `('わ','あ')` が コマ3・5 で名指しされ、同じ「上乗せ」を持つ コマ4・13 は崩れていない
  ＝ 4回 中 2回 だけ ＝ 「同じ語が出るたびに同じだけ崩れる」の反証。
"""
import pytest

from studio.hear import near_quiet, near_repeats

pytestmark = pytest.mark.live


def _rows():
    """09/13 の本の形（「うわのせ」が 4コマ・崩れたのは 2コマ）。"""
    return [
        {"i": 3, "exp": "かいしゃではたらくひとにはうわのせがあります", "near": [("わ", "あ")]},
        {"i": 4, "exp": "こくみんねんきんだけのひとにはうわのせがあります", "near": []},
        {"i": 5, "exp": "きまりではそのうわのせがふかねんきんです", "near": [("わ", "あ")]},
        {"i": 13, "exp": "もうひとつのうわのせのこくみんねんきんききん", "near": [("お", "う")]},
        {"i": 9, "exp": "けいさんすると200えんかける120かげつです", "near": []},
    ]


def test_名指しはそのまま出る():
    assert near_repeats(_rows()) == [(("わ", "あ"), [3, 5])]


def test_崩れなかったコマが反証として出る():
    assert near_quiet(_rows(), "わ") == [4, 13]


def test_崩れたコマは反証に数えない():
    q = near_quiet(_rows(), "わ")
    assert 3 not in q and 5 not in q


def test_その字を持たないコマは数えない():
    # コマ9 の予定に「わ」は無い
    assert 9 not in near_quiet(_rows(), "わ")


def test_反証が無い本は空を返す():
    rows = [
        {"i": 1, "exp": "つまのきそねんきん", "near": [("つ", "す")]},
        {"i": 2, "exp": "つまのぶんはでません", "near": [("つ", "す")]},
        {"i": 3, "exp": "こうせいねんきんのはなし", "near": []},
    ]
    assert near_repeats(rows) == [(("つ", "す"), [1, 2])]
    assert near_quiet(rows, "つ") == []


def test_差し込み型は測れない():
    # **3つ目のコマ（崩れていない）を入れてあります** —— 入れないと、早戻りを外しても
    # 「どの予定にも空文字は含まれる → でも全コマが空文字の組を持つ」で同じ [] が返り、
    # 陽性対照が落ちません（§5 教訓の形 3つ目・2026-09-12 01:5x に撃って直した）
    rows = [
        {"i": 1, "exp": "こうせいねんきん", "near": [("", "い")]},
        {"i": 2, "exp": "こうせいねんきんのぶん", "near": [("", "い")]},
        {"i": 3, "exp": "きそねんきんのはなし", "near": []},
    ]
    assert near_quiet(rows, "") == []


def test_near_の無い行でも落ちない():
    rows = [{"i": 1, "exp": "うわのせ"}, {"i": 2, "exp": "うわのせ", "near": None}]
    assert near_quiet(rows, "わ") == [1, 2]


def test_exp_の無い行でも落ちない():
    assert near_quiet([{"i": 1}, {"i": 2, "exp": None}], "わ") == []
