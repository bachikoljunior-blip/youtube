"""`show`/`sub` だけに古い言い方が残った回を `lint` が言うこと（2026-09-09 06:5x・optimizer・Opus）。

**なぜ足したか**（実測。作り物ではありません）:
09/10 の本（`2026-09-10-izoku-kosei-4bunno3`）で、03:2x の直しは「年に」→「毎年」を
**`say` と `sub` にしか当てていません**（commit `ae5bb859` の本文「門と同じ regex で `say` と `sub` に当てた」）。
`show` は 3コマ 残り、**声は「毎年320万円」・画面は「年に320万円」**という食い違いが
06:5x まで（3周半）誰にも見えていませんでした。

**なぜ どの道具にも見えなかったか**:

    lint の門    `studio/script.py` の `warnings()` が `s.say` しか読まない
    hear         声と音を突き合わせる ＝ **画面は音にならない**
    critique     say/show/sub を読むが、指すのは「分かりにくさ」で、声と画面の食い違いではない
    crosscheck   声 と 説明欄・notes を見る ＝ **`show` は入っていない**

**拾うのは「年に」だけ ——「年」＋数字 では広すぎました（先に撃って外した）**:
最初この検査は `BARE_YEAR`（裸の「年」＋数字）を画面に当てましたが、
**09/06 の本 `zaishoku-62man` コマ8 が鳴りました** —— show「年66万円多い」／声「1年で66万円です」。
これは取り残しではなく、**16字の見出しとしての正しい縮め方**です（画面は読まれないので誤読も起きない）。
「年に」だけが違うのは、**縮め方として何も得しない形**（「年320万円」のほうが短い）で、かつ
**§3 が名指しで捨てた言い方**だから ＝ 画面に在れば、声を直したときの取り残しです。
だから **`say` にも残っている回は鳴らしません**（そちらは上の門が鳴る ＝ 1つの原因に2つの声を出さない）。
"""
from studio import script as sc


def _warn(say: str, show: str = "", sub: str = "") -> list[str]:
    seg = sc.Segment(say=say, show=show, sub=sub)
    s = sc.Script(id="t", title="t", date="2026-09-10", segments=[seg], takeaway="t")
    return [w for w in s.warnings() if "画面" in w]


#: **凍らせた証拠**（`git show b76738d8^:data/studio/scripts/2026-09-10-izoku-kosei-4bunno3.json`）。
#: 03:2x の直しのあと・06:5x の直しの前に、実際にファイルに在った 3コマ。
#: say は既に「毎年」に直っており、show だけが「年に」で残っていました。
STALE = [
    ("厚生年金のほかに、基礎年金がひとり毎年80万円ずつ、ふたりで160万円。", "夫婦あわせて\n年に320万円"),
    ("夫は毎年120万円でしたから、その4分の3で毎年90万円になります。", "年に90万円"),
    ("妻の基礎年金80万円は、そのまま出ます。あわせて毎年170万円です。", "妻の年金は\n年に170万円"),
]


def test_09_10_の本で実際に残っていた3コマが鳴る():
    for say, show in STALE:
        assert _warn(say, show=show), f"鳴らない: {show!r}"


def test_subの側も見る():
    # 03:2x は sub を直したが、直し忘れる側は回によって入れ替わる
    assert _warn("あわせて毎年170万円です。", sub="妻の年金は 年に170万円")


def test_声にも残っている回は鳴らさない():
    """1つの原因に2つの声を出さない —— そちらは `s.say` の門が鳴る。"""
    assert not _warn("妻の年金は年に170万円です。", show="年に170万円")


def test_声と画面がそろっている回は鳴らさない():
    assert not _warn("あわせて毎年170万円です。", show="妻の年金は\n毎年170万円")
    assert not _warn("70歳まで5年おくらせると42%増えます。", show="5年で42%")


def test_いまの09_10の本は鳴らない():
    """06:5x に直した後の実物。ここが鳴ったら、また片側だけ直した回。"""
    import json, pathlib
    p = pathlib.Path("data/studio/scripts/2026-09-10-izoku-kosei-4bunno3.json")
    d = json.loads(p.read_text())
    s = sc.Script(**d)
    assert [w for w in s.warnings() if "画面" in w] == []


def test_09_06_の本の見出しは鳴らさない():
    """**陰性対照**（捨てないこと）。広いほうの門で撃って、実際に外した1件。

    show「年66万円多い」は声「1年で66万円です」の取り残しではなく、16字に縮めた見出し。
    ここが鳴ったら、門がまた広がっている。
    """
    import json, pathlib
    d = json.loads(pathlib.Path("data/studio/scripts/2026-09-06-zaishoku-62man.json").read_text())
    s = sc.Script(**d)
    assert [w for w in s.warnings() if "画面" in w] == []
