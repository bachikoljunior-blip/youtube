"""**ショートの上限に、長尺を混ぜないこと。**（2026-08-26 に足した）

`src/day_cap.py` の冒頭は最初から「**長尺は最初から0なので除く**」と書いて
いましたが、**除いていませんでした。** `_readings` は `data/views.jsonl` を
丸ごと読み、`measure` は 0再生 の本を **`n_dead`（＝上限の証拠）**として
数えます。つまり長尺は、除かれるどころか**上限を押し下げる側**に居ました。

実物（2026-08-21）では、死んだ22本のうち **5本が長尺**でした。
そのときは `n_alive` が動かないので `cap` は 10本 のままでしたが、
**無害だったのは偶然**です —— ショートが全部生きた日に長尺が1本混ざれば、
その日が「崩れた日」に化けて上限を1本ぶん下げます。
"""
from __future__ import annotations

import datetime as dt
import json

from src import day_cap


def _views(tmp_path, rows):
    p = tmp_path / "views.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _forms(tmp_path, mapping):
    p = tmp_path / "video_forms.json"
    p.write_text(json.dumps({"forms": mapping}), encoding="utf-8")
    return p


def _row(vid, hour, views, day="2026-08-21"):
    """公開 day の hour 時（JST）に出して、6時間後に views 再生。"""
    pub = dt.datetime.fromisoformat(f"{day}T{hour:02d}:00:00+09:00")
    at = (pub + dt.timedelta(hours=6)).astimezone(dt.timezone.utc)
    return {"id": vid, "at": at.isoformat().replace("+00:00", "Z"),
            "hours": 6.0, "views": views}


def test_長尺は既定で外れる(tmp_path):
    v = _views(tmp_path, [_row("s1", 9, 900), _row("s2", 10, 800),
                          _row("s3", 11, 700), _row("L1", 12, 0)])
    f = _forms(tmp_path, {"s1": "ショート", "s2": "ショート",
                          "s3": "ショート", "L1": "長尺"})
    days = day_cap.by_day(v, f)
    ids = {vid for rows in days.values() for vid, _, _ in rows}
    assert "L1" not in ids, "長尺がショートの母集団に残っています"
    assert ids == {"s1", "s2", "s3"}

    both = day_cap.by_day(v, f, include_long=True)
    ids2 = {vid for rows in both.values() for vid, _, _ in rows}
    assert "L1" in ids2, "include_long=True で比べられなくなっています"


def test_長尺1本でショートの上限が下がっていた(tmp_path):
    """**ここが本体。** ショートが全部生きた日に長尺を1本足すと、
    混ぜたままでは「崩れた日」に化けて上限が下がります。"""
    shorts = [_row(f"s{i}", 9 + i, 900) for i in range(4)]
    f = _forms(tmp_path, {f"s{i}": "ショート" for i in range(4)} | {"L1": "長尺"})

    clean = day_cap.measure(_views(tmp_path, shorts), f)
    mixed_path = _views(tmp_path, shorts + [_row("L1", 13, 0)])
    mixed_now = day_cap.measure(mixed_path, f)
    mixed_old = day_cap.measure(mixed_path, f, include_long=True)

    # 長尺を混ぜた「昔の数え方」は、崩れたことにして上限を 4本 で止める
    assert mixed_old["measured"] is True
    assert mixed_old["cap"] == 4
    # 外せば、崩れは観測されていない（＝既定値のまま・上限は未確定）
    assert mixed_now["measured"] is False
    assert mixed_now == clean, "長尺を外した結果が、最初から無い場合と一致しません"


def test_実物で08_21の証拠から長尺5本が抜けている():
    """`data/views.jsonl` と `data/video_forms.json` の実物。

    2026-08-21 は 32本 の読みがあり、うち **5本が長尺**。
    ショートだけで数えると 27本 になります。
    """
    longs = day_cap._long_ids()
    if not longs:
        return                                   # 形の控えが無い環境では飛ばす
    day = dt.date(2026, 8, 21)
    only_short = day_cap.by_day().get(day) or []
    with_long = day_cap.by_day(include_long=True).get(day) or []
    if not with_long:
        return                                   # その日の読みが無ければ飛ばす
    mixed_in = [v for v, _, _ in with_long if v in longs]
    assert mixed_in, "08/21 の実物に長尺が混ざっていません（前提が変わりました）"
    assert len(only_short) == len(with_long) - len(mixed_in)


def test_長尺の上限は崩れを見てからしか言わない():
    """**「測った」に化けないこと。** 崩れを観測して初めて上限が言えます。

    2026-08-26 に**言い方だけ**変えました。守っているものは同じです ——
    もとは「未測定」の4文字と「6時間の読みでは判定できない」の2つを見ていました。
    **6時間 で読むのをやめた**ので（`LONG_MIN_AGE_H`・齢48時間）、
    後者はもう本文に出ません。**代わりに、齢を間違えると何が起きるかを見ます。**

    ## 2026-08-27 に、**値ではなく不変量**へ書き直しました

    ここは `measured is False` と `collapsed is False` を**直に**見ていました。
    **それは「まだ崩れていない」という、その日の実測の写しです。**
    実際に崩れた日（`most=7` / `alive=5`）に、この試験は赤くなりました ——
    **機械は正しく、試験だけが古い値を握っていた**わけです。

    見るべきは「崩れを見ずに measured を名乗らないこと」と
    「**印字が `collapsed` と食い違わないこと**」の2つです。
    実際、`long_form_lines()` は崩れた日にも
    「**7本/日 までは崩れていません**（最大の日 **5/7本** が生存）」と
    印字していました（同じ行で自分を否定している）。**そこも直しました。**
    """
    m = day_cap.long_form()
    assert m["measured"] is m["collapsed"], (
        "`measured` は「崩れを観測したか」そのものです（`long_form()` の返りの註）"
    )
    text = "\n".join(day_cap.long_form_lines())
    if m["collapsed"]:
        assert "崩れました" in text, "崩れているのに、印字がそう言っていません"
        assert "までは崩れていません" not in text, (
            "崩れた日に「崩れていません」と印字しています（同じ行が自分を否定します）"
        )
        # 機構（`batch_build._long_ring()`）は `most - 1` へ落とします。
        # **印字もその数を出すこと** —— ここが割れると、読む側と置く側が別を見ます
        assert f"{max(1, m['most'] - 1)}本/日" in text
    else:
        assert "上限そのものはまだ出ていません" in text
    # **齢を間違えると長尺は全部 死んで見える**、という註が消えないこと
    assert "6時間の読みで数えないこと" in text


def test_長尺は齢をそろえて数える():
    """**6時間 で数えると、長尺は何本 出しても『ほぼ全部 死んだ』に見えます。**

    実測（2026-08-21・長尺を5本 出した唯一の日）: 齢 6時間 で 1/5本、
    24時間 で 5/5本。**崩れではなく、読みが早すぎただけ**でした。
    """
    assert day_cap.LONG_MIN_AGE_H >= 24.0, "長尺を 24時間 未満で数えないこと"
    late = day_cap.long_form()
    early = day_cap.long_form(min_age_h=6.0)
    if not late["per_day"] or late["most"] < 2:
        return                                   # 実物が無い環境では飛ばす
    assert late["alive"] >= early["alive"], (
        "齢を延ばしたのに生存が減っています（読みの採り方が壊れています）")


def test_ショートの面は齢を変えても動かない():
    """**ずれるのは長尺だけ**、という切り分けの担保（2026-08-26 の実測）。"""
    if not day_cap.measure()["measured"]:
        return
    assert day_cap.measure()["cap"] == day_cap.cap()


def test_上限の行がショートの面だと名乗る():
    text = "\n".join(day_cap.lines())
    assert "ショートの面" in text, "何の面の上限かが出ていません"
