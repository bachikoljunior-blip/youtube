"""**題の特徴を数える所を1か所にする**（2026-09-05 に足した）。

この帯で題の特徴を数えた回が少なくとも3回 在り、**3回とも その場で正規表現と窓を
書き直して、出た数が食い違いました**（×0.09 ／ ×0.73 ／ ×0.38）。
`niche_ceiling.title_features()` が正本です。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import niche_ceiling as nc  # noqa: E402

NOW = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)


def _corpus(tmp_path, rows):
    p = tmp_path / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _row(vid, title, views, *, form="short", days=100, at="2026-09-01T00:00:00Z"):
    pub = (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    return {"at": at, "id": vid, "views": views, "secs": 40, "form": form,
            "channel": "c" + vid, "title": title, "published": pub, "q": "q"}


def test_ratio_is_per_day_not_lifetime(tmp_path):
    """**古い本ほど累計は大きい。** 齢で割らないと「古い本が勝つだけの表」になります。"""
    rows = [
        # 疑問形 有: 新しくて累計は小さいが、1日あたりは大きい
        _row("a", "いくら戻る？", 1000, days=10),
        _row("b", "いくら減る？", 1000, days=10),
        # 疑問形 無: 古くて累計は大きいが、1日あたりは小さい
        _row("c", "戻る額の話", 2000, days=1000),
        _row("d", "減る額の話", 2000, days=1000),
    ]
    p = _corpus(tmp_path, rows)
    got = {d["name"]: d for d in nc.title_features("short", path=p, now=NOW)}
    q = got["疑問形"]
    assert q["n_yes"] == 2 and q["n_no"] == 2
    assert q["med_yes"] == 100.0 and q["med_no"] == 2.0   # 1000/10 と 2000/1000
    assert q["ratio"] == 50.0                              # 累計で見れば ×0.5 の側
    assert q["thin"] is True                               # 升が薄い → 印が付く


def test_duplicate_ids_are_counted_once(tmp_path):
    """**同じ本が何度も帯に入ります**（語ごとに撃つので）。数え直すと倍率が膨らみます ——
    2026-09-05 の回が、重なりを潰さずに ショートの「？」を ×8.06 と読みました
    （潰すと ×2.39）。`corpus_rows()` は `id` ごとに新しい `at` の1行だけ残します。"""
    rows = [
        _row("a", "いくら戻る？", 1000, days=10, at="2026-09-01T00:00:00Z"),
        _row("a", "いくら戻る？", 1000, days=10, at="2026-09-02T00:00:00Z"),  # 同じ本
        _row("a", "いくら戻る？", 1000, days=10, at="2026-09-03T00:00:00Z"),  # 同じ本
        _row("c", "戻る額の話", 10, days=10),
    ]
    p = _corpus(tmp_path, rows)
    got = {d["name"]: d for d in nc.title_features("short", path=p, now=NOW)}
    assert got["疑問形"]["n_yes"] == 1, "同じ id は1本として数えること"
    assert got["疑問形"]["n_no"] == 1


def test_layer_drops_the_layer_feature_itself(tmp_path):
    rows = [_row("a", "【年金】いくら戻る？", 100), _row("b", "【年金】戻る額", 100),
            _row("c", "いくら戻る？", 100), _row("d", "戻る額", 100)]
    p = _corpus(tmp_path, rows)
    names = {d["name"] for d in nc.title_features("short", path=p, now=NOW, layer="【】")}
    assert "【】" not in names          # 層そのものは並べない
    got = {d["name"]: d for d in nc.title_features("short", path=p, now=NOW, layer="【】")}
    assert got["疑問形"]["n_yes"] == 1 and got["疑問形"]["n_no"] == 1  # 【】の2本だけ


def test_form_is_respected(tmp_path):
    rows = [_row("a", "いくら？", 100, form="short"),
            _row("b", "いくら？", 100, form="long")]
    p = _corpus(tmp_path, rows)
    s = {d["name"]: d for d in nc.title_features("short", path=p, now=NOW)}
    L = {d["name"]: d for d in nc.title_features("long", path=p, now=NOW)}
    assert s["疑問形"]["n_yes"] == 1 and s["疑問形"]["n_no"] == 0
    assert L["疑問形"]["n_yes"] == 1 and L["疑問形"]["n_no"] == 0


def test_lines_say_the_sign_can_flip_by_form(tmp_path):
    p = _corpus(tmp_path, [_row("a", "いくら？", 100), _row("b", "額の話", 100)])
    lines = nc.title_feature_lines("short", path=p, now=NOW)
    joined = "\n".join(lines)
    assert "1日あたり" in joined
    assert "符号が逆" in joined, "形をまたいで写すな、を毎回 印字すること"
    assert "薄い升" in joined


def test_thin_flag_uses_the_constant(tmp_path):
    rows = [_row(f"y{i}", "いくら？", 100) for i in range(nc.THIN_CELL)]
    rows += [_row(f"n{i}", "額の話", 100) for i in range(nc.THIN_CELL)]
    p = _corpus(tmp_path, rows)
    got = {d["name"]: d for d in nc.title_features("short", path=p, now=NOW)}
    assert got["疑問形"]["thin"] is False
    rows = rows[:-1]
    p2 = _corpus(tmp_path / "x" if False else tmp_path, rows)
    got = {d["name"]: d for d in nc.title_features("short", path=p2, now=NOW)}
    assert got["疑問形"]["thin"] is True
