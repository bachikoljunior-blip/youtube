"""`eta.headline()` / `eta.solve()` —— **免除は、それを計算した腕のものか。**

## なぜ要るか（2026-09-05 05:xx JST・最適化の回に実物で数えた）

`plan()` は「名指しした腕の測定は、もう予約済みの本が答える」という**免除**を
`lever_hint_covered` に積みます。出どころは `blocking["sample"]` ＝
`long_sample_forecast()` ＝ **長尺の1本あたり再生の標本が n≥`LONG_SAMPLE_MIN` に
届く日**で、書く条件も `lever_hint == "per_video"` です。**`per_video` の免除**です。

ところが `solve()` は、そのあとで `gate_arm_pick()` を通し、到達日が出ない回は
`lever_hint` を**門1'（登録者）の腕 ＝ `sub_rate` へ書き換え**ます。
画面も台帳も `pl["lever_hint"]` を読むので、`per_video` の免除が
**`sub_rate` の名前で**刷られていました::

    ### **その `sub_rate` の測定は、予約済みの本が 2026-09-06 に答えます**
        → **この回は別の腕を引くこと。**

**実測 `data/runs.jsonl`（2026-09-05 05:xx）: ship 239件 中 90件（38%）**が
`lever_hint="sub_rate"` かつ `lever_hint_covered` 付きで出ています。
その 90件 が引いた腕は `per_video` 69 ／ `none` 12 ／ **`sub_rate` は 7件**。
`moves` が 0 以外は **3件**。そして `lever_followed=False` が **83件** ——
**画面の指示どおりに別の腕を引いた回が、名指しを外したとして採点されていました。**

同じ回の `eta.py` 自身の数では、門1' は据え置き **512日**、`sub_rate` を天井
（×6.22）まで引けば **83日**、`per_video`（×4.54）で **113日**。
**いちばん大きい腕から回を追い出す1行**でした。さらに `scripts/ab_slots.py` の
実測では `subs_badge` の A/B は**両群とも「まだ1本も予約に在りません」** ＝
その日に答える本は **0本**で、免除の中身も空でした。

`resume_gate` の側（名指しを `gate` に倒す口）は 2026-08-26 から
`lever_hint_covered` を落としています。**`gate_arm_pick()` の側に無かった**のが
この漏れです。

## ここで固定するもの

1. 免除には**腕の名前**が付く（`lever_hint_covered_arm`）
2. 名指しがその腕から離れたら、免除は落ちる（`solve()`）
3. 刷る側も名前を見る（`headline()`）—— 名指しを書き換える口が3つめに増えても、
   黙って通らない
4. 台帳（`data/eta.jsonl`）にも腕の名前が積まれる ——
   次の回が「どの腕の免除か」を見分けられるように

## 覆る条件

`blocking["sample"]` が腕ごとに出るようになったら（＝ `sub_rate` 側にも
「予約済みの本で埋まる日」が立ったら）、`plan()` の `per_video` のべた書きを
やめて、その腕の名前を入れること。この検査はそのまま生きます。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "eta_covered_arm_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

_LINE = "の測定は、予約済みの本が"


def _pl(**kw) -> dict:
    pl = {
        "binding": "再生数が天井に当たっている",
        "lever_hint": "per_video",
        "lever_hint_covered": "2026-09-06",
        "lever_hint_covered_arm": "per_video",
        "target_date": None,
        "days_to_target": eta.NEVER,
        "lever_days": [],
    }
    pl.update(kw)
    return pl


def _head(pl) -> str:
    return "\n".join(eta.headline(pl, None, None, []))


def test_腕が合っていれば免除はそのまま刷られる():
    out = _head(_pl())
    assert _LINE in out, "`per_video` 自身の免除まで消してはいけない"
    assert "`per_video` の測定は" in out


def test_名指しが別の腕なら免除は刷られない():
    """**この回のいちばんの中身。** 90件 が踏んだ形をそのまま置く。"""
    out = _head(_pl(lever_hint="sub_rate"))
    assert _LINE not in out, (
        "`per_video` の免除が `sub_rate` の名前で刷られている。"
        "ship 239件 中 90件 がこれを読んで、いちばん大きい腕から降りた")
    assert "`sub_rate` の測定は" not in out


def test_腕の名前が無い古い行は今までどおり刷る():
    """**過去の `data/eta.jsonl` を黙らせないこと。** 腕の欄は
    2026-09-05 に足したので、それより前の行には在りません。
    無い行は「名指しのもの」と読む（＝ 今までと同じ）。"""
    pl = _pl()
    pl.pop("lever_hint_covered_arm")
    assert _LINE in _head(pl)


def test_solve_は名指しを門1へ倒したときに免除を落とす():
    src = (ROOT / "scripts" / "eta.py").read_text()
    i = src.index('pl["lever_from"] = "門1\'"')
    tail = src[i:i + 900]
    assert 'lever_hint_covered_arm' in tail and 'pop("lever_hint_covered"' in tail, (
        "`gate_arm_pick()` の書き換えが、免除を落とさなくなった。"
        "落とさないと `per_video` の免除が `sub_rate` の名前で出る")


def test_台帳に腕の名前が積まれる():
    src = (ROOT / "scripts" / "eta.py").read_text()
    assert 'row["lever_hint_covered_arm"]' in src, (
        "`data/eta.jsonl` に腕の名前が積まれない。"
        "積まないと、次の回はどの腕の免除か見分けられない")
