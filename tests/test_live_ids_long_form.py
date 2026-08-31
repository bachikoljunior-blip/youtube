"""**`day_cap.live_ids()` は長尺を外します。** そして**長尺を控えの尺で見分けます。**

## この検査が 2026-08-29 に取り逃したもの（2026-08-30 に書き直した）

前の版はこう書いていました ——「いまは 0本 の差ですが、機構は在ります。
**落ちたら、そのときが `include_long` を足す回**です」。
**落ちませんでした。条件は満たされていたのに。**

理由は、検査が `day_cap._long_ids()` を使っていたことです。あれは
`data/video_forms.json`（Analytics の `creatorContentType`）だけを読み、
**公開して再生の付いた本にしか付きません** —— つまり
**予約ぶんの長尺が、1本も入っていませんでした。** 実測（2026-08-30）:

    `forms()` が「長尺」と言う本            **18本**
    控えの `duration_s` が 180秒 以上の本   **98本**
    **重なり                                  1本**

同じ日の同じ帳面を、控えの尺で数え直すと:

    `forms()` 由来の 18本 で見る   帯の枠を取っている長尺 **0本** ／ 落ちたショート **0本**
    控えの尺で見る                 帯の枠を取っている長尺 **16本** ／ 落ちたショート **7本**

**見張りと見張られる側が、同じ目で見ていました。**
だからこの検査は「`_long_ids()` を信じて数える」形をやめます ——
**長尺の一覧を、この検査が自分で `data/uploaded.jsonl` から引きます。**
道具の側が壊れても、ここは独立に気づけます。

## いま守っているもの

  1. `live_ids()` の既定は長尺を外す（`by_day()` と同じ）
  2. `_long_ids()` は控えの `duration_s` を見る（＝予約ぶんが入る）

**覆る条件**: 長尺がショートの面（`SHORTS_FEED`）の枠を実際に食うと分かったら、
`live_ids()` と `by_day()` の既定を**同時に**戻すこと。
控えに 55〜260秒 の本が現れたら、180秒 の境目は使えません（尺の分布が二山でなくなる）
—— そのときは `_long_by_duration()` の「二山」の節から測り直すこと。
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "uploaded.jsonl"


def _long_from_ledger(min_s: float = 180.0) -> set[str]:
    """**この検査が自分で引く長尺の一覧。** `day_cap` の実装を1行も使いません。"""
    out: set[str] = set()
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid, sec = r.get("video_id"), r.get("duration_s")
        if not vid or sec is None:
            continue
        try:
            long_form = float(sec) >= min_s
        except (TypeError, ValueError):
            continue
        out.add(str(vid)) if long_form else out.discard(str(vid))
    return out


def test_live_ids_は長尺を1本も返さない():
    """既定で外れていること。**返っていたら、ショートの枠を食っている。**"""
    from src import day_cap
    from src.ab_split import published

    rows = [r for r in published() if r.get("at")]
    if not rows:
        pytest.skip("控えが読めません（データが無い環境）")
    longs = _long_from_ledger()
    if not longs:
        pytest.skip("控えに `duration_s` の入った長尺がありません")

    taken = day_cap.live_ids(rows) & longs
    assert not taken, (
        f"`live_ids()` が長尺 {len(taken)}本 を返しています。"
        "既定は `include_long=False` のはず（`by_day()` と同じ）。"
        "戻すなら `by_day()` の既定も同時に戻すこと")


def test_long_ids_は控えの尺を見る():
    """**`video_forms.json` だけを見ていた頃に戻ったら落ちます。**

    あれは公開して再生の付いた本にしか付かないので、**予約ぶんが見えません。**
    2026-08-29 の検査が条件を満たしたまま緑だったのは、これが理由です。
    """
    from src import day_cap

    longs = _long_from_ledger()
    if not longs:
        pytest.skip("控えに `duration_s` の入った長尺がありません")

    missing = longs - day_cap._long_ids()
    assert not missing, (
        f"控えの尺で長尺と分かる {len(missing)}本 を、`_long_ids()` が見落としています"
        f"（例 {sorted(missing)[:3]}）。`data/video_forms.json` だけを"
        "読む形に戻っていないか見ること（`_long_by_duration()` の節）")


def test_尺の分布は二山のまま():
    """**180秒 の境目が、どちらの山も切っていないこと。**

    切りはじめたら尺だけでは形を割れません（`_long_by_duration()` の「覆る条件」）。
    実測 2026-08-30: 控えの 178本 に **55〜260秒 の本は 1本もありません**。
    """
    if not LEDGER.exists():
        pytest.skip("控えがありません")
    near: list[tuple[str, float]] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        sec = r.get("duration_s")
        if sec is None:
            continue
        try:
            s = float(sec)
        except (TypeError, ValueError):
            continue
        if 65.0 <= s <= 175.0:
            near.append((str(r.get("video_id")), s))
    assert not near, (
        f"境目（180秒）の近くに {len(near)}本 あります（例 {near[:3]}）。"
        "**尺だけでは形を割れません。** `_long_by_duration()` の「二山」の節から"
        "測り直すこと —— `data/video_forms.json` と突き合わせる道が要ります")


def test_同じ本について控えと_forms_が食い違わない():
    """両方に載っている本で、**答えが割れていないこと。**（実測 2026-08-30: 食い違い 0件）"""
    from src import day_cap

    forms = day_cap.forms()
    longs = _long_from_ledger()
    if not forms or not longs:
        pytest.skip("突き合わせる材料がありません")
    bad = [v for v, f in forms.items()
           if (f == day_cap.LONG_FORM) != (v in longs) and v in _ledger_ids()]
    assert not bad, (
        f"控えの尺と `video_forms.json` が {len(bad)}本 で食い違っています"
        f"（例 {bad[:3]}）。どちらが正しいかを決めてから、片方を消すこと")


def _ledger_ids() -> set[str]:
    """控えに `duration_s` のある本だけ（**尺の分からない本は突き合わせない**）。"""
    out: set[str] = set()
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("video_id") and r.get("duration_s") is not None:
            out.add(str(r["video_id"]))
    return out


def test_include_long_true_で前の姿に戻せる():
    """**比べる道を残しておくこと**（`by_day()` と同じ）。合成データで確かめます。"""
    from src import day_cap

    jst = dt.timezone(dt.timedelta(hours=9))
    day = dt.datetime(2026, 9, 1, 9, 0, tzinfo=jst)
    rows = [{"video_id": "a", "at": day},
            {"video_id": "b", "at": day + dt.timedelta(minutes=30)}]
    both = day_cap.live_ids(rows, include_long=True)
    assert both == {"a", "b"}, both
