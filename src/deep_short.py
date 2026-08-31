"""**「深い題のショート」の前提を、`falsified_if` の手順そのままで数える。**

対象（`config/hypotheses.yaml`・腕 `per_video`）:

    深い題（`s-` で始まらない・節を持つ題）をショートとして出すと、
    1本あたり再生が `s-` の題のショートより上がる

**API は1単位も使いません**（`data/uploaded.jsonl` / `data/views.jsonl` /
`data/video_forms.json` だけ）。CLI は `scripts/deep_short_verdict.py`。

## なぜ 1か所にしたか（2026-08-29 06:3x・最適化の回）

**門と、判定の手順が、別の母集団を数えていました。**

その日、`deadline_check` は **[OK] 判定できるのは 08-29**（＝今日）と言い、
`drift.py` は **「外れています。いま判定できる前提の期限が来ているのに、
直近20回で1件も判定していません」**と鳴っていました。
ところが `falsified_if` の手順をそのまま解くと、**判定できません**:

    門の数え方                        手順の数え方（`falsified_if`）
    ─────────────────────────────     ─────────────────────────────
    `uploaded` の `s-` でない本 15本   処置 **4本**（要 8本）
    `deep_short_days()`        3日    使える日 **2日**（要 3日）

門が落としていた条件は、`falsified_if` が**明記している3つ**です:

    1. その日の**生きた帯**の中だけ（`day_cap.live_ids`。帯の外は0再生）
    2. **齢48時間 の読み**が在ること（`data/views.jsonl`）
    3. その公開日に**処置と対照が両方 居る**こと

**門は「作った／公開した」を数え、手順は「比べられる」を数えます。**
`falsified_if` は、この条件を外して判定した場合に何が起きるかまで書いています
——「題の差と日の差を分離できない」。実際 2026-08-26 に**符号が反転する
割り方**で一度 測られており、その記録も同じ台帳に残っています。

**だから門の `count_expr` を、ここへ向けました。** 2か所が別々に同じ問いを
解くのをやめる、という `_ans_group_key`（2026-08-25）と同じ合流です。

**覆る条件**: `falsified_if` の本文が変わったら、**同じ回のうちに**ここも
合わせること。片方だけ動かすと、台帳と道具で答えが割れます。
検査は `tests/test_deep_short_verdict.py`。
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

#: `falsified_if` の「齢48時間でそろえた」
AGE_H = 48.0
#: `falsified_if` の「どちらも 8本 に満たなければ判定できない」
MIN_PER_ARM = 8
#: `falsified_if` の「使える日が 3日 未満なら判定できない」
MIN_DAYS = 3
#: `falsified_if` の合格点
BAR = 1.2


def _forms() -> dict[str, str]:
    fp = ROOT / "data" / "video_forms.json"
    if not fp.exists():
        return {}
    try:
        return (json.loads(fp.read_text(encoding="utf-8")) or {}).get("forms") or {}
    except (OSError, ValueError):
        return {}


def _uploaded_last() -> dict[str, dict]:
    """`video_id` → **最後の行**（`reschedule.py` が公開時刻を動かすと行が増える）。"""
    out: dict[str, dict] = {}
    fp = ROOT / "data" / "uploaded.jsonl"
    if not fp.exists():
        return out
    for line in fp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("video_id") and r.get("at"):
            out[str(r["video_id"])] = r
    return out


def measure(as_of: date | None = None) -> dict:
    """`falsified_if` の4段を、そのまま解く。**API 0単位。**

        1. 公開日ごとに、その日の**生きた帯**（`day_cap.live_ids`）の中だけを取る
        2. **処置と対照が両方 1本以上ある日**だけを使う
        3. 日ごとに「処置の平均 ÷ 対照の平均」を出し、**その比の中央値**を見る
        4. **使える日が 3日 未満なら判定できない。** 期限を延ばすこと
    """
    from . import day_cap                       # 重いので遅延（`views.jsonl` を読む）

    today = as_of or datetime.now(JST).date()
    forms, last = _forms(), _uploaded_last()
    readings = day_cap._readings(min_age_h=AGE_H)      # id → (公開JST, 齢, 再生)

    rows = [{"at": datetime.fromisoformat(str(r["at"])), "video_id": vid}
            for vid, r in last.items()]
    live = day_cap.live_ids([r for r in rows if isinstance(r["at"], datetime)])

    per_day: dict[date, dict[str, list[int]]] = {}
    n_arm = {"処置": 0, "対照": 0}
    for vid, r in last.items():
        if forms.get(vid) != "ショート":
            continue
        if vid not in readings:
            continue                                   # 齢48時間 の読みがまだ無い
        if vid not in live:
            continue                                   # 1. その日の生きた帯だけ
        pub, _h, views = readings[vid]
        day = pub.date()
        if day > today:
            continue
        side = "対照" if str(r.get("topic", "")).startswith("s-") else "処置"
        n_arm[side] += 1
        per_day.setdefault(day, {}).setdefault(side, []).append(views)

    # 2. 処置と対照が両方 1本以上ある日だけ
    usable = {d: s for d, s in per_day.items() if s.get("処置") and s.get("対照")}
    # 3. 日ごとの比 → その中央値
    ratios = {d: statistics.fmean(s["処置"]) / statistics.fmean(s["対照"])
              for d, s in sorted(usable.items()) if statistics.fmean(s["対照"]) > 0}

    out: dict = {"as_of": today, "n_treat": n_arm["処置"], "n_ctrl": n_arm["対照"],
                 "days": len(ratios), "ratios": ratios, "bar": BAR,
                 "median": statistics.median(ratios.values()) if ratios else None,
                 "per_day": usable}

    why = []
    if n_arm["処置"] < MIN_PER_ARM or n_arm["対照"] < MIN_PER_ARM:
        why.append(f"群が {MIN_PER_ARM}本 に満たない"
                   f"（処置 {n_arm['処置']} ／ 対照 {n_arm['対照']}）")
    if len(ratios) < MIN_DAYS:
        why.append(f"使える日が {MIN_DAYS}日 未満（{len(ratios)}日）")
    out["blocked"] = why
    out["verdict"] = None if why else (
        "survived" if out["median"] >= BAR else "falsified")
    return out


# --- `deadline_check` の `count_expr` が呼ぶ2つ（**門と手順を同じ数にする**）----

def arm_n(side: str = "処置") -> int:
    """比べられる本の数（`falsified_if` の群の作り方そのまま）。"""
    return int(measure()["n_treat" if side == "処置" else "n_ctrl"])


def usable_days() -> int:
    """**比が出せる公開日**の数（生きた帯 ＋ 齢48時間 ＋ 両群そろい）。

    `deadline_check.deep_short_days()` は 1 と 2 を見ていませんでした。
    実測 2026-08-29: あちらは **3日**、こちらは **2日**。
    """
    return int(measure()["days"])


def by_family(as_of: date | None = None) -> dict:
    """**族をそろえて、同じ比を出し直す**（`next_if_false` が指した先）。

    `falsified_if` の群の作り方は `measure()` と**同じ**まま、割り方だけを
    「公開日ごと」から「族ごと」に替えます（`family_perf._video_calc`）。

    ## なぜ要るか（2026-08-31 に、この前提を閉じた回が足した）

    `next_if_false` は外れたときの次の手を1つだけ書いています ——
    「**次に疑うのは族**。深い題は `calc_sections` を持つぶん族が偏っており
    （`nenkin` `iryohi` `zangyo` …）、`src/family_perf.py` が実測で族べつに
    4倍の差を出している。題の『深さ』ではなく族が効いているなら、
    族を揃えて比べ直すこと」。

    **偏りは実在します**（実測 2026-08-31: 処置 8本 が 8族 に1本ずつ・
    対照 103本 が 46族）。だから「族が効いているのを題の深さと読み違えた」は
    真っ当な疑いでした。**答えは救済ではなく追認です**:

        族をそろえない（`measure()`）  比の中央値 **×0.72**
        族をそろえた（この関数）        比の中央値 **×0.35**  ← **さらに悪い**
        両群がそろう族 **8件** が、**8件とも 1.0 未満**

    族が交絡していたなら、そろえた時に合格点（×1.2）へ寄るはずでした。
    **逆に半分になったので、深い題の不利は族では説明できません。**

    **覆る条件**: 処置が族あたり1本しかありません（8族 × 1本）。
    処置が同じ族で 3本 以上たまったら、**族ごとの平均が1本の当たり外れで
    振れなくなる**ので、そこで撃ち直すこと。中央値が ×1.2 を超えたら、
    この結論は覆ります。検査は `tests/test_deep_short_family.py`。
    """
    from . import day_cap, family_perf

    today = as_of or datetime.now(JST).date()
    forms, last = _forms(), _uploaded_last()
    readings = day_cap._readings(min_age_h=AGE_H)

    rows = [{"at": datetime.fromisoformat(str(r["at"])), "video_id": vid}
            for vid, r in last.items()]
    live = day_cap.live_ids([r for r in rows if isinstance(r["at"], datetime)])
    vcalc = family_perf._video_calc(family_perf.known_calcs())

    per_fam: dict[str, dict[str, list[int]]] = {}
    for vid, r in last.items():
        if forms.get(vid) != "ショート":
            continue
        if vid not in readings or vid not in live:
            continue                                   # `measure()` と同じ3条件
        pub, _h, views = readings[vid]
        if pub.date() > today:
            continue
        side = "対照" if str(r.get("topic", "")).startswith("s-") else "処置"
        per_fam.setdefault(vcalc.get(vid, ""), {}).setdefault(side, []).append(views)

    usable = {f: s for f, s in per_fam.items()
              if f and s.get("処置") and s.get("対照")
              and statistics.fmean(s["対照"]) > 0}
    ratios = {f: statistics.fmean(s["処置"]) / statistics.fmean(s["対照"])
              for f, s in usable.items()}
    return {"as_of": today, "per_family": usable, "ratios": ratios,
            "families": len(ratios), "bar": BAR,
            "median": statistics.median(ratios.values()) if ratios else None}
