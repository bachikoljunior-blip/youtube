"""**書き手が、人間の専門家を名乗らないこと。**（`AUTOMATION_PAUSED.md` 解除条件 1・2）

## この検査が守っているもの（2026-08-30）

オーナーが 08/30 に直接 push した `AUTOMATION_PAUSED.md` は、生成・投稿を止めた
理由をこう書いています。

    - AI-generated personas presenting themselves as human experts on sensitive topics
    - AI personas providing financial guidance or interpreting legal rules

その時点の `config/channel.yaml` の `persona` は **「元・事業会社の経理／人事で、
制度を実務で回してきた立場から解説する」**でした。**実在しない人間の実務経歴**を
名乗って税・保険・雇用の話をする形で、`CLAUDE.md` が「手段として成立しない」と
書いている **なりすまし** に当たります。

**収益化されなければ、RPM がいくつでも収入は 0 円**（`CLAUDE.md`）。
つまりこれは危険度の話ではなく、**到達可能性そのもの**の話です。
`scripts/eta.py` の言い方では、`p_pass`（審査に受かる確率）は到達日に
**掛かる**項で、4本の腕はその内側にあります —— **外側が 0 なら、
内側を何倍にしても 0。**

## なぜ「直した」で終わらせないか

`persona` は 1か所の文字列で、**書き戻すのは 3行の編集**です。
この repo は「昔そう決まったから」で戻る事故を何度も記録しています
（`CLAUDE.md` A14・`docs/JOURNAL.md`）。**門にしておかないと、
次に台本の出来を上げたい回が「実務家の口調のほうが刺さる」と考えて戻します。**

## 覆る条件

YouTube 側のポリシーが変わって、この制約が要らなくなったら**この検査ごと消してよい。**
そのときは `AUTOMATION_PAUSED.md` の解除条件 1・2 も同時に書き換わっているはずで、
**片方だけが残っている状態を作らないこと。**
"""
from __future__ import annotations

import re

import yaml

from src.config import ROOT

CHANNEL = ROOT / "config" / "channel.yaml"

#: **人間の書き手を名乗る語。** 一致したら赤。
#:
#: 「元・経理」「経理出身」「10年の実務」「私が担当していた」のような形を拾います。
#: **語を増やすときは、実際に踏んだ文だけを足すこと** ——
#: 想像で広げると、正しい台本まで落ちて、次の回がこの門ごと外します。
HUMAN_CLAIMS = (
    r"元[・･]?\s*(事業会社|会社|企業)",
    r"(経理|人事|総務|税理士|社労士|社会保険労務士|FP|ファイナンシャルプランナー)"
    r"\s*(出身|として働|の実務経験|歴)",
    r"実務経験\s*\d+\s*年",
    r"\d+\s*年(間)?の実務",
    r"(私|僕|自分)(は|が)[^。\n]{0,20}(担当|勤務|在籍|経験)し",
    r"現役の?\s*(税理士|社労士|会計士|FP)",
)

#: **助言・相談回答の形。**（ポリシーの2行目「providing financial guidance」）
ADVICE_SHAPES = (
    r"あなたの場合は",
    r"ご相談",
    r"アドバイスします",
)


def _persona() -> str:
    cfg = yaml.safe_load(CHANNEL.read_text(encoding="utf-8"))
    return (cfg["channel"]["persona"] or "").strip()


def test_persona_claims_no_human_career():
    """**経歴・資格・実務年数を名乗らないこと。**"""
    body = _persona()
    hits = [p for p in HUMAN_CLAIMS if re.search(p, body)]
    assert not hits, (
        "`config/channel.yaml` の persona が、人間の実務経歴を名乗っています"
        f"（当たった形: {hits}）。**これが 2026-08-30 の停止の原因そのもの**です ——"
        " `AUTOMATION_PAUSED.md` の解除条件 1・2。戻すなら、先にあちらを書き換えること。")


def test_persona_is_not_advice_shaped():
    """**個別の助言の形にしないこと。**（「financial guidance」の側）"""
    body = _persona()
    hits = [p for p in ADVICE_SHAPES if re.search(p, body)]
    assert not hits, f"persona が相談回答の形になっています（{hits}）"


def test_persona_says_what_it_is_instead():
    """**「名乗らない」だけでは足りない。** 何として話すかが書いてあること。

    空にすると `script_writer` の `# 書き手の人格` が無内容になり、
    モデルが**自分で人格を作ります**（そこが最も戻りやすい所）。
    `CLAUDE.md` の根幹どおり「計算して、前提と式を出す」が本文に要ります。
    """
    body = _persona()
    assert len(body) >= 40, "persona が空同然です —— 空欄はモデルが埋めます"
    assert "計算" in body, "何をする書き手なのか（計算する）が書かれていない"
    assert "前提" in body, "前提を出すこと（独自性の出どころ）が書かれていない"


def test_the_forbidden_shapes_are_also_in_avoid():
    """**`avoid` にも載っていること。** persona と avoid は別の所からプロンプトに入ります
    （`src/script_writer.TASK` の「# 書き手の人格」と「# 扱わないこと」）。
    片方だけだと、もう片方の節がモデルに逃げ道を残します。"""
    cfg = yaml.safe_load(CHANNEL.read_text(encoding="utf-8"))
    avoid = "\n".join(cfg["channel"]["avoid"])
    assert "経歴" in avoid or "人間として" in avoid, (
        "`avoid` に「書き手を人間として語ること」が無い")
    assert "助言" in avoid or "相談" in avoid, (
        "`avoid` に「個別の助言・相談回答の形」が無い")
