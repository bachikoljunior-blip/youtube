"""**規則で固定された腕を、「面が開いているから」で生き返らせないこと。**

## なぜ要るか（2026-08-31・最適化の回。**この回に自分で撃った数**）

`data/eta.jsonl` の最後の天井の行は、こうでした:

    arm_caps    {'per_video': 2.01, 'sub_rate': 6.64, 'rpm': 59.77, 'density': 1.00}
    dead        ('per_video', 'sub_rate', 'rpm')      ← **動かせる腕が全部 死んでいる**
    open_why    {'density': '…長尺の面は開いています…'} ← **`density` だけが生きている**

門1（登録者1,000人）を腕ごとに解き直すと（`house_rule.cap()` を掛けて）:

    いま                      3,292日
    per_video を天井 ×2.01     1,640日   （**−1,652日**）
    sub_rate  を天井 ×6.64       495日   （**−2,797日**）
    density   を天井 ×1.00     3,292日   （**    0日**）
    density   を **無限大**    3,292日   （**    0日**）  ← 規則が頭を押さえる

**`density` は無限大にしても到達日を1日も動かしません。**
それでもこの機械は、`density` を**唯一の生きた腕**として差し出していました
（直近10回の ship の腕は `density` 3回・過去の配分の 39%）。

## 直したのは「面の話」ではありません

2026-08-26〜27 に入った救済（`_long_surface_open`）は、当時**正しい**ものでした ——
天井が `day_cap.cap()` ＝ **観測**で、観測は測り直せば動くからです。
**2026-08-31 に、その上に規則が乗りました**（`src/house_rule.PUBLISH_PER_DAY = 1`・
「覆る条件: **ありません**」）。規則は測り直しても動きません。

**長尺の面が開いている、という事実は正しいままです。** 変わったのは
**その事実がどの腕を指すか** —— 1日の本数は固定なので、自由なのは
**その1本がどの形か**のほうで、それは `rpm` です。だから救済の中身は
捨てずに `rpm` へ**付け替え**ます（`redirect_why`）。

## 覆る条件

**オーナーが自分の言葉で 1日1本 を外したとき。** そのとき
`house_rule.PUBLISH_PER_DAY` が上がり、`scripts/eta.physical_caps` の
`rule_binds` が自然に False になって、この検査は 08/26 の姿へ戻ります。
**手で消さないこと。**
"""
from __future__ import annotations

from src import levers

#: 長尺の面は開いていて、ショートの面は規則で固定 —— **実データと同じ形**。
RULE_PINNED = {"short": {"at_ceiling": True, "measured": True, "rule_binds": True},
               "long": {"at_ceiling": False, "measured": True}}
#: 同じ形だが、天井が**観測**のとき（2026-08-30 までの姿）。
OBSERVED = {"short": {"at_ceiling": True, "measured": True, "rule_binds": False},
            "long": {"at_ceiling": False, "measured": True}}


def _row(surfaces: dict | None) -> dict:
    row = {"arm_caps": {"per_video": 2.01, "sub_rate": 6.64,
                        "rpm": 59.77, "density": 1.0},
           "arm_reaches": {"per_video": False, "sub_rate": False,
                           "rpm": False, "density": False},
           "lever_hint": "rpm"}
    if surfaces is not None:
        row["density_surfaces"] = surfaces
    return row


def test_規則が天井なら面が開いていても死んだ腕のまま():
    st = levers.arm_state(_row(RULE_PINNED))
    assert "density" in st["dead"], (
        "規則で 1日1本 に固定された腕が、面が開いているだけで生きています"
        f"（dead={st['dead']}）")
    assert st["dead_why"]["density"].startswith(levers.RULE_DEAD)
    assert not st["open_why"], (
        "規則で死んだ腕に「面が割れているから引ける」を付けています: "
        + repr(st["open_why"]))


def test_理由に天井と書かないこと():
    """**「天井」と書くと「測り直せば上がる」と読まれます。**

    そう読んだ回は「天井を上げる前提を1件 立てよう」に向かい、
    **オーナーが外すまで永久に閉じない前提**を台帳に積みます
    （`src/house_rule.unreachable_needs` が数えているのと同じ形）。
    """
    st = levers.arm_state(_row(RULE_PINNED))
    why = st["dead_why"]["density"]
    assert "house_rule" in why, why
    assert "覆る条件はありません" in why, why


def test_長尺の面の話は捨てずに_rpm_へ付け替える():
    """**中身は正しいままです。指す先だけが変わりました。**"""
    st = levers.arm_state(_row(RULE_PINNED))
    note = (st.get("redirect_why") or {}).get("rpm")
    assert note, "長尺の面の話ごと消しています（`none` へ落ちる回が戻ります）"
    assert "4,000時間の門に入るのは長尺だけ" in note
    assert "`none` へ落とさないこと" in note
    assert "`rpm`" in note


def test_密度を選んだ回に_無限大でも動かないと出る():
    st = levers.arm_state(_row(RULE_PINNED))
    text = "\n".join(levers.lever_notes("density", st))
    assert "無限大にしても到達日は1日も動きません" in text, text
    assert "天井に着いています" not in text, "規則を天井と同じ字で叱っています"
    assert "天井を上げる前提を立てないこと" in text


def test_rpm_を選んだ回にも長尺の仕事の行き先が出る():
    """**`rpm` の側に出さないと、長尺の仕事が担当なしになります。**"""
    st = levers.arm_state(_row(RULE_PINNED))
    text = "\n".join(levers.lever_notes("rpm", st))
    assert "4,000時間の門に入るのは長尺だけ" in text, text


def test_天井が観測のときは_08_26_の救済がそのまま生きる():
    """**全部を殺す変更ではありません。** 観測は測り直せば動きます。"""
    st = levers.arm_state(_row(OBSERVED))
    assert "density" not in st["dead"], (
        "観測の天井まで規則あつかいにしています（08/26 の救済が消えます）")
    assert "長尺の面は開いています" in st["open_why"]["density"]
    assert not st.get("redirect_why")


def test_欄が無い古い行は前のまま():
    """**済んだ回の判定を、あとから足した欄で塗り替えないこと。**

    ここを「規則」に倒すと `drift.dead_arm_report` の
    「到達日を動かせない腕を選んだ回」がさかのぼって書き換わります。
    新しい行は毎回この欄を持つので、次の `eta.py` で入ります。
    """
    surfaces = {"short": {"at_ceiling": True, "measured": True},
                "long": {"at_ceiling": False, "measured": True}}
    st = levers.arm_state(_row(surfaces))
    assert "density" not in st["dead"]
    assert not st.get("redirect_why")


def test_ほかの腕を巻き込まない():
    st = levers.arm_state(_row(RULE_PINNED))
    assert st["dead_why"].get("sub_rate") == "天井まで引いても届かない"
    assert st["dead_why"].get("per_video") == "天井まで引いても届かない"
