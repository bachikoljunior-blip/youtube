# -*- coding: utf-8 -*-
"""**狙いを上げるのは前向きの手、下限を上げるのは遡る手。**（2026-09-05 02:3x・毎時の回）

## この検査が守っているもの —— **この回が実際に踏みました**

尺の狙いを 26〜29分 に上げたとき、`OUTSIDE_CHAPTERS_LO` も 5 → 7 に上げました
（元の註「規則の本文と数える側が別々の数を持つと壊れる」に従ったつもりで）。
**そのとき壊れたのは実物のほうでした**:

    dp.pick_legs('GFvAcxvDmYM')
      LO=5 → ([], None)             ＝ 4脚すべて○ ＝ **処置**
      LO=7 → (['(2) 章・締め'], …)   ＝ **処置ではない**

`GFvAcxvDmYM` は **09/05 09:00 に出る、前提「外の作り方を写した長尺」を
期限（09-07）内に閉じられる唯一の本**です。**下限を上げた瞬間、その本は
「処置ではない」に変わり、前提は期限内に閉じられなくなります。**
その枠は、ショートの 1,049回 を捨てて買ったものでした（`src/slot_cost.py`）。

**＝ 受け取る下限は、走っている判定を遡って壊せます。狙いは壊しません。**
"""
import re

import pytest

from src import daily_pick as dp
from src import script_writer as sw


def test_受け取る幅は規則が命じる狙いを含むこと():
    """**狙いが幅の外に出ていないこと。**

    ここが本当の「本文と数える側の食い違い」です —— 7〜9章 と命じておいて
    上限が 7 だと、命じたとおりに焼いた本が自分の検査で落ちます。
    """
    m = re.search(r"章を\*\*(\d+)〜(\d+)つ\*\*", sw.OUTSIDE_LONG_RULE)
    assert m, "規則の本文に章数の狙いが書かれていません"
    lo, hi = int(m.group(1)), int(m.group(2))
    assert sw.OUTSIDE_CHAPTERS_HI >= hi, (
        f"狙いの上 {hi}章 が、受け取る上限 {sw.OUTSIDE_CHAPTERS_HI} の外です —— "
        "命じたとおりに焼いた本が、焼いた直後に自分の検査で落ちます"
    )
    assert sw.OUTSIDE_CHAPTERS_LO <= lo, (
        f"受け取る下限 {sw.OUTSIDE_CHAPTERS_LO} が狙いの下 {lo}章 より上です"
    )


#: 判定を待っている枠の日（`config/hypotheses.yaml`「外の作り方を写した長尺」・期限 09-07）。
#: **本の ID ではなく日で持ちます** —— 理由は下の docstring。
JUDGED_SLOT_DAY = "2026-09-05"


def _standing_long(day: str = JUDGED_SLOT_DAY) -> tuple[str, str]:
    """その日の枠に**いま立っている**決めが 長尺 なら、その動画ID。`(video_id, なぜ)`。API 0単位。

    **長尺でなければ `("", 理由)`** を返します —— この検査が見ているのは
    「前提『外の作り方を写した長尺』を閉じる本」であって、
    「その日の枠に入っている本」ではありません。枠は形ごと替わることがあります。
    """
    import json
    from pathlib import Path

    rows = []
    f = Path(dp.ROOT) / "data" / "daily_pick.jsonl"
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if str(r.get("for_day")) == day and str(r.get("video_id") or "").strip():
            rows.append(r)
    if not rows:
        return "", f"{day} の決めが `data/daily_pick.jsonl` に在りません"
    last = rows[-1]
    if str(last.get("form")) != "長尺":
        return "", (f"{day} の枠は **{last.get('form')}** へ替わっています"
                    f"（{last.get('at')}・`{last.get('video_id')}`）")
    return str(last["video_id"]), f"{day} の最後の決め（{last.get('at')}）"


def test_下限は走っている判定を遡って壊さないこと():
    """**期限の内側で判定を待っている本が、いまの下限で「処置」のままであること。**

    これが赤くなったら、**下限を戻すこと**（狙いのほうは戻さなくてよい）。
    判定が閉じた後なら、下限を上げてよい —— そのとき遡って外れる本は、
    もう判定に使われていません。

    ## **本の ID を直に書かないこと**（2026-09-05 07:1x に踏んで書き換えた）

    前の版は `dp.treated_probe("GFvAcxvDmYM")` と**ID を直に**書いていました。
    **焼き直しは ID を変えます** —— 実測 09/04 21:31 に
    `e6sLHLmPhrk` → `GFvAcxvDmYM` へ替わっており、規則3（次の枠の1本を出る瞬間まで
    良くし続ける）の下では**替わるのが正常**です。ID を焼き付けると、
    枠の本が良くなった回に、**この検査だけが古い本を見て赤くなります。**

    ## **枠の形が替わった日は、この検査は黙ります**（同じ回に踏んだ）

    2026-09-05 05:37、別の回が門の算（道 ショート ×106 / 長尺 ×334・齢48h の
    中央値 ショート 164回 / 長尺 1回）に従って、**09/05 の枠を ショート へ替えました。**
    そのとき ID だけを引くと、この検査は**ショートの控えを外の長尺の型で測って**
    赤くなります —— 見ている物が変わってしまう形です。

    **この検査が守っているのは「章の下限を上げて、走っている判定を遡って壊すな」**
    の1点だけです。枠が別の形へ行った日は、**その判定はこの枠では閉じません** ——
    下限の話ではないので、`skip` して理由を出します。**赤で隠さないこと。**

    **覆る条件**: 前提「外の作り方を写した長尺」が閉じたら、この検査ごと落とすこと
    （`config/hypotheses.yaml` の `closed_on` を見る）。
    """
    vid, whence = _standing_long()
    if not vid:
        pytest.skip(
            f"{whence} —— 前提『外の作り方を写した長尺』は**この枠では閉じません**。"
            "章の下限の話ではないので、ここは判定しません。"
            "（枠を長尺へ戻すか、前提の期限を動かすかは `config/hypotheses.yaml` の側の判断）")
    state, why = dp.treated_probe(vid)
    assert state == "yes", (
        f"判定を待っている長尺 `{vid}` が『処置』ではありません（{why}）。\n"
        f"  引いた先: {whence}\n"
        f"  いまの門: OUTSIDE_CHAPTERS_LO={sw.OUTSIDE_CHAPTERS_LO} "
        f"HI={sw.OUTSIDE_CHAPTERS_HI}\n"
        "  **下限を上げると、過去に作った本が遡って型から外れます。**\n"
        "  **脚が『尺』なら、下限の話ではありません** —— 台本が"
        "外の帯の切れ目 25分（8,430字）を割っています。焼き直しで直します"
        "（`python -m src.pipeline --topic <題材>`。`--script` では直りません）"
    )
    assert dp.pick_legs(vid) == ([], None)


def test_下限は5のままであること():
    """**覆る条件つきの固定。** 09-07 の判定が閉じるまでは 5。"""
    assert sw.OUTSIDE_CHAPTERS_LO == 5, (
        "`OUTSIDE_CHAPTERS_LO` が 5 から動いています。"
        "上げてよいのは `外の作り方を写した長尺`（期限 09-07）が閉じた後です —— "
        "`config/hypotheses.yaml` の `closed_on` を見てから上げること"
    )


def test_註が理由と覆る条件を持っていること():
    """**次の回が、同じ『揃えたつもり』をやらないこと。**"""
    src = open(sw.__file__, encoding="utf-8").read()
    i = src.index("OUTSIDE_CHAPTERS_LO = ")
    head = src[max(0, i - 2600):i]
    assert "遡" in head, "下限が遡る門であることが書かれていません"
    assert "覆る条件" in head, "覆る条件が書かれていません"
    assert "pick_legs" in head, "踏んだ実物の引き方が書かれていません"


@pytest.mark.parametrize("n", [5, 6, 7, 8, 9])
def test_5から9までは受け取ること(n):
    """既にある本（5〜7章）も、これから作る本（7〜9章）も、どちらも通ること。"""
    assert sw.OUTSIDE_CHAPTERS_LO <= n <= sw.OUTSIDE_CHAPTERS_HI
