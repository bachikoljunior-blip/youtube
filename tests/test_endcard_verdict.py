"""`src/endcard_verdict.py` の検査。

**先に「既知の当たり」を1件固定してあります**（`docs/trigger_main.md` §4）——
実データから人が目で拾った、問いかけの形の読み上げ。道具がこれを外したら、
件数がいくら出ていても意味がありません。
"""
from __future__ import annotations

import json

import pytest

from src import endcard_verdict as ev


# --- 既知の当たり（実データから目で拾った1件） -----------------------------

def test_既知の当たり_問いかけの行を問いかけと読む():
    # data/critique_queue/-15HcNgcv6M.json の narration[-1]（2026-08-17 投稿）
    assert ev.is_ask(["前提は再就職手当の給付率です。",
                      "あなたの所定給付日数は、何日ですか。"])


def test_既知の当たり_後ろに文が続く問いかけも読む():
    # 文末は「ください。」で、疑問の印は行の途中にある。**文末で見ると外す。**
    assert ev.is_ask(["率と額、どちらで見ていましたか。コメントで教えてください。"])
    assert ev.is_ask(["あなたの治療、月をまたぐ予定になっていませんか。"])


def test_問いかけでない行は問いかけと読まない():
    assert not ev.is_ask(["前提は再就職手当の給付率です。残日数が3分の1未満ならゼロ。"])
    assert not ev.is_ask([])


# --- 母集団 -----------------------------------------------------------------

def _ledger():
    return [
        {"video_id": "a1", "topic": "t1", "title": "年金の話 #Shorts"},
        {"video_id": "a2", "topic": "t2", "title": "医療費の話 #Shorts"},
        {"video_id": "a3", "topic": "t3", "title": "長尺の解説"},        # 長尺
        {"video_id": "a4", "topic": "t4", "title": "控えの無い本 #Shorts"},
        {"video_id": "a1", "topic": "t1", "title": "年金の話 #Shorts"},  # 重複
    ]


def _queue(tmp_path, bodies: dict[str, list[str]]):
    for vid, nar in bodies.items():
        (tmp_path / f"{vid}.json").write_text(
            json.dumps({"video_id": vid, "narration": nar}, ensure_ascii=False),
            encoding="utf-8")
    return tmp_path


def test_母集団はショートの問いかけ型だけ(tmp_path):
    q = _queue(tmp_path, {"a1": ["あなたは何歳ですか。"],
                          "a2": ["ここまでが前提です。"],
                          "a3": ["長尺のおしまいですか。"]})
    ask, breakdown = ev.population(_ledger(), q)
    assert ask == ["a1"]
    assert breakdown == {"ask": 1, "not_ask": 1, "no_narration": 0,
                         "no_queue": 1, "long": 1}


def test_控えが無い本を問いかけでない側に数えない(tmp_path):
    # 分母が実際より大きく見えると、反証条件が甘くなります。
    q = _queue(tmp_path, {"a1": ["何円ですか。"]})
    _, breakdown = ev.population(_ledger(), q)
    assert breakdown["not_ask"] == 0
    assert breakdown["no_queue"] == 2   # a2 と a4


def test_読み上げが空の本も問いかけでない側に数えない(tmp_path):
    q = _queue(tmp_path, {"a1": ["何円ですか。"], "a2": []})
    _, breakdown = ev.population(_ledger(), q)
    assert breakdown["not_ask"] == 0
    assert breakdown["no_narration"] == 1


def test_同じ動画IDを二度数えない(tmp_path):
    q = _queue(tmp_path, {"a1": ["何円ですか。"], "a2": ["何円ですか。"]})
    ask, _ = ev.population(_ledger(), q)
    assert ask == ["a1", "a2"]


# --- 反証条件 ---------------------------------------------------------------

def test_再生が足りないうちは判定しない():
    v = ev.verdict(views=1999, comments=0, shares=0)
    assert v["state"] == "not_yet"


def test_再生が届いてコメントが2件未満なら外れ():
    v = ev.verdict(views=2000, comments=1, shares=9)
    assert v["state"] == "falsified"
    assert "外れ" in v["line"]


def test_再生が届いてコメントが2件以上なら保つ():
    v = ev.verdict(views=2000, comments=2, shares=0)
    assert v["state"] == "held"


def test_共有は判定に入れない():
    # `falsified_if` が名指しているのはコメントだけ。共有は claim の本文にしかない。
    assert ev.verdict(2000, 0, 999)["state"] == "falsified"
    assert ev.verdict(2000, 2, 0)["state"] == "held"


@pytest.mark.parametrize("views,comments,state", [
    (0, 0, "not_yet"), (1999, 5, "not_yet"),
    (2000, 0, "falsified"), (20000, 1, "falsified"),
    (2000, 2, "held"), (2000, 40, "held"),
])
def test_境目(views, comments, state):
    assert ev.verdict(views, comments, 0)["state"] == state


# --- 実データ（型が分かれた。**次はどう分かれているかを固定する**） -----------

def test_実データ_問いかけでない本は全部_依頼の型():
    """**この検査は 2026-08-26 夕に鳴りました。書き換えた記録を残します。**

    元の形は `assert breakdown["not_ask"] == 0` で、docstring はこう言っていました
    ——「**緑でなくなったら、それは進歩です** —— 対照群ができたということ」。
    **そのとおりに鳴りました**（`not_ask` が 0 → 5）。

    **ただし「対照群」ではありませんでした。処置群のほうです。**
    出てきた5本は全部これです:

        「雑損控除の境目を毎日出します。登録して次の数字をどうぞ。」
        「介護の限度額の計算を毎日出すので登録してください」

    ＝ `config/hypotheses.yaml` 期限 2026-10-11
    「**ショートの最後で登録を直接1回頼むと、登録率が上がる**」の**処置群**が
    積みはじめた、という意味です（`src/script_writer.py`「2026-08-24 に解禁」。
    実際に出はじめたのは **2026-08-26 02:50**）。

    ## いま固定していること

    **ショートの終端は、問いかけか依頼のどちらかであること。**
    どちらでもない本が出たら、それは `script_writer` の型から外れた本です
    （長尺の「明日やること」がショートに漏れた、など。実際に長尺側では
    その型を使っているので、漏れは起こりえます）。

    **件数では固定しません** —— 同じ枝で主実行が走っていて、毎周 増えます。
    """
    _, breakdown = ev.population(ev.load_ledger())
    assert breakdown["ask"] > 300, "問いかけ型（過去の在庫）が消えています"

    ledger, seen, stray = ev.load_ledger(), set(), []
    for row in ledger:
        vid = row["video_id"]
        if vid in seen or "#Shorts" not in (row.get("title") or ""):
            continue
        seen.add(vid)
        if ev.form_of(vid) == "other":
            stray.append(vid)
    assert not stray, (
        "終端が問いかけでも依頼でもないショートがあります: "
        f"{stray[:5]}（全 {len(stray)}本）。"
        "`src/script_writer.py` の終端の型から外れています —— "
        "長尺の「明日やること」がショートに漏れていないか見ること。"
    )


def test_依頼と問いかけは独立に数える():
    """**「問いかけでない ＝ 依頼」ではありません。**

    `src/script_writer.py`:「問いかけを残す余裕があるなら残してよいが、
    **優先は依頼のほう**」。両方 入っている本は `is_ask` も `is_request` も真です。
    **処置群を `not_ask` で数えると、その本を落とします**（＝ 群が実際より小さく見え、
    30,000再生 の門に届くのが遅く見える）。
    """
    both = ["この計算を毎日出しています。登録して次の数字を受け取りますか。"]
    assert ev.is_ask(both) and ev.is_request(both)
    only_ask = ["あなたの手当は全員同額ですか。"]
    assert ev.is_ask(only_ask) and not ev.is_request(only_ask)
    only_req = ["介護の限度額の計算を毎日出すので登録してください"]
    assert ev.is_request(only_req) and not ev.is_ask(only_req)
    assert ev.is_request([]) is False
