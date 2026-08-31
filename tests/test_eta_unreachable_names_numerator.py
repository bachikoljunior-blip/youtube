"""**「どの帯でも届きません」を、裸で出さないこと。**

`CLAUDE.md`（オーナー指示 2026-08-21 21:3x の直後）:

    (イ) それが引けないうちは、**「届きません」と印字するたびに、
         何を固定したせいでそう出たのかを同じ行に並べる**。
         **裸の「届きません」を出さないこと。**

この検査が見ているのは、**帯の側の固定ではなく分子の側の固定**です。
`eta.py` の 6帯 は `RPM_SCENARIOS` そのもので、**分子は「再生 × 広告 RPM」の1つだけ**
（`TARGET_YEN ÷ RPM × 1000`）。`CLAUDE.md` は稼ぎ方を4つ名指ししています ——
**広告・メンバーシップ・Super Thanks・企業案件**。あとの3つは、この機械のどこにも
入っていません（2026-08-29 の実測: 4語とも `scripts/eta.py` / `src/*.py` /
`docs/MEANS.md` / `docs/STRATEGY.md` / `docs/CONSTRAINTS.md` に **0件**）。

だから断りが無いと、この行は「**YouTube では届かない**」と読まれます。
実際に言えるのは「**広告だけを分子にすると届かない**」までです。

**覆る条件**: `RPM_SCENARIOS` の外の分子（メンバーシップ・Super Thanks・企業案件）が
1つでも `eta.py` の到達計算に入ったら、この検査は書き直すこと ——
そのときは断りではなく**帯そのもの**が答えになります。足し先と着手条件は
`docs/MEANS.md` の M23。

**この検査は文言を固定しません**（言い回しを変えるたびに赤くなるのは費用だけ）。
見ているのは2点だけ: 印字が同じ行にあること、そこに「広告以外の分子」を
名指しする語が在ること。
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
ETA = ROOT / "scripts" / "eta.py"

BARE = "どの帯でも届きません"


def _print_call_containing(src: str, needle: str) -> str:
    """`needle` を含む `P(...)` 呼び出しを、丸ごと1つの文字列で返す。

    引数がいくつに割れていても（暗黙の連結）1件として拾うため、
    行ではなく**括弧の対応**で切ります。

    ## **最初の1件で決めないこと**（2026-08-31 に踏んだ）

    ここは `src.index(needle)` ＝ **ファイル中の最初の1件**だけを見ていました。
    ところが `どの帯でも届きません` は、いま `eta.py` に **4か所**あります ——
    印字は1つで、**残り3つは docstring（この印字を説明している文）**です。
    そして docstring は印字より**前**に書かれることがあるので、
    そのとき `rindex("P(")` は**まったく別の印字**を拾い、
    「メンバーシップが無い」と赤くなりました。**印字は1文字も変わっていません。**

    **説明を書いた回が落とされる**のは、この検査の意図と逆です
    （この検査は「印字に断りを付けろ」であって「同じ語を書くな」ではない）。
    だから**全部の出現を見て、`P(...)` の中身に `needle` が実際に入っている
    ものだけ**を拾います。**docstring の側は、どの `P(` にも入りません。**
    """
    hits: list[str] = []
    pos = 0
    while True:
        i = src.find(needle, pos)
        if i < 0:
            break
        pos = i + 1
        start = src.rfind("P(", 0, i)
        if start < 0:
            continue
        depth = 0
        for j in range(start + 1, len(src)):
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
                if depth == 0:
                    call = src[start:j + 1]
                    # **その `P(` の中に本当に入っているものだけ**を採る。
                    #     docstring の出現は、手前の別の印字を拾ってしまうので落ちる。
                    if needle in call:
                        hits.append(call)
                    break
    assert hits, f"`{needle}` を含む `P(...)` の印字が1つも見つかりません"
    return hits[0]


def test_届きませんの行が分子を名指ししていること():
    src = ETA.read_text(encoding="utf-8")
    assert BARE in src, (
        f"`{BARE}` の印字が消えています。"
        "消したのなら、この検査ごと消すか、新しい印字に合わせて書き直すこと"
    )
    call = _print_call_containing(src, BARE)

    # `CLAUDE.md` が名指ししている、広告以外の3つ。**どれか1つでは足りません** ——
    # 3つとも入っていない断りは、「広告以外にもある」を言い切れていない。
    for word in ("メンバーシップ", "Super Thanks", "企業案件"):
        assert word in call, (
            f"「{BARE}」と**同じ印字の中**に `{word}` がありません。"
            " この行は『YouTube では届かない』と読まれます。"
            " 言えるのは『広告だけを分子にすると届かない』までです"
            f"（`docs/MEANS.md` の M23）。いまの印字: {call[:200]}…"
        )

    # 帯の側が `RPM_SCENARIOS` であることも、同じ行で言うこと
    # （**なぜ広告だけなのか**が、ここを読まないと分かりません）。
    assert "RPM_SCENARIOS" in call, (
        f"「{BARE}」の印字が、6帯が `RPM_SCENARIOS` であることを言っていません。"
        " どこが固定されているかを同じ行に並べるのが (イ) の要求です"
    )


def test_広告以外の分子は台帳に在ること():
    """**断りだけ足して、行き先を書かないのを止める。**

    印字は「広告以外にもある」と言います。**その先の手が台帳に無ければ、
    次の回は同じ所で止まります**（`docs/MEANS.md` は「未着手が0件です。
    これは達成ではありません」を出し続けていました）。
    """
    means = (ROOT / "docs" / "MEANS.md").read_text(encoding="utf-8")
    for word in ("メンバーシップ", "Super Thanks", "企業案件"):
        assert word in means, (
            f"`docs/MEANS.md` に `{word}` がありません。"
            " `eta.py` が『広告だけを分子にすると届かない』と印字しているのに、"
            " 広告以外の手が台帳に1件も無い状態です"
        )
    assert re.search(r"^###\s*M23\.", means, re.M), (
        "`docs/MEANS.md` に M23 の見出しがありません。"
        " `eta.py` の印字がそこを指しています"
    )
