"""札と声の言い回しの対応を `lint` が `[?]` で名指しする門
（2026-09-11 21:4x・optimizer・Opus。**§15 の申し送りを閉じた側**）。

§3 の 7-b（2026-09-10 13:3x・hourly・Fable。オーナー 12:3x「言い回しで、事実なのか前提なのかとか
分かるようにした方が良い」）が決めた口は **3つ だけ** ——
前提「たとえば、」・決まり「決まりでは、」・計算「計算すると、」。
**結論・見る所・しくみ には口を決めない**（§3 の 7-b・7-c）。

**輪も lint も、ここまで `tag` を1度も見ていませんでした** —— `critic.critique_screen` に
板と札は渡るが、`tag` と `say` の言い回しの対応を見る所がどこにも無い（§4 (0) と同じ族）。

**1文目のどこかに在るか**で見ます（文頭ちょうどではない）—— 実物の 09/12 コマ5 が
「そこで決まりでは、…」で、接続詞を 1つ 前に置く形は書き手の慣行だから
（撃って数えた: 頭ちょうどにすると 09/12 の本で 1件 増える）。**止めない。**

覆る条件は `script.TAG_OPENERS` の註（3つ）。
"""
from studio import script


def _seg(say: str, tag: str) -> dict:
    return {"say": say, "show": "", "sub": "", "tag": tag, "board": []}


def _script(pairs: list[tuple[str, str]]) -> script.Script:
    return script.Script(
        id="test-tag-opener", date="2026-09-12", title="ためし #Shorts",
        takeaway="ためし", description="ためし", tags=[],
        yomi={}, segments=[_seg(s, t) for s, t in pairs] + [_seg("なぜかを言います。", "しくみ")],
    )


def _rings(s: script.Script) -> list[str]:
    return [w for w in s.warnings() if "声の口" in w]


def test_口がそろっていれば鳴らない():
    s = _script([
        ("たとえば、30年はたらいた人です。", "前提"),
        ("決まりでは、枠は年数で決まります。", "決まり"),
        ("計算すると、枠は1500万円です。", "計算"),
    ])
    assert _rings(s) == []


def test_接続詞が1つ前に付く形は通す():
    """実物 09/12 コマ5「そこで決まりでは、…」。頭ちょうどで見ると、ここが偽で鳴る。"""
    s = _script([("そこで決まりでは、退職金はほかの収入とわけます。", "決まり")])
    assert _rings(s) == []


def test_口が無ければ名指しする():
    """実物 09/12 コマ10「では、20年でやめた人はどうか。」＝ 2人目の例なのに「たとえば、」が無い。"""
    s = _script([("では、20年でやめた人はどうか。枠は800万円です。", "前提")])
    rings = _rings(s)
    assert len(rings) == 1, rings
    assert "前提" in rings[0] and "たとえば、" in rings[0]


def test_2文目に在っても名指しする():
    """1文目で札を名乗らないと、視聴者が事実か前提かを聞き分けられない（オーナー 12:3x）。"""
    s = _script([("枠は800万円です。たとえば、20年でやめた人です。", "前提")])
    assert len(_rings(s)) == 1


def test_口を決めない札は見ない():
    for tag in ("結論", "見る所", "しくみ"):
        s = _script([("あわせて1500万円が枠です。", tag)])
        assert _rings(s) == [], tag


def test_札が空のコマは見ない():
    """板の無い台本（公開ずみの 5本）は `tag` が空 ＝ この門に当たらない（§3 の 7-b）。"""
    s = _script([("会社をやめて、退職金をもらう人へ。", "")])
    assert _rings(s) == []


def test_止めない():
    s = _script([("では、20年でやめた人はどうか。", "前提")])
    assert [p for p in s.problems() if "声の口" in p] == []


def test_口の出どころは1か所():
    """§3 の 7-b が口を変えたら、直すのは `TAG_OPENERS` だけ（覆る条件 (2)）。"""
    assert set(script.TAG_OPENERS) == {"前提", "決まり", "計算"}
    assert set(script.TAG_OPENERS) < set(script.TAGS)


# ---- 【2026-09-16 14:3x】毎コマ → 本に 1度 へ変えた（オーナー `be77dee9`） ----

def test_本に1度出ていれば残りのコマは鳴らない():
    """**この規則が、オーナーが違和感を言った当のものを毎コマ 作っていました。**

    オーナー 09/16 12:2x「あと決まりでは、と言うのが連続してくると違和感ある」。
    「札が同じなら同じ口で文を始める」を毎コマ 当てると、札が続くコマで声が必ず同じ字で始まります
    （実物: 113コマ の本で「決まりでは、」20回）。
    09/10 の「事実なのか前提なのか分かるように」は**画面の札**（`slides.TAG_COLORS`）が毎コマ 持つ側へ。
    """
    s = _script([
        ("計算すると、枠は1500万円です。", "計算"),
        ("そこから税金を引きます。", "計算"),
        ("のこりは1400万円です。", "計算"),
    ])
    assert _rings(s) == []


def test_本に1度も出ていない札だけ鳴る():
    s = _script([
        ("枠は1500万円です。", "計算"),
        ("そこから税金を引きます。", "計算"),
    ])
    rings = _rings(s)
    assert len(rings) == 1 and "計算" in rings[0]
    assert "毎コマ ではありません" in rings[0], "戻すときに、なぜ変えたかが読めること"


def test_窓の中の2度目は別の門が止める():
    """声の口を毎コマ 求めるのをやめた代わりに、**近くの繰り返し**は `problems()` が止めます。"""
    s = _script([
        ("計算すると、枠は1500万円です。", "計算"),
        ("計算すると、のこりは1400万円です。", "計算"),
    ])
    assert _rings(s) == []
    # 門は日付で切ってあります（`CLARITY_FROM` ＝ 公開ずみの本を遡って赤くしない）
    s.date = "2026-09-20"
    assert [p for p in s.problems() if "書き出し" in p], "窓の中の 2度目は赤にすること"
