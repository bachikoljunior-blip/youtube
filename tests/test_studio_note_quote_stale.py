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


# ---- 札を 3つ に分ける（2026-09-12 00:0x・optimizer・Opus。§14 の申し送り「直す先は印字の側でもよい」）
# **門は動かしていません** —— 下の 3件 はどれも鳴ったままで、変わるのは行の言い方だけ。
# 数（実物 15件 に当てた）と 覆る条件 (6)(7)(8) は `script._QUOTE_COPY_MARK` の註。


def _warn(notes: str) -> str:
    ws = [w for w in _script(notes, SAYS).warnings() if "notes の" in w]
    assert len(ws) == 1, ws
    return ws[0]


def test_書き直しの記録らしい行は消すなと言う():
    """実物 9件（09/06 2・09/07 4・09/11 3）の形 —— 引用のすぐ右に書き直しの語。"""
    w = _warn('480字に収めるため コマ2「20年までは1年で40万円ずつ」→「1年で40万円」。')
    assert "作業の記録らしい" in w and "消さないこと" in w


def test_記録の印は左にも在る():
    """`…を落とした（…）` の向き（09/07 コマ4・コマ5 の形）。"""
    w = _warn('95秒 を越えた → コマ2「20年までは1年で40万円ずつ」を落とした（コマ3 に同じ札）。')
    assert "作業の記録らしい" in w


def test_記録の鎖は継ぐ():
    """印は 1つ目の左に在り、長い引用を跨ぐと 24字 から外れます（09/07 コマ3 の形）。"""
    ws = [w for w in _script(
        'だから単位そのものを捨てた: コマ2「20年までは1年で40万円ずつ」・'
        'コマ3「はみ出た700万円も、半分にします」（式は説明欄）。', SAYS).warnings() if "notes の" in w]
    assert len(ws) == 2, ws
    assert all("作業の記録らしい" in w for w in ws)


def test_写しの印が在る行は強い札のまま():
    """`＝ 声の コマN「…」` ＝ notes が声を引いている所そのもの。実物の本物 6件 のうち 4件 がこの形。"""
    w = _warn('国税庁 No.1420。\n＝ 声の コマ2「20年までは1年で40万円ずつふえます」は、この式そのもの。')
    assert "写しを声に合わせる" in w and "作業の記録" not in w


def test_写しの鎖も継ぐ():
    ws = [w for w in _script(
        '＝ 声の コマ2「20年までは1年で40万円ずつふえます」・'
        'コマ3「はみ出た700万円も、半分にします」は、この2つの式。', SAYS).warnings() if "notes の" in w]
    assert len(ws) == 2, ws
    assert all("写しを声に合わせる" in w for w in ws)


def test_写しの印は記録の語に勝つ():
    """順は 写し → 記録。写しの印が在る行は、近くに `→` が在っても弱くしない（(6) の当て所）。"""
    w = _warn('＝ 声の コマ2「20年までは1年で40万円ずつふえます」→ この式そのもの。')
    assert "写しを声に合わせる" in w


def test_どちらの印も無ければ今までの札():
    """実物の本物 6件 のうち 2件（09/12 コマ11・コマ5）がこの側 ＝ **弱くしない**。"""
    w = _warn('言い換えられない語は使わない（§3 の 2）ので、'
              'コマ2「20年までは1年で40万円ずつふえます」と言っている。')
    assert "作業の記録" not in w and "`＝ 声の`" not in w
    assert "写しを声に合わせる" in w


def test_陽性対照_印の表を空にすると記録の札が消える():
    saved_r, saved_l = script._QUOTE_REC_RIGHT, script._QUOTE_REC_LEFT
    notes = '480字に収めるため コマ2「20年までは1年で40万円ずつ」→「1年で40万円」。'
    assert "作業の記録らしい" in _warn(notes)
    try:
        script._QUOTE_REC_RIGHT, script._QUOTE_REC_LEFT = (), ()
        assert "作業の記録らしい" not in _warn(notes)
    finally:
        script._QUOTE_REC_RIGHT, script._QUOTE_REC_LEFT = saved_r, saved_l


def test_陽性対照_写しの印を変えると強い札が素に落ちる():
    saved = script._QUOTE_COPY_MARK
    notes = '＝ 声の コマ2「20年までは1年で40万円ずつふえます」は、この式そのもの。'
    assert "`＝ 声の`" in _warn(notes)
    try:
        script._QUOTE_COPY_MARK = "ありえない印"
        assert "`＝ 声の`" not in _warn(notes)
    finally:
        script._QUOTE_COPY_MARK = saved


def test_札を分けても鳴る件数は変わらない():
    """**門は動かしていない** —— 3つ の形が、どれも 1件ずつ 鳴ること。"""
    for notes in ('480字に収めるため コマ2「20年までは1年で40万円ずつ」→「1年で40万円」。',
                  '＝ 声の コマ2「20年までは1年で40万円ずつふえます」は、この式そのもの。',
                  'ので、コマ2「20年までは1年で40万円ずつふえます」と言っている。'):
        _warn(notes)


def test_で_をはさむ形で本に無いコマを指していれば名指しする():
    """09/14 の本で実際に踏んだ形（2026-09-13 03:4x）: コマ4 を削って 12コマ になったあとも、
    notes の「声はコマ13で「ねんきん定期便で見る」」が 13 を指したまま 2周 通った。
    `で` を通さない式では 1件も鳴らず、人が §4 (0) の型（2本目）で拾った。"""
    s = _script('声はコマ4で「税金は、この350万円で決まります」とだけ言っている。', SAYS)
    warns = [w for w in s.warnings() if "notes の" in w]
    assert len(warns) == 1, warns
    assert "コマ4" in warns[0] and "無いコマ" in warns[0]


def test_で_をはさむ形でも写しが声と同じなら鳴らない():
    s = _script('声はコマ2で「20年までは、1年ごとに40万円ふえます」とだけ言っている。', SAYS)
    assert [w for w in s.warnings() if "notes の" in w] == []
