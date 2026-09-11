"""notes の「コマN「…」」の写しが、いまの声と食い違うのを `lint` が名指しする門
（2026-09-11 21:4x・optimizer・Opus。**§15 の申し送りを閉じた側**）。

**なぜ機械の門にしたか**（`hourly` 21:2x の刻・JOURNAL）: 声を書き直した回が、notes の写しを
置いていきます —— **10時間 で 2度**（11:5x・20:0x）。notes 自身に「声を直した回は、ここも
一緒に直すこと」と書いてあっても踏みました ＝ **人が守る申し送りでは持ちません。**
同じ族（あとの手の直しが、前の手の答えを古くする）: §4 (0-b)・`loop_sig`・`build_sig` ——
**この族の中で、これだけが機械の門を持っていませんでした。**

**止めない**（`warnings()` の側）—— 写しが古いだけで本は出せるし、notes は焼きに渡らないので
`build_sig` も上げていません（鳴っても焼き直しは不要）。

**陽性対照は捨てないこと**: `git show 29e1cce4^:data/studio/scripts/2026-09-12-taishoku-koujo-70man.json`
＝ 写しが 5か所 古かったときの本そのもの（直したのは 29e1cce4）。

覆る条件は `script.stale_note_quotes` と `script._QUOTE_MIN` の註（5つ）。
"""
from studio import script


def _seg(say: str) -> dict:
    return {"say": say, "show": "", "sub": "", "tag": "", "board": []}


def _script(notes: str, says: list[str]) -> script.Script:
    return script.Script(
        id="test-note-quote", date="2026-09-12", title="ためし #Shorts",
        takeaway="ためし", description="ためし", tags=[],
        yomi={}, notes=notes, segments=[_seg(x) for x in says],
    )


SAYS = [
    "会社をやめて、退職金をもらう人へ。税金の話です。",
    "決まりでは、20年までは、1年ごとに40万円ふえます。",
    "決まりでは、はみ出た700万円も、何年ぶんかがまとまっています。",
]


def test_写しが声と同じなら鳴らない():
    s = _script('コマ2「20年までは、1年ごとに40万円ふえます」は式そのもの。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []


def test_写しが古ければ名指しする():
    # 09/12 の本で実際に踏んだ形（20:0x の書き直しの前の字が残った）
    s = _script('コマ2「20年までは1年で40万円ずつ」は式そのもの。', SAYS)
    warns = [w for w in s.warnings() if "notes の" in w]
    assert len(warns) == 1, warns
    assert "コマ2" in warns[0]


def test_助詞をはさむ形も拾う():
    """`コマ11 は「…」` —— いちばん高い写し（どのコマに分離課税が在るか）がこの形だった。"""
    s = _script('コマ3 は「税金は、この350万円で決まります」と言っている。', SAYS)
    warns = [w for w in s.warnings() if "notes の" in w]
    assert len(warns) == 1, warns
    assert "コマ3" in warns[0]


def test_省略の三点は割って当てる():
    s = _script('コマ3「決まりでは、はみ出た700万円も…がまとまっています」。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []


def test_太字の印と句読点は落として当てる():
    s = _script('コマ2「決まりでは、**20年まで**は、1年ごとに40万円ふえます」。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []


def test_短い断片は見ない():
    """実測の外れの族 (a): notes が語を指しているだけ（「厚生年金」「12か月で」…）。"""
    s = _script('コマ2「40万円ずつ」の側。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []


def test_問いの札は見ない():
    """実測の外れの族 (b): 見出し（「なぜ配偶者の年金で止まるか」）で、声の引き写しではない。"""
    s = _script('コマ3「なぜ半分にするのか、なぜ割るのか」の答えは下。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []


def test_無いコマを指したら名指しする():
    s = _script('コマ9「20年までは、1年ごとに40万円ふえます」。', SAYS)
    warns = [w for w in s.warnings() if "notes の" in w]
    assert len(warns) == 1, warns
    assert "無いコマ" in warns[0]


def test_止めない():
    s = _script('コマ2「20年までは1年で40万円ずつ」。', SAYS)
    assert [p for p in s.problems() if "notes" in p] == []


def test_陽性対照_門を外すと直した本でも鳴る():
    """`_QUOTE_MIN` を 0 に戻すと、短い断片の族が戻ることを実際に撃って確かめる
    （＝ 門が「効いていない所で効いているふり」をしていない）。"""
    s = _script('コマ2「40万円ずつ」の側。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []
    saved = script._QUOTE_MIN
    try:
        script._QUOTE_MIN = 0
        assert len(script.stale_note_quotes(s.notes, [x.say for x in s.segments])) == 1
    finally:
        script._QUOTE_MIN = saved
