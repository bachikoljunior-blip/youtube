"""その日の決めの本の題に `【 】` が在るか（`daily_pick.standing_pick_title`）。

## なぜ要るか（2026-09-05 06:2x）

`script_writer.short_title_problems` は同じ日に立った**作る側**の門で、
これから焼く本の題に `【 】` を要求します。外の帯のショート 132本 の実測で
`【】` が在る本は 1.46回/日・無い本は 0.26回/日 ＝ **×5.52**（n=55対77）。

**ところが、その日の枠へ入るのは「池の private 316本」であることが普通です。**
池の本はもう焼き上がっているので、**作る側の門は1本も通りません** ——
自分のショート **552本 の題に `【】` は 0本**でした。
だから、決めが立った時点で読む側にも言います（`retitle.py` は 50単位・焼き直し無し）。

## この検査がいちばん守っているもの —— **素の帳面を読まないこと**

`data/uploaded.jsonl` は**上げたときの行**で、`scripts/retitle.py` が実物の題を
差し替えても1文字も変わりません。重ねるのは `src/retitles.overlay()` です。

**この関数の最初の版は、そこを踏みました** —— 4分前に自分で `retitle.py` を撃った本に
対して「題に `【 】` が在りません」と言いました。そのまま出していれば、
次の回が同じ本にもう一度 50単位 を払います（09-05 03:4x が 100単位 払ったのと同じ形）。
**下の `test_差し替えずみの本には何も言わないこと` が、その形を固定します。**

**覆る条件**: `niche_ceiling.title_features('short')` の `【】` の倍率が 1.0 を割ったら、
この行ごと落とすこと。`_latest_uploaded()` 自身が差し替えを取り込むようになったら、
この関数の中の重ねは要らなくなります（**先に消さないこと** —— 消す順を間違えると、
また同じ 50単位 を払います）。
"""
import json

import pytest

from src import daily_pick as dp


@pytest.fixture()
def 帳面(tmp_path, monkeypatch):
    """`uploaded.jsonl`（素の題）と `retitled.jsonl`（差し替え後）を別々に作る。"""
    up = tmp_path / "uploaded.jsonl"
    up.write_text(
        json.dumps({"video_id": "AAA", "topic": "s-a", "title": "税額が3.46倍 #Shorts"},
                   ensure_ascii=False) + "\n"
        + json.dumps({"video_id": "BBB", "topic": "s-b", "title": "手取りが22pt下がる #Shorts"},
                     ensure_ascii=False) + "\n"
        + json.dumps({"video_id": "CCC", "topic": "s-c", "title": "【育休】手取りが22pt下がる #Shorts"},
                     ensure_ascii=False) + "\n",
        encoding="utf-8")
    re_ = tmp_path / "retitled.jsonl"
    # **BBB だけ、もう差し替えずみ**（`retitle.py` を撃ったあとの姿）。
    re_.write_text(
        json.dumps({"at": "2026-09-05T06:02:50Z", "video_id": "BBB",
                    "title": "【育休181日目】手取りが22pt下がる #Shorts",
                    "prev": "手取りが22pt下がる #Shorts"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    from src import retitles
    monkeypatch.setattr(retitles, "LEDGER", re_, raising=False)
    return up


def test_題に括弧が無い本には撃つ1行が出ること(帳面):
    lines = dp.standing_pick_title({"form": "ショート", "video_id": "AAA"},
                                   uploaded_path=帳面)
    assert lines, "括弧の無い本で黙ってはいけない"
    assert "【 】" in lines[0]
    assert "×5.52" in lines[0]
    assert "retitle.py AAA" in lines[1]


def test_差し替えずみの本には何も言わないこと(帳面):
    """**素の帳面を読むと、ここが落ちます。**
    `uploaded.jsonl` の BBB は括弧なし・`retitled.jsonl` の BBB は括弧あり。
    重ねずに読むと「無い」と言い、次の回が **もう一度 50単位** を払います。"""
    assert dp.standing_pick_title({"form": "ショート", "video_id": "BBB"},
                                  uploaded_path=帳面) == []


def test_はじめから括弧が在る本には何も言わないこと(帳面):
    assert dp.standing_pick_title({"form": "ショート", "video_id": "CCC"},
                                  uploaded_path=帳面) == []


@pytest.mark.parametrize("cur", [
    None,
    {},
    {"form": "長尺", "video_id": "AAA"},          # 形をまたいで写さない（疑問形は符号が逆）
    {"form": "ショート"},                          # 池の本ではない（これから作る）
    {"form": "ショート", "video_id": "知らないID"},  # 帳面に無い
])
def test_言えない回は黙ること(cur, 帳面):
    """**推測で 50単位 を撃たせないこと。**"""
    assert dp.standing_pick_title(cur, uploaded_path=帳面) == []


def test_その日の決めの画面から呼ばれていること():
    """**測るだけでは1本も変わりません。** `[きょうの1本]` の本文を組む所から
    呼ばれていること自体を固定します（`standing_pick_treatment` の隣）。"""
    import inspect
    src = inspect.getsource(dp.lines) if hasattr(dp, "lines") else ""
    if "standing_pick_title" not in src:
        src = inspect.getsource(dp)
        # 呼び出しが1つも無ければ、この行は誰にも届きません。
        assert src.count("standing_pick_title(") >= 2, "定義だけで、呼び手がありません"
