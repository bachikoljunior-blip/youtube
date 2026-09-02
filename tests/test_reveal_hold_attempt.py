"""**「判定できます」と言った回に、判定できないこと**を、跡で塞ぐ。

## 実物（2026-09-02・最適化の回。**同じ回の中で2つのことを言っていた**）

    python -m src.reveal_hold            両群がそろう公開日: **4日** → **判定できます**
    python -m src.reveal_hold --judge    比の取れた本 17本 ／ 対にできた日 **2日**
                                         {'decided': False, 'why': '… 2日（要 3日）'}

`paired_days()` は**控えだけ**で数えます（その日に両群の本が居るか）。
`ratios_by_day()` は、そこへ **Analytics の engaged 比**を join します ——
比の付かない本が落ちて **4日 → 2日**（08/28・08/29 が消えた）。
`verdict()` が見ているのは後者です。

そして `config/hypotheses.yaml` の `needs` は
`min(reveal_hold_arm('処置'), reveal_hold_arm('対照'))` ＝ **本の数**しか
数えていませんでした（16本 は満ちている）。だから
`scripts/deadline_check.py` は `[OK]`、`scripts/eta.py` は頭の3行で
**「この回は `verdict` で日付が動かせます」**とこの前提を名指しします。
**頭3行しか読まない回は、2日ぶんの中央値で前提を閉じます** ——
閉じた前提は軌跡の腕を動かすので、**到達日が在りもしないデータで動きます。**

この前提の註が、同じ形の穴を自分で2回 数えています
（`deep_short_arm()` 2026-08-29 が1件目、`arm_n` の行／本 が2件目）。
**これが3件目です。** 違いは **0単位 では見えないこと** ——
比が付くかは Analytics を撃つまで分かりません。だから
**撃った結果のほう**を控えに残します（`record_attempt`）。

## 発火を確かめてあること（**発火したことのない検査は検査ではない**）

- `test_render_says_not_judgeable_after_a_short_attempt` … 跡が「足りない」なら黙る（発火）
- `test_render_offers_the_shot_when_never_attempted` … 一度も撃っていなければ撃てと言う
  （**常に「まだです」と言う実装を落とす**）
- `test_judgeable_days_prefers_the_attempt` … 上限ではなく実測を返す

## 覆る条件

比の付かなかった本にあとから Analytics が比を付けたら（遅れ 2〜3日）、
同じ日が生き返ります。**だから跡は積み**、`last_attempt()` は新しい行を読みます。
`--judge` を撃ち直せば、次の行がその日を数え直します。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import reveal_hold  # noqa: E402

NOW = datetime(2026, 9, 2, 6, 0, tzinfo=timezone.utc)


def _attempt(tmp_path: Path, pairs: int, decided: bool) -> Path:
    p = tmp_path / "reveal_hold_attempts.jsonl"
    p.write_text(json.dumps(
        {"ts": "2026-09-02T06:01:00+00:00", "pairs": pairs,
         "need_days": reveal_hold.NEED_DAYS, "decided": decided,
         "why": "", "verdict": ""}, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def test_record_then_read_round_trips(tmp_path):
    p = tmp_path / "a.jsonl"
    reveal_hold.record_attempt(
        {"decided": False, "why": "両群がそろう公開日が 2日（要 3日）"}, 2,
        now=NOW, path=p)
    got = reveal_hold.last_attempt(p)
    assert got is not None
    assert got["pairs"] == 2 and got["decided"] is False


def test_last_attempt_reads_the_newest_line(tmp_path):
    """**跡は積みます。** あとから比が付いた回を、古い行で潰さないため。"""
    p = tmp_path / "a.jsonl"
    reveal_hold.record_attempt({"decided": False}, 2, now=NOW, path=p)
    reveal_hold.record_attempt({"decided": True, "verdict": "survived"}, 4,
                               now=NOW, path=p)
    got = reveal_hold.last_attempt(p)
    assert got["pairs"] == 4 and got["decided"] is True


def test_judgeable_days_prefers_the_attempt(tmp_path):
    """**上限（控えだけの `paired_days`）ではなく、撃った実測を返すこと。**"""
    p = _attempt(tmp_path, pairs=2, decided=False)
    assert reveal_hold.judgeable_days(path=p) == 2


def test_judgeable_days_falls_back_to_the_ceiling(tmp_path):
    """一度も撃っていない回は `paired_days()`（上限）。**最初の1回は撃つしかない。**"""
    p = tmp_path / "missing.jsonl"
    got = reveal_hold.judgeable_days(now=NOW, rows=[], path=p)
    assert got == 0          # rows が空なので上限も 0


def test_render_says_not_judgeable_after_a_short_attempt(tmp_path, monkeypatch):
    """**発火。** 跡が「2日（要 3日）」なら、`判定できます` と言わないこと。"""
    p = _attempt(tmp_path, pairs=2, decided=False)
    monkeypatch.setattr(reveal_hold, "ATTEMPTS", p)
    monkeypatch.setattr(reveal_hold, "comparable",
                        lambda *a, **k: {"処置": [f"t{i}" for i in range(16)],
                                         "対照": [f"c{i}" for i in range(21)]})
    monkeypatch.setattr(reveal_hold, "paired_days", lambda *a, **k: {})
    monkeypatch.setattr(reveal_hold, "next_ready", lambda *a, **k: None)
    out = reveal_hold.render(now=NOW)
    assert "まだ判定できません" in out
    assert "比の取れた日は 2日" in out


def test_render_offers_the_shot_when_never_attempted(tmp_path, monkeypatch):
    """**常に「まだです」と言う実装を落とすため。**"""
    monkeypatch.setattr(reveal_hold, "ATTEMPTS", tmp_path / "none.jsonl")
    monkeypatch.setattr(reveal_hold, "comparable",
                        lambda *a, **k: {"処置": [f"t{i}" for i in range(16)],
                                         "対照": [f"c{i}" for i in range(21)]})
    monkeypatch.setattr(reveal_hold, "paired_days", lambda *a, **k: {})
    monkeypatch.setattr(reveal_hold, "next_ready", lambda *a, **k: None)
    out = reveal_hold.render(now=NOW)
    assert "判定を撃てます" in out
    assert "「判定できる」ではありません" in out


def test_gate_reads_the_same_number():
    """**門と判定が同じ数を数えていること**（`scripts/deadline_check.reveal_hold_days`）。"""
    from scripts import deadline_check                          # noqa: PLC0415
    assert "reveal_hold_days" in deadline_check.EXPR_NS
    assert deadline_check.reveal_hold_days() == reveal_hold.judgeable_days()


def test_the_premise_gates_on_judgeable_days():
    """**台帳の側も、本の数だけで満ちたと言わないこと。**"""
    import yaml                                                 # noqa: PLC0415
    rows = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(
        encoding="utf-8"))
    rows = rows["hypotheses"] if isinstance(rows, dict) else rows
    hit = [h for h in rows
           if "完成した図を説明のあいだ画面に残す" in str(h.get("claim") or "")]
    assert hit, "前提が見つかりません"
    exprs = [str(n.get("count_expr") or "") for n in (hit[0].get("needs") or [])]
    assert any("reveal_hold_days" in e for e in exprs), \
        "本の数だけを門にしています（`verdict()` は比の取れた日を見ます）"
