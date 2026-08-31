"""**`--alloc` の名指しを、台帳が打ち消していないか**（2026-08-29 に足した）。

`eta.py --alloc` は 2026-08-27 から **5回 続けて `sub_rate`** を名指しし、
**5回とも回の側が手で打ち消しています。** 打ち消す根拠は台帳の
`next_if_false`（「`--alloc` が名指ししていても、次の1件はそこに立てないこと」）で、
**機械が読める所に、機械が読める字で書いてあります。**
読まないので、毎回 人が思い出していました。

**道具が言わないものは、毎回 人が思い出すことになります。**
"""
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import arm_speed  # noqa: E402


DOC = {
    "hypotheses": [
        {"claim": "ホームに紹介動画を置くと登録率が上がる",
         "lever": "sub_rate", "deadline": "2026-09-09",
         "next_if_false": ["`--alloc` が `sub_rate` を名指ししていても、"
                           "**次の1件はそこに立てないこと**"]},
        {"claim": "何も言っていない前提", "lever": "rpm", "deadline": "2026-09-30",
         "next_if_false": ["別の帯を試す"]},
    ],
    "confirmed": [
        {"claim": "閉じた前提", "lever": "density", "confirmed_on": "2026-08-05",
         "effect": 1.0, "next_done": ["この腕には立てないこと（実測で天井 ×1.00）"]},
    ],
}


def test_腕べつに拾う():
    bans = arm_speed.standing_bans(DOC)
    assert set(bans) == {"sub_rate", "density"}, bans
    assert bans["sub_rate"][0]["open"] is True
    assert bans["density"][0]["open"] is False


def test_言っていない腕は空():
    assert arm_speed.ban_lines("rpm", DOC) == []


def test_印字は状態と本文の両方を出す():
    """**「立てるな」だけを出さないこと。** 開いている前提の `next_if_false` は
    条件つきなので、そのまま従わせると**判定の前に腕を捨てます**。"""
    lines = arm_speed.ban_lines("sub_rate", DOC)
    joined = "\n".join(lines)
    assert "まだ開いています" in joined, joined
    assert "2026-09-09" in joined, joined
    assert "次の1件はそこに立てないこと" in joined, joined
    assert "条件つき" in joined, "条件つきであることを言っていません"


def test_実物の台帳でも落ちない():
    """**この検査は「1件も無い」を許します。** 台帳から消えたら
    `standing_bans` は毎回 空を返す（＝ 費用だけ）ので、
    そのときは呼び出し側ごと外すこと —— `standing_bans` の「覆る条件」。"""
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    bans = arm_speed.standing_bans(doc)
    assert isinstance(bans, dict)
    for lever, rows in bans.items():
        assert lever in arm_speed.ARMS, f"腕の名前が台帳の外です: {lever}"
        for r in rows:
            assert r["line"], r
