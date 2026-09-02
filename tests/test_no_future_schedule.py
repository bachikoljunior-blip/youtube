"""**先の日付へは、もう1本も置けないこと**（規則5・固定その4の「置く側」）。

## なぜ要るか（2026-09-02・オーナー原文）

> **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

**「今後」の側は、外す側では塞げません。** `scripts/pool_drain.py` も
`scripts/ahead_gate.py` も、**もう置かれたものを外す**道具です。
置く側が開いたままなら、外した先から積み直せます —— そして**開いていました**:

    src.uploader.next_publish_at()  きょうの枠が過去／埋まっていると
                                    `target += timedelta(days=1)` で翌日以降へ歩く
                                    （最大60日先まで）
    scripts/reschedule._update()    `publish_at` に何を渡しても、そのまま書く

**459本 → 107本 の作り置きは、この2つが積んだものです。**

## 塞ぎ方（**判定は1か所。写しを作らないこと**）

    src.house_rule.refuse_future_publish()   ← 判定の本文はここだけ
      ├ scripts/reschedule._update()          `videos.update` の関門（例外で止める）
      ├ src.uploader.next_publish_at()        釘づけの道（例外で止める）
      └ src.uploader.upload()                 自動探索の道（**下書きへ倒す**）

**自動探索だけ倒す形にしてあるのは、例外にすると枠の埋まった日に
投稿そのものが落ちるから**です（`CLAUDE.md`「**投稿が途切れるのが最大の損失**」）。
下書きなら物は上がり、その日になってから `--move` で予約できます。

## 覆る条件

オーナーが「先の日付にも置いてよい」と言ったら
`house_rule.SAME_DAY_SCHEDULING_ONLY` が `False` になり、**4か所とも同時に緩みます**
（`test_規則5_が外れたら4か所とも緩む`）。**片方だけ残さないこと。**
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import house_rule, uploader  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "reschedule_mod", ROOT / "scripts" / "reschedule.py")
reschedule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reschedule)

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)          # 09/02 14:00 JST


def _stamp(days: int, hour: int = 20, base: datetime | None = None) -> str:
    """`base`（既定は `NOW`）の JST 日付から `days` 日ずらした日の `hour` 時。"""
    day = ((base or NOW).astimezone(JST) + timedelta(days=days)).date()
    t = datetime(day.year, day.month, day.day, hour, 0, tzinfo=JST)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _real(days: int, hour: int = 20) -> str:
    """**本物のいま**を起点にした時刻。

    `reschedule.house_rule` は `src.house_rule` **そのもの**なので、
    そこへ偽の `now` を差し込むと自分を呼び直して落ちます（実際に踏んだ）。
    関門の検査は、本物の時計のまま撃つこと。
    """
    return _stamp(days, hour, base=datetime.now(timezone.utc))


# ------------------------------------------------------------------ 判定そのもの
def test_きょうは通る():
    assert house_rule.refuse_future_publish(_stamp(0), NOW) == ""


def test_明日は断る():
    why = house_rule.refuse_future_publish(_stamp(1), NOW)
    assert why
    assert "先の日付" in why


def test_外す手は通る():
    """`publish_at=None` は**予約を外す手**（池化）。ここを断ると外せなくなる。"""
    assert house_rule.refuse_future_publish(None, NOW) == ""


def test_読めない時刻では止めない():
    """推測で投稿を止めないこと（`CLAUDE.md`「投稿が途切れるのが最大の損失」）。"""
    assert house_rule.refuse_future_publish("あした", NOW) == ""


def test_規則5_が外れたら黙る(monkeypatch):
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", False)
    assert house_rule.refuse_future_publish(_stamp(30), NOW) == ""


# ------------------------------------------------------------------ 書く側の関門
class _Svc:
    """`videos.list` が呼ばれたら**そこで落とす**。門は単位を使う前に効くこと。"""
    def videos(self):
        raise AssertionError("**単位を使う前に断ること** —— videos.list が呼ばれた")


def test_故障を注入すると発火する_先の日付への_update():
    """**注入する故障**: 明日 20:00 JST へ `--move` する。"""
    with pytest.raises(SystemExit) as e:
        reschedule._update(_Svc(), "vid", _real(1))
    assert "先の日付" in str(e.value)


def test_きょうへの_update_は関門を素通りする():
    """**常に断る実装を落とす検査。** 門の先（`videos.list`）まで届くことを見る。"""
    with pytest.raises(AssertionError, match="単位を使う前に"):
        reschedule._update(_Svc(), "vid", _real(0))


def test_外す手は関門を素通りする():
    """池化（`publish_at=None`）が止まったら、作り置きが1本も外せなくなる。"""
    with pytest.raises(AssertionError, match="単位を使う前に"):
        reschedule._update(_Svc(), "vid", None)


# ------------------------------------------------------------------ 投稿の側
def test_釘づけの道は_先の日付で例外(monkeypatch):
    """`--date <先の日>` は黙って別の日へ置き換えない（測っている数字が壊れる）。"""
    monkeypatch.setattr(uploader.measure_window, "check",
                        lambda *a, **k: None)
    tomorrow = (datetime.now(JST) + timedelta(days=3)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError, match="先の日付"):
        uploader.next_publish_at(20, 0, taken=set(), date_jst=tomorrow)


def test_釘づけの道は_きょうなら通る(monkeypatch):
    """**常に断る実装を落とす検査。** きょうの先の時刻は返ること。

    **`now.hour + 1` にしないこと**（2026-09-02 に踏んだ）—— `next_publish_at` は
    「予約は 20分先から」で弾くので、**15:45 に撃つと 16:00 が 15分先**になり、
    規則5 とは無関係の `ValueError` で落ちます。**時計しだいで色が変わる検査**でした。
    余白を大きく取り、足りない時間帯は見送ります。
    """
    monkeypatch.setattr(uploader.measure_window, "check", lambda *a, **k: None)
    now = datetime.now(JST)
    hour = now.hour + 2
    if hour > 23:                            # きょうの残りに 2時間 無い回は見送る
        pytest.skip("きょうの中に 2時間 先の枠が残っていません")
    got = uploader.next_publish_at(hour, 0, taken=set(),
                                   date_jst=now.strftime("%Y-%m-%d"))
    assert got.endswith("Z")


# ------------------------------------------------------------------ 4か所そろい
def test_判定の写しを作っていないこと():
    """**写すと「片方だけ直す」に戻ります**（この repo が通算12回 踏んだ形）。

    呼ぶ側3か所は `house_rule.refuse_future_publish` を**呼ぶだけ**で、
    自分で日付を比べないこと。
    """
    for rel in ("scripts/reschedule.py", "src/uploader.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "refuse_future_publish" in text, rel


def test_規則5_が外れたら4か所とも緩む(monkeypatch):
    """緩むのも1か所から。**片方だけ残さないこと。**"""
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", False)
    assert house_rule.refuse_future_publish(_stamp(1), NOW) == ""
    # **`reschedule.house_rule` は `src.house_rule` そのもの** ——
    #     上の1行を倒すだけで、関門も一緒に緩むのが正しい姿。
    with pytest.raises(AssertionError, match="単位を使う前に"):
        reschedule._update(_Svc(), "vid", _real(1))


def test_予約時刻を書く所は_2か所しかないこと():
    """**7つ目の入口を作らせないこと。**

    `reschedule._update()` の docstring:「入口が6つあり、塞いでも**7つ目が
    同じ穴を作ります**（この repo が通算11回 踏んでいる「片方だけ」の形）。
    **関門はここ1か所なので、ここで止めます**」。

    その関門は `status["publishAt"] = …` を書く所にしか効きません。
    **新しく書く所を足した回は、ここで落ちます** —— そのときは、
    足した所からも `house_rule.refuse_future_publish()` を呼ぶこと
    （**判定を写さないこと**。写すと、また片方だけ直せます）。

    `videos().update(part="snippet", …)`（`link_longform` / `retitle`）は
    ここに入りません —— `status` を触らないので、予約を作れません。
    """
    import re
    hits = []
    for rel in sorted(list((ROOT / "src").glob("*.py"))
                      + list((ROOT / "scripts").glob("*.py"))):
        text = rel.read_text(encoding="utf-8")
        for line in text.splitlines():
            if re.search(r'\["publishAt"\]\s*=', line):
                hits.append(rel.relative_to(ROOT).as_posix())
                break
    assert hits == ["scripts/reschedule.py", "src/uploader.py"], hits
    for rel in hits:
        assert "refuse_future_publish" in (ROOT / rel).read_text(encoding="utf-8"), rel
