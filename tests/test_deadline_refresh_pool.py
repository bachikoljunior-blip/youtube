"""**「取り直せ」と言うなら、それがいま撃てるかも言うこと**（2026-08-28・最適化の回）。

`scripts/deadline_check.py` は、同じ出力の中に2種類の行を並べます。

    08-28  「取り直す `python scripts/snapshot.py` は **Data API の日枠**を使い、
            **この窓ではもう尽きています**（403 を 364回 観測）」
    08-31  「取り直すまで、待っても増えません。 `python -m src.rpm_mix --forms`」

**後者には枠の話が1文字もありません。** 直前に「尽きています」を読んだ回は、
**後者も尽きていると読みます。** 2026-08-28 の前の回がそう読んで、この1件を
丸ごと飛ばしました —— **実際は Analytics だけを引くので、そのまま通ります**
（`src.rpm_mix.fetch_video_forms` の註「**Data API は0単位です**」）。
この回が撃って通り、判定日は **09-03 → 08-30** へ 3日 手前に来ました。

`_quota_gate` は、**どの道具が日枠を使うかを正確に知っています**
（`src.upload_cap.DATA_API_TOOLS`）。知っているのに、`_stale_todo` が
それを読んでいませんでした。**この検査は、下流が上流を読む状態を留めます。**

**外したら落ちる向き**: 「いま撃てます」を消す（＝前の回と同じ読み違いに戻る）か、
日枠を使う道具にまで「いま撃てます」と言う（＝403 を買いに行かせる）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as J  # noqa: E402
from src import upload_cap  # noqa: E402


def _dq(*, is_open: bool, hits: int = 364):
    back = datetime.now(timezone.utc) + timedelta(hours=1)
    return upload_cap.DayQuota(open=is_open, observed=not is_open, hits=hits,
                               resets_at=back, line="(検査)")


def _patch(monkeypatch, *, is_open: bool):
    monkeypatch.setattr(upload_cap, "day_quota",
                        lambda *a, **k: _dq(is_open=is_open), raising=False)


def test_日枠を使わない手にはいま撃てますと言う(monkeypatch):
    """**この検査が守っている、そのものです。**"""
    _patch(monkeypatch, is_open=False)
    note = J._refresh_pool_note({"refresh": "python -m src.rpm_mix --forms"})
    assert "いま撃てます" in note, "**日枠と無関係な手が、尽きている側に読まれます**"
    assert "別の枠" in note


def test_日枠を使う手には撃てないと言う(monkeypatch):
    """**403 を1つ買いに行かせないこと。**"""
    _patch(monkeypatch, is_open=False)
    note = J._refresh_pool_note({"refresh": "python scripts/snapshot.py"})
    assert "この窓では撃てません" in note
    assert "いま撃てます" not in note


def test_日枠が開いていれば何も足さない(monkeypatch):
    """**区別に意味がない場面で口を開かないこと**（毎行に付くと読まれなくなります）。"""
    _patch(monkeypatch, is_open=True)
    assert J._refresh_pool_note({"refresh": "python -m src.rpm_mix --forms"}) == ""
    assert J._refresh_pool_note({"refresh": "python scripts/snapshot.py"}) == ""


def test_quota欄の申告が一覧より優先する(monkeypatch):
    """`needs.quota:` は `_quota_gate` と同じ順で効くこと（2か所で食い違わせない）。"""
    _patch(monkeypatch, is_open=False)
    forced = J._refresh_pool_note({"refresh": "python -m src.rpm_mix --forms",
                                   "quota": "data_api"})
    assert "この窓では撃てません" in forced
    freed = J._refresh_pool_note({"refresh": "python scripts/snapshot.py",
                                  "quota": "none"})
    assert "いま撃てます" in freed


def test_refreshが無ければ黙る(monkeypatch):
    _patch(monkeypatch, is_open=False)
    assert J._refresh_pool_note({}) == ""


def test_stale_todoが枠の判定を連れてくる(monkeypatch, tmp_path):
    """**入口はこちら。** `_stale_todo` が `_refresh_pool_note` を呼んでいること。"""
    _patch(monkeypatch, is_open=False)
    p = tmp_path / "video_forms.json"
    p.write_text('{"at": "2020-01-01", "forms": {}}\n', encoding="utf-8")
    monkeypatch.setattr(J, "ROOT", tmp_path, raising=False)
    note = J._stale_todo({"data_file": "video_forms.json",
                          "refresh": "python -m src.rpm_mix --forms"})
    assert "待ち方が違います" in note, "古い計器を古いと言えていません"
    assert "いま撃てます" in note, "**枠の判定が下流に降りていません**"
