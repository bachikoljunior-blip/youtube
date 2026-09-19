# -*- coding: utf-8 -*-
"""**ASP の画面を台帳へ写し、押される率を帯と突き合わせる口**（`cli asp-report`・`trend.asp_report`）の検査
（2026-09-19 11:xx・optimizer・Fable 5.1・ultracode）。

**なぜ在るか**: 「押されたか」を知る口は ASP の画面 1つ だけで、09/19 10:51 の 1枚（クリック 11件）は受け取り帳にしか
無く、`trend` が読める形ではどこにも無かった。この検査が守るのは 4つ:
  (1) 行が無いのと 0件 の行は別の字で出ること（`None` を 0 と読まない）
  (2) 分母が無ければ率を出さないこと（件数だけ）
  (3) 中の率が `PERF_CLICK_BAND` の外なら「引き直せ」と印字すること（覆る条件 (1)）
  (4) 成果の側はクリック 40件 未満では読まないこと（0件 を「出ない」と読まない）
"""
from __future__ import annotations

from studio import trend


def _rep(**kw) -> dict:
    row = {"event": "asp_report", "id": "-", "at": "2026-09-19T11:05:09+09:00",
           "clicks": 11, "actions": 0, "approved": 0, "since": "2026-09-01", "until": "2026-09-19"}
    row.update(kw)
    return row


def test_行が無いのと0件は別():
    assert trend.asp_report([]) is None
    assert "まだ 1枚 も台帳に無い" in trend.asp_report_line([])
    assert trend.asp_report_short([]) == ""
    d = trend.asp_report([_rep(clicks=0)])
    assert d is not None and d["clicks"] == 0


def test_分母が無ければ率を出さない():
    d = trend.asp_report([_rep()])
    assert d["click_rate"] is None and d["in_band"] is None
    line = trend.asp_report_line([_rep()])
    assert "分母" in line and "率は出しません" in line
    assert "%" not in line.split("分母")[0].split("クリック")[1]


def test_帯の内と外():
    inside = _rep(views=2100, views_low=4919, views_high=1400, review="審査中")
    d = trend.asp_report([inside])
    assert abs(d["click_rate"] - 11 / 2100) < 1e-9
    assert d["click_low"] < d["click_rate"] < d["click_high"]
    assert d["in_band"] is True
    line = trend.asp_report_line([inside])
    assert "帯の内" in line and "審査中" in line and "否認" in line
    assert "0.52%" in line
    # 帯の外（率が 10倍 大きい）→ 引き直せ
    outside = _rep(clicks=110, views=2100)
    assert trend.asp_report([outside])["in_band"] is False
    assert "引き直す" in trend.asp_report_line([outside])
    assert "引き直し" in trend.asp_report_short([outside])


def test_成果の側は40件まで読まない():
    few = _rep(clicks=11, actions=0, views=2100)
    d = trend.asp_report([few])
    assert d["convert_rate"] is None
    assert "まだ読めない" in trend.asp_report_line([few])
    many = _rep(clicks=50, actions=0, views=10000)
    d = trend.asp_report([many])
    assert d["convert_rate"] == 0.0
    assert "案件を疑う" in trend.asp_report_line([many])
    hit = _rep(clicks=50, actions=4, views=10000)
    assert abs(trend.asp_report([hit])["convert_rate"] - 0.08) < 1e-9


def test_いちばん新しい行を読む():
    rows = [_rep(clicks=3, at="2026-09-19T09:00:00+09:00"), _rep(clicks=11, at="2026-09-19T11:05:09+09:00")]
    assert trend.asp_report(rows)["clicks"] == 11


def test_statusの短い形に画面が付く():
    text = trend.perf_short(trend.ledger_rows())
    assert "ASP の画面（最新）" in text or "押す側は実測" in text
