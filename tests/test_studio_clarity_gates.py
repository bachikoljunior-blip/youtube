"""オーナー 2026-09-16 12:2x の 2つ（受け取り帳 `be77dee9`）の門。

原文（**一字も変えないこと**）:

    「40年を480か月に言い換えてるのね。分かりづらかった。他にもそういう分かりづらさは
      作り途中のものや、今後作るものでないようにして。これは指示だからサブに渡して。
      あと決まりでは、と言うのが連続してくると違和感ある」

**陽性対照つき** —— 門を `return []` にすると落ちる検査を、どちらの門にも 1件 ずつ置いています
（この repo は 2026-08-xx に「見出しだけ出して 1本も描かずに正常終了」を 7日 見逃しています）。
"""
from pathlib import Path

import pytest

from studio import script as S

ROOT = Path(__file__).resolve().parents[1]


def seg(say, tag="計算"):
    return S.Segment(say=say, show="", sub="", tag=tag, board=[])


# ---- オーナーの原文が repo に在ること（`tests/test_house_rule.py` と同じ形） ----

def test_オーナーの原文がrepoに在る():
    """**門の註と、その回の刻の両方に在ること。**

    `CLAUDE.md` は見ません —— あれは親が同じ周に書き足す側で、
    サブの worktree には まだ来ていないことが在ります（2026-09-16 13:3x に踏んだ）。
    """
    words = "40年を480か月に言い換えてるのね"
    for rel in ("studio/script.py", "docs/JOURNAL.md"):
        assert words in (ROOT / rel).read_text(encoding="utf-8"), f"原文が {rel} に無い"


# ---- (1) 同じ量を別の単位で並べて言い直さない ----

def test_オーナーが指したコマを止める():
    """`2026-09-16-ninni-kanyu-108man` コマ4 そのもの（回帰）。"""
    say = "決まりでは、満額を40年、480か月で割ると、1か月はらうごとに毎年1765円ふえます。"
    assert S.unit_restate(say) == [("40年", "480か月")]


@pytest.mark.parametrize("say", [
    "満額を40年、480か月で割ると、1か月ぶんが出ます。",
    "40年（480か月）はらった人の満額です。",
])
def test_同格の言い直しは止める(say):
    assert S.unit_restate(say), f"止まっていない: {say}"


@pytest.mark.parametrize("say", [
    # 「Xは Y」は換算そのものが計算の一段（次の文でその先を使っている）
    "5年は60か月。保険料は毎月1万7920円かける60で、約108万円です。",
    "40年は480か月なので、満額を480で割ります。",
    # 別の量なら並んでいてもよい
    "20年で800万円、10年で700万円です。",
    # 同じ単位の繰り返しは言い直しではない
    "5年、5年と足して10年です。",
])
def test_仕事をしている換算は止めない(say):
    assert S.unit_restate(say) == [], f"止めてはいけない: {say}"


def test_陽性対照_言い直しの門(monkeypatch):
    """門を殺すと、オーナーが指したコマが通ってしまうこと。"""
    monkeypatch.setattr(S, "_APPOSITION", __import__("re").compile(r"(?!)"))
    assert S.unit_restate("満額を40年、480か月で割ると、") == []


def test_コマをまたぐ言い直しは警告どまり():
    segs = [seg("40年で満額になります。"), seg("加入期間が480か月に足りなければ対象です。")]
    assert S.unit_aliases(segs), "またいだ側は拾うこと"
    # ただし `problems()` ではなく `warnings()` の側（止めない）
    assert all("2通りの単位" not in x for s in segs for x in S.unit_restate(s.say))


# ---- (2) 同じ書き出しを続けない ----

def test_オーナーが指した書き出しを止める():
    """コマ2・4 の「決まりでは、」（1つ おき ＝ オーナーが「連続」と読んだ形）。"""
    segs = [seg("年金の話です。"), seg("決まりでは、年金は65歳から。"),
            seg("たとえば、60歳の女性。"), seg("決まりでは、満額は40年です。")]
    out = S.phrase_runs(segs)
    assert any("決まりでは" in x for x in out)


def test_3つ続けて同じ書き出しは止める():
    segs = [seg(f"計算すると、{n}円です。") for n in (1, 2, 3)]
    assert any("計算すると" in x for x in S.phrase_runs(segs))


def test_主語の繰り返しは止めない():
    """「障害基礎年金は、」が続くのは話題が続いているだけ（オーナーが言ったのは言い回し）。"""
    segs = [seg("障害基礎年金は、請求できません。"), seg("けがをした話です。"),
            seg("障害基礎年金は、60歳から先は出ません。")]
    assert S.phrase_runs(segs) == []
    assert S.opener("障害基礎年金は、請求できません。") == ""


def test_回数の門は尺で割る():
    """絶対の回数にすると長尺で壊れる（191コマ で 3回 ＝ 64コマに 1回 は連続ではない）。"""
    far = [seg("たとえば、Aです。")] + [seg("ふつうの文です。")] * 60 \
        + [seg("たとえば、Bです。")] + [seg("ふつうの文です。")] * 60 \
        + [seg("たとえば、Cです。")]
    assert S.phrase_runs(far) == [], "隔たり 61コマ を止めてはいけない"
    tight = [seg("たとえば、Aです。"), seg("ふつうの文です。")] * 4
    assert S.phrase_runs(tight), "短い本で 4回 は止めること"


def test_陽性対照_書き出しの門(monkeypatch):
    monkeypatch.setattr(S, "STOCK_OPENERS", frozenset())
    segs = [seg(f"計算すると、{n}円です。") for n in (1, 2, 3)]
    assert S.phrase_runs(segs) == []


# ---- 直す口 ----

def test_直す口は間を空ける():
    """隣り合いを外すだけでは、回数の門が代わりに鳴る（2026-09-16 13:0x に踏んだ）。"""
    segs = [seg(f"決まりでは、{n}です。") if n % 3 == 0 else seg(f"ふつうの文{n}です。")
            for n in range(60)]
    for i, _old, new, tag in S.drop_repeated_openers(segs):
        segs[i - 1].say = new
        segs[i - 1].tag = segs[i - 1].tag or tag
    assert S.phrase_runs(segs) == [], "直したあとに門が 1件も残らないこと"


def test_直す口は札が空なら札を立てる():
    """声から消える印を、画面（`slides.TAG_COLORS`）へ移すこと。"""
    segs = [seg("決まりでは、Aです。", tag=""), seg("決まりでは、Bです。", tag="")]
    out = S.drop_repeated_openers(segs)
    assert out and out[0][3] == "決まり"


def test_直す口は札の無い書き出しを落とさない():
    """`OPENER_TAG` に無い言い回し（「だから」）は、落とすと印がどこにも残らない。"""
    segs = [seg("だから、Aです。", tag=""), seg("だから、Bです。", tag="")]
    assert S.drop_repeated_openers(segs) == []


# ---- 前の一手の型 ----

def test_前の一手の型は自分が要る読みを連れてくる():
    """型の `say` の漢字が、`EARLY_CTA_YOMI` だけで全部 覆えること。

    2026-09-16 13:2x に踏んだ: 型をそのまま入れた長尺 5本 が、5本 とも
    「『数字』の読みが固定されていない」で赤くなった。**型が要る読みを、型が言っていなかった。**
    """
    #: 出口の型（`default_cta`）の語は、門（`CTA_FROM` 2026-09-15）が在るので
    #: **通っている本の `yomi` には必ず在ります**。だから見るのは「その差」だけ。
    early = S.uncovered_kanji(S.default_early_cta().say, S.EARLY_CTA_YOMI)
    exit_ = S.uncovered_kanji(S.default_cta().say, {})
    assert set(early) <= set(exit_), f"型が要る読みを、型が言っていない: {set(early) - set(exit_)}"


# ---- 公開ずみの本を遡って赤くしない ----

def test_公開ずみの本は遡って赤くしない():
    s = S.Script(id="2026-09-16-ninni-kanyu-108man", date="2026-09-16",
                 title="x #Shorts", takeaway="x", form="short",
                 segments=[seg("決まりでは、40年、480か月で割ります。")] * 11)
    assert all("言い直" not in p and "書き出し" not in p for p in s.problems())


def test_公開ずみの本は前の一手の門でも赤くならない():
    """**日付では 1日の中の時刻を切れません**（2026-09-16 16:0x に足した）。

    `2026-09-19-nenkin-15man-tedori` は `date` が 09/19 なのに **09/16 12:00 に公開ずみ**
    （前の晩に別の枠へ動かした本）で、**もう直せないのに永久に赤いまま**でした。
    **直せない赤は、次の回に「焼き直す物だ」と読ませます ＝ 狼少年になります。**
    """
    # 出口の一手（`CTA_FROM`）は別の門なので、そちらは満たしておく
    segs = [seg(say="あ" * 60) for _ in range(39)] + [seg(say="登録しておくと、あすの分もとどきます。")]
    s = S.Script(id="2026-09-19-nenkin-15man-tedori", date="2026-09-19",
                 title="x", takeaway="x", form="long", segments=segs)
    assert all("登録の一手" not in p for p in s.problems()), s.problems()


def test_公開ずみでない長尺は前の一手の門で赤くなる():
    """陽性対照 —— 外した所が、外すべきでない本まで通していないこと。"""
    segs = [seg(say="あ" * 60) for _ in range(39)] + [seg(say="登録しておくと、あすの分もとどきます。")]
    s = S.Script(id="2026-09-20-nanika", date="2026-09-20",
                 title="x", takeaway="x", form="long", segments=segs)
    assert any("長尺の前半に登録の一手が無い" in p for p in s.problems())
