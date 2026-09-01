"""`scripts/reschedule.py --compact` の割り当てと、控えの書き換え。

**この道具は251本の予約を動かします。**間違えると、投稿が途切れるか、
測定中の窓を踏むか、同じ割り当てを2回目に出せなくなります。
守っている条件は3つで、ここで固定します:

    1. **新しい時刻は必ず今より前か同じ**（途中で止まっても、やり直せる）
    2. 測定の窓（`src.measure_window`）の日は、置き先からも対象からも外す
    3. 控え（`data/uploaded.jsonl`）は**足さずに書き換える**（幻の埋まりを残さない）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import dupes  # noqa: E402

reschedule = pytest.importorskip("reschedule")

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 18, 2, 0, tzinfo=timezone.utc)      # 08/18 11:00 JST
EMPTY = ("", "")


def _row(vid: str, at_jst: str, topic: str = "s-x") -> dict:
    at = datetime.fromisoformat(at_jst).replace(tzinfo=JST).astimezone(timezone.utc)
    return {"id": vid, "topic": topic, "title": vid,
            "at": at.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _jst(stamp: str) -> str:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(
        JST).strftime("%Y-%m-%dT%H:%M")


def test_1時間きざみの3日ぶんが30分きざみの1日に詰まる():
    """**錨は 2026-09-02 に「いちばん早い予約の日」から「いちばん早く撃てる日」へ移りました。**

    以前はここが `08/24`（＝ `v0` の日）で、`v0` だけ動かない形でした。
    いまは床（`now + lead_min` ＝ 08/18 12:00 JST）の日から埋めるので、
    **18本 とも動きます。**理由は `compact_plan` の「その錨は、1本 公開される
    だけで 22日 跳びます」の節（実測で穴の20日が目盛りから消えました）。
    """
    rows = [_row(f"v{i}", f"2026-08-2{4 + i // 6}T{9 + i % 6:02d}:00") for i in range(18)]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=1, window=EMPTY)
    # 08/18 の 12:30〜21:00（30分きざみ・床の後ろ）に18本 とも入る
    assert {p["id"] for p in plan} == {f"v{i}" for i in range(18)}
    assert _jst(plan[0]["new"]) == "2026-08-18T12:30"
    assert _jst(plan[-1]["new"]) == "2026-08-18T21:00"
    for p in plan:
        assert p["new"] <= p["old"], p


def test_動かす先はいつも今より前か同じ():
    rows = [_row(f"v{i}", f"2026-08-2{4 + i // 6}T{9 + i % 6:02d}:00") for i in range(18)]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=2, window=EMPTY)
    for p in plan:
        assert p["new"] <= p["old"], p


def test_途中で止めても2回目が同じ割り当てを出す():
    """**`videos.update` は日枠で 190本ぶんしか撃てません。**途中で止まります。"""
    rows = [_row(f"v{i}", f"2026-08-2{4 + i // 6}T{9 + i % 6:02d}:00") for i in range(18)]
    first = reschedule.compact_plan(rows, now=NOW, max_days=1, window=EMPTY)
    half = first[:5]
    moved = {p["id"]: p["new"] for p in half}
    after = [dict(r, at=moved.get(r["id"], r["at"])) for r in rows]
    second = reschedule.compact_plan(after, now=NOW, max_days=1, window=EMPTY)
    assert {(p["id"], p["new"]) for p in second} == {
        (p["id"], p["new"]) for p in first[5:]}


def test_測定の窓は置き先からも対象からも外れる():
    """窓の中の本は動かさず、**窓の日には1本も置きません**（M14）。"""
    win = ("2026-08-26", "2026-08-27")
    rows = [_row("in", "2026-08-26T09:00")] + [
        _row(f"v{i}", f"2026-08-2{5 + i // 6}T{9 + i % 6:02d}:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=2, window=win)
    assert "in" not in {p["id"] for p in plan}
    days = {_jst(p["new"])[:10] for p in plan}
    # **窓の日には1本も置かない**（ここが本題）。置き先の日そのものは、
    # 2026-09-02 に錨が「いちばん早く撃てる日」へ移ったので床の側から始まります。
    assert days & {"2026-08-26", "2026-08-27"} == set()
    assert days <= {"2026-08-18", "2026-08-19"}
    for p in plan:
        assert p["new"] <= p["old"], p


def test_錨はいちばん早く撃てる日で_いちばん早い予約の日ではない():
    """**2026-09-02 に置き換えました。** 前は「いちばん早い予約の日から。
    それより前は、窓か、目前の日」でした。

    **その錨は、予約の山の手前が1本 公開されるだけで、山の日まで跳びます。**
    実測（2026-09-02 01:0x・控えの実物 108本）——
    先頭 `a63FzIUV2wI`（09/02 13:00）／2本目 `Eggpp86CkDk`（09/24 10:30）／
    あいだの **09/03〜09/23 は 0本**。13:00 にその1本が出た後は錨が 09/24 になり、
    **穴の20日が目盛りから丸ごと消えて**、`max_days` を 26〜40 の
    どれにしても「後ろへ動かす割り当て」で `SystemExit` ＝ **1本も動きません**。

    「窓」は `measure_window` が別に外し、「目前の日」は `lead_min` と
    `writable_from` が外します。**錨に兼ねさせる理由はありませんでした。**

    **覆る条件**: `live_edge_min` が 1日 複数枠に戻り（＝ 規則1 が外れ）、
    錨を山に置いても後ろ向きの割り当てが出なくなったら、この検査は要りません。
    """
    rows = [_row("a", "2026-09-01T09:00"), _row("b", "2026-09-02T09:00")]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=1, window=EMPTY)
    assert [p["id"] for p in plan] == ["a", "b"]
    assert _jst(plan[0]["new"]) == "2026-08-18T12:30"      # 床（08/18 12:00）の直後
    for p in plan:
        assert p["new"] <= p["old"], p


def test_動かせない本が埋めている日には置かない():
    """`floor` より前に出る本の日は、目盛りから外す（置くと **1日2本**）。"""
    rows = [_row("soon", "2026-08-18T11:30"),      # 床（12:00）の手前 ＝ 動かせない
            _row("ok", "2026-09-01T09:00")]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=1, lead_min=60,
                                   window=EMPTY)
    assert [p["id"] for p in plan] == ["ok"]
    # 08/18 は `soon` が埋めているので、置き先は翌日
    assert _jst(plan[0]["new"]) == "2026-08-19T09:00"


def test_いまより前の本と公開済みは触らない():
    rows = [_row("past", "2026-08-17T09:00"), _row("soon", "2026-08-18T11:30"),
            {"id": "none", "topic": "s-x", "title": "none", "at": None},
            _row("ok", "2026-09-01T09:00")]
    rows.append(_row("ok2", "2026-09-02T09:00"))
    plan = reschedule.compact_plan(rows, now=NOW, max_days=2, lead_min=60,
                                   window=EMPTY)
    # past（過ぎた）・soon（lead の中）・at が無い行は、**動かす対象に入らない**
    assert [p["id"] for p in plan] == ["ok", "ok2"]
    # 08/18 は past と soon が埋めているので、置き先は 08/19 から
    assert _jst(plan[0]["new"]) == "2026-08-19T09:00"
    for p in plan:
        assert p["new"] <= p["old"], p


def test_後ろへ動かす割り当てになったら止まる():
    """`--hour` が遅すぎると、前に詰めるつもりで後ろへ送ります。

    錨が床の日へ移った（2026-09-02）ので、**同じ日の中で**後ろへ送る形にしました
    —— 錨が本の日より前にあると、`--hour` が遅くても前へ動いてしまうためです。
    """
    rows = [_row("v0", "2026-08-18T13:00")]        # 床（12:00）の直後
    with pytest.raises(SystemExit, match="後ろへ動かす"):
        reschedule.compact_plan(rows, now=NOW, hour=20, until_hour=21,
                                max_days=1, window=EMPTY)


def test_目盛りが60の約数でないと止まる():
    with pytest.raises(SystemExit, match="60 の約数"):
        reschedule.compact_plan([_row("v0", "2026-09-01T09:00")], now=NOW,
                                step_min=7, window=EMPTY)


def test_控えは足さずに書き換える(tmp_path, monkeypatch):
    """**足すと `ledger_minutes` が古い時刻も「埋まっている」と読みます。**"""
    from src import config
    path = tmp_path / "data" / "uploaded.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"video_id": "a", "topic": "s-a", "title": "A",
                    "at": "2026-09-01T00:00:00Z", "uploaded_at": "2026-08-17T00:00:00Z"},
                   ensure_ascii=False) + "\n"
        + json.dumps({"video_id": "b", "topic": "s-b", "title": "B",
                      "at": "2026-09-02T00:00:00Z"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)

    assert dupes.retime("a", "2026-08-24T00:30:00Z") is True
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 2                      # **増えていない**
    got = {r["video_id"]: r for r in lines}
    assert got["a"]["at"] == "2026-08-24T00:30:00Z"
    assert got["a"]["uploaded_at"] == "2026-08-17T00:00:00Z"   # 投稿時刻は動かさない
    assert got["b"]["at"] == "2026-09-02T00:00:00Z"
    assert dupes.retime("a", "2026-08-24T00:30:00Z") is False  # 同じなら書かない
    assert dupes.retime("zz", "2026-08-24T00:30:00Z") is False


def test_同じ動画IDが2行あれば両方書き換える(tmp_path, monkeypatch):
    from src import config
    path = tmp_path / "data" / "uploaded.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(
        json.dumps({"video_id": "a", "topic": "s-a", "title": "A", "at": at})
        for at in ("2026-09-01T00:00:00Z", "2026-09-05T00:00:00Z")) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    assert dupes.retime("a", "2026-08-24T00:30:00Z") is True
    ats = {json.loads(x)["at"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}
    assert ats == {"2026-08-24T00:30:00Z"}


# ---------------------------------------------------------------------------
# **真ん中に空く穴**（2026-08-19 12:5x に足した）
#
# `--min-days` は「予約の最後」しか見ません。**全部を詰め切らない**割り当てでは、
# 後ろの何本かが元の時刻に残るので**最後は動かず**、その手前だけが空になります。
# 実物（317本・`--max-days 10`）で **08/30〜09/11 の13日**がこの形でした。
# ---------------------------------------------------------------------------


def _hole_setup(days: int):
    """1日1本 × 12日ぶん。`max_days` を小さくすると詰め切れずに穴が空く。"""
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, step_min=60, hour=9, until_hour=11,
                                   max_days=days, window=EMPTY)
    return rows, plan


def test_詰め切らないと真ん中に穴が空くのを数える():
    rows, plan = _hole_setup(2)          # 置き先は 08/19〜08/20 の 3枠 × 2日
    holes = reschedule.hole_days(rows, plan, NOW)
    assert holes, "穴が空いているのに0件を返した"
    # 最後の本（08/30）は動かないので、その手前が空になる
    assert "08/30" not in holes, "**予約の最後そのもの**を穴に数えている"
    assert "08/22" in holes


def test_全部を詰め切ったときは穴と数えない():
    """後ろがからになるのは**地平線が縮んだ**だけ。`--min-days` が見る側です。"""
    rows, plan = _hole_setup(12)
    assert reschedule.hole_days(rows, plan, NOW) == []


def test_動かすものが無くても連続していれば穴は無い():
    """**「動かさないから穴も無い」ではありません**（下の検査を見ること）。

    ここが見ているのは「連続して埋まっているなら0件」のほうです。
    """
    rows = [_row("v0", "2026-08-19T09:00")]
    assert reschedule.hole_days(rows, [], NOW) == []


def test_もともと空いていた日も穴に数える():
    """**これが落ちていた1件です**（2026-08-19 17:0x）。

    ここは長らく `before - after` を返していました ——
    **「本があったのに、動かしたせいで無くなった日」**しか数えない形です。
    **もともと1本も無い日は `before` に居ないので、永久に映りません。**

    実測: 控え345本の **08/28〜09/03 が0本**（7日連続）なのに、
    既定の `--max-days 4` は `plan` が空 ＝ `before == after` で
    **穴0件で静かに通っていました。**
    """
    rows = [_row("v0", "2026-08-19T09:00"), _row("v1", "2026-08-23T09:00")]
    holes = reschedule.hole_days(rows, [], NOW)      # **1本も動かさない**
    assert holes == ["08/20", "08/21", "08/22"], holes


def test_もともと空いていた日を道具が名指しして詰め方まで出す():
    """**見つけるだけでは、次の回が同じ既定で撃ちます。**

    `suggest_max_days` は `hole_days` の返りを見ているので、
    見えていなければ「いまの `--max-days` で穴は空きません」と答えます。
    """
    rows = [_row(f"v{i}", f"2026-08-{19 + i * 4:02d}T09:00") for i in range(3)]
    assert reschedule.hole_days(rows, [], NOW), "穴があるのに0件"
    hint = reschedule.suggest_max_days(rows, NOW, _Args(1), ceiling=20,
                                       window=EMPTY)
    assert hint is not None, "**詰め方を名指しできていない**"
    plan = reschedule.compact_plan(rows, now=NOW, step_min=60, hour=9, until_hour=11,
                                   max_days=hint, window=EMPTY)
    assert reschedule.hole_days(rows, plan, NOW) == []


def test_今日は穴に数えない():
    """今日の枠は半分が過ぎています（`old <= now` の本は既に公開済み）。

    今日を入れると「今日が0本＝穴」と**毎回鳴ります**。
    """
    rows = [_row("v0", "2026-08-19T09:00"), _row("v1", "2026-08-20T09:00")]
    assert "08/18" not in reschedule.hole_days(rows, [], NOW)   # NOW は 08/18 11:00 JST


def test_予約の最後より後ろの0本の日は穴ではない():
    """12本を1日ぶんに詰めると 08/19 以外は全部 0本。**穴は0件**であること。"""
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, step_min=5, hour=9, until_hour=11,
                                   max_days=1, window=EMPTY)
    assert len(plan) == 11               # 08/19 09:00 の1本だけ動かない
    assert reschedule.hole_days(rows, plan, NOW) == []


class _Args:
    """`suggest_max_days` が読む欄だけ。"""
    step_min = 60
    hour = 9
    until_hour = 11
    lead_min = 60
    min_days = 0.0

    def __init__(self, max_days: int):
        self.max_days = max_days


def test_穴の空かない詰め方を道具の側が名指しする():
    """**増やすと消える**ので、人の直感（減らす）と逆向きです。

    ## 割り当てを組み直さないこと（2026-09-01 に直した。**赤が3回 持ち越された**）

    ここは長らく `suggest_max_days()` の**数だけ**を受け取り、`compact_plan` を
    自分で組み直していました。その数の保証は
    「**探索と同じ引数で組み立てたなら**穴が空かない」であって、数そのものでは
    ありません。探索は `live_edge_min=_live_edge_min(...)` を渡しますが、
    ここは渡していませんでした。

    **2026-08-31 に規則（1日1本）が入るまでは、たまたま同じ形でした** ——
    上限10本のとき `_live_edge_min(9, 60)` は 9:00〜13:00 で、`until_hour=11` と
    枠の数が重なるからです。規則で上限が 1本 になった瞬間、生きる帯は
    **9:00 の1枠**へ縮み、こちらは 3枠/日 のまま。**同じ数で別の割り当てになり、
    赤が出ました**（11時間・3周 持ち越し）。

    直し方は「検査の引数を合わせる」ではありません（次に引数が増えた回に
    また落ちます）。**検証ずみの割り当てを返す口** `suggest_compact()` を足して、
    組み直す道を消しました。
    """
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    hint, plan = reschedule.suggest_compact(rows, NOW, _Args(2), ceiling=20,
                                            window=EMPTY)
    assert hint is not None
    assert reschedule.hole_days(rows, plan, NOW) == []
    # **数だけの口も残しますが、同じ答えであること**（呼び側の逃げ道）
    assert reschedule.suggest_max_days(rows, NOW, _Args(2), ceiling=20,
                                       window=EMPTY) == hint


def test_撃ち切れない回は途中の姿の穴も数えられる():
    """`--max` で切ると、前に詰めた本が抜けた跡が**翌日の窓まで空いたまま**残る。

    穴が0件の割り当てでも、**途中の姿は別に数える**こと。
    """
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, step_min=60, hour=9, until_hour=11,
                                   max_days=12, window=EMPTY)
    assert reschedule.hole_days(rows, plan, NOW) == []      # 撃ち切れば穴は無い
    assert reschedule.hole_days(rows, plan[:3], NOW), "途中で止めた姿の穴を数えていない"


def test_探しはじめる値を指定できる():
    """`start` を渡した回は、**そこから上だけ**を探す（床は下げない）。"""
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    args = _Args(2)
    low = reschedule.suggest_max_days(rows, NOW, args, ceiling=20, window=EMPTY)
    high = reschedule.suggest_max_days(rows, NOW, args, ceiling=20, window=EMPTY, start=low + 1)
    assert low is not None and high is not None
    assert high > low, "start を上げても同じ値が返るなら、探しはじめが効いていない"
    assert args.max_days == 2, "args を書き換えてはいけない"


def test_床から上へしか探さない():
    """穴が空かない値が床より下にあっても、**下げません**。

    `DEFAULT_MAX_DAYS` は判定に要る日数で決めた床で、
    穴を避けるために上げることはあっても、**下げる理由は別の話**です。
    """
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(3)]
    hint = reschedule.suggest_max_days(rows, NOW, _Args(reschedule.DEFAULT_MAX_DAYS),
                                       ceiling=20)
    assert hint is not None
    assert hint >= reschedule.DEFAULT_MAX_DAYS


def test_max_days_の既定は自動():
    """**既定は数字ではありません。** `None` ＝「道具が床から上へ探す」の印。

    ここが 4 に戻っていたら、`_compact` は**穴が残っても止まるだけ**に戻ります
    （名指ししてから撃つまでが2手になり、実測で24周持ち越しました）。
    """
    ns = reschedule.build_parser().parse_args(["--compact"])
    assert ns.max_days is None
    assert reschedule.DEFAULT_MAX_DAYS == 4
    assert reschedule.build_parser().parse_args(
        ["--compact", "--max-days", "9"]).max_days == 9
