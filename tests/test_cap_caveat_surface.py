"""**「この腕は死んでいる」を、面を1つしか見ずに印字しないこと。**（2026-08-28）

## 何を守っているか

`scripts/eta.py` の `physical_caps` は `density` の天井を **2つ**立てます:

    density       ショートの面   ×1.00      実測      **天井**
    density_long  長尺の面       ×128       未測定    **開いている**

`density_long` を `LEVERS` に入れないのは**正しい**（未測定の天井で軌跡を
歩かせると 08/21 の実害。`physical_caps` の註）。壊れていたのは**印字**のほうで、
`cap_lines` と `alloc_search` はショートの面の ×1.00 だけを見て、

    **この腕は天井 ×1.00（引き代なし）です。**立てても、閉じても、上の日付は1日も動きません

と出していました。実測 2026-08-28、台帳の**開いている density の前提 6件**のうち
**2件は長尺の面**（「長尺は1日4本 作れる」／「長尺の生成が落ちる主因は…」）で、
**4,000時間の門に入るのは長尺だけ**です。さらに 3件は `day_cap` の上限そのものを
測る前提で、同じ回に `caps["density"]["confounded"] = True` が立っています ——
**×1.00 を作っている当の数を、いま測っている最中**でした。

## 覆る条件

`physical_caps` が面ごとに腕を立て、`LEVERS` に長尺の面が入ったら、
この検査ごと外してよい（軌跡が面を歩くので、印字は自動で正しくなる）。
`day_cap.window()` の切り分けが済んだら、2件目の理由は**自動で**消えます ——
そのとき ①③ は緑のままです。**手で消さないこと。**
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.eta as E  # noqa: E402

BARE = "立てても、閉じても、上の日付は1日も動きません"
#: `cap_lines` 側の言い切り。**否定形（「…とは言えません」）と
#: 取り違えないよう、頭から当てます。**
BARE_MARK = "**引き代なし。この腕に立てても"


def _arm(cap=1.0, **kw):
    a = {"cap": cap, "cap_why": "テスト", "cap_measured": True}
    a.update(kw)
    return a


# --- ① 面が割れていない腕は、いままでどおり「引き代なし」と言い切る -------------
#     **この検査がいちばん大事です。** 註を足しただけで警告が全部 消えるなら、
#     直したのではなく黙らせただけになります。
def test_面が1つしかない腕は裸の引き代なしを出す():
    lines = E.cap_lines({"density": _arm()})
    assert any(BARE_MARK in ln for ln in lines), lines
    assert E.cap_caveats("density", _arm()) == []


# --- ② 別の面が開いていたら、裸の「動きません」を出さない ---------------------
def test_別の面が開いていたら裸の動きませんを出さない():
    a = _arm(cap_surface="ショート",
             cap_surfaces=[{"key": "density_long", "surface": "長尺",
                            "factor": 128.1, "measured": False,
                            "at_ceiling": False, "why": "口が通す 92本/日 から…"}])
    caveats = E.cap_caveats("density", a)
    assert len(caveats) == 1, caveats
    assert "長尺" in caveats[0] and "128" in caveats[0]
    assert "未測定" in caveats[0]

    lines = E.cap_lines({"density": a})
    body = "\n".join(lines)
    assert BARE not in body, body
    assert BARE_MARK not in body, body
    assert "長尺" in body, body


# --- ③ 別の面も天井なら、割れていても「引き代なし」に戻る ---------------------
#     **面が在ること自体は理由になりません。** 開いている面が理由です。
def test_別の面も天井なら引き代なしに戻る():
    a = _arm(cap_surface="ショート",
             cap_surfaces=[{"key": "density_long", "surface": "長尺",
                            "factor": 1.0, "measured": True,
                            "at_ceiling": True, "why": "…"}])
    assert E.cap_caveats("density", a) == []
    assert any(BARE_MARK in ln for ln in E.cap_lines({"density": a}))


# --- ④ 天井そのものが未決着なら、それも理由になる -----------------------------
def test_天井が未決着なら理由になる():
    a = _arm(cap_confounded=True, cap_answer_on="2026-09-03")
    caveats = E.cap_caveats("density", a)
    assert len(caveats) == 1, caveats
    assert "決着" in caveats[0] and "2026-09-03" in caveats[0]
    assert BARE not in "\n".join(E.cap_lines({"density": a}))


# --- ⑤ 天井が 1.0 を超える腕には、何も足さない -------------------------------
def test_引き代のある腕には何も足さない():
    a = _arm(cap=6.5, cap_confounded=True)
    lines = E.cap_lines({"density": a})
    assert not any("[!]" in ln for ln in lines), lines


# --- ⑥ `_capped_arms` が、面の割れを実際に運んでいること ----------------------
#     **ここが切れると、上の全部が空振りします**（`cap_surfaces` が誰にも付かない）。
def test_capped_arms_が面の割れを運ぶ(monkeypatch):
    phys = {
        "density": {"factor": 1.0, "why": "ショートの面", "measured": True,
                    "surface": "ショート", "at_ceiling": True,
                    "confounded": True, "answer_on": "2026-09-03"},
        "density_long": {"factor": 128.1, "why": "長尺の面", "measured": False,
                         "surface": "長尺", "at_ceiling": False},
    }
    monkeypatch.setattr(E, "physical_caps", lambda *a, **k: phys)
    out = E._capped_arms({}, arms={"density": {"cap": None}})
    a = out["density"]
    assert a["cap"] == 1.0
    assert a["cap_surface"] == "ショート"
    assert [s["surface"] for s in a["cap_surfaces"]] == ["長尺"]
    assert a["cap_confounded"] is True
    assert a["cap_answer_on"] == "2026-09-03"
    assert BARE not in "\n".join(E.cap_lines(out))


# --- ⑦ 判断の正本は1か所であること ------------------------------------------
#     この repo がいちばん多く踏んでいるのは
#     「同じことを2か所が別々に言っていて、片方しか読まれていない」形です
#     （`CLAUDE.md`）。**この欠陥そのものが、その形でした。**
@pytest.mark.parametrize("fn", ["cap_lines", "alloc_search"])
def test_両方の印字が同じ判定器を呼ぶ(fn):
    import inspect
    src = inspect.getsource(getattr(E, fn))
    assert "cap_caveats(" in src, f"{fn} が `cap_caveats` を呼んでいません"


def test_面の対応表に長尺が入っている():
    assert E._SURFACE_SIBLINGS.get("density") == ("density_long",)
    # **軌跡には渡さないこと**（未測定の天井で歩かせない・08/21 の実害）。
    assert "density_long" not in E.LEVERS
