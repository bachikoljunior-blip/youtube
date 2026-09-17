"""**説明欄の食い違いは、向きを見ないと前の周の仕事を壊します**
（2026-09-18 05:xx JST・optimizer・Fable 5.1・ultracode・`cli.desc_appended` の註）。

09/18 の 5本 は 3周 続けて `!! 台本と食い違い: 説明欄 → update_meta(...)` と印字していました。
引くと **live は台本を 1字も変えずに含み、後ろに §33 の橋が 278字 足されている**だけで、
その `update_meta` は **50単位 × 5 を払って橋を 5本 とも消す手**でした。
`meta_mark` は**題**についてだけ同じ向きを見分けており（台帳 `retitled`）、
**説明欄にはその口がありませんでした**（`meta_mark` の覆る条件 (2) が名指ししていた穴）。

止めるのは 4つ:

  (1) 前方一致（live ⊃ 台本）なら、足された分を返すこと
  (2) **陰性対照** —— 全一致・書き換え（前方一致でない）では返さないこと
  (3) 前後の空白だけの差では返さないこと（`_trim` が先に当てる）
  (4) `meta_mark` が **`update_meta` を勧めない**こと ＝ 直す先が台本だと言うこと
"""
from studio import cli


class _S:
    def __init__(self, description, title="題", tags=()):
        self.description = description
        self.title = title
        self.tags = list(tags)


BODY = "本文です。\n#年金 #手取り"
BRIDGE = "\n\n【くわしい計算（長尺）】\n・https://youtu.be/4MpH3QliNi4"


def test_足された分を返す():
    rd = {"description": BODY + BRIDGE}
    added = cli.desc_appended(rd, _S(BODY))
    assert added is not None
    assert added.startswith("【くわしい計算（長尺）】")


def test_陰性対照_全一致と書き換えでは返さない():
    assert cli.desc_appended({"description": BODY}, _S(BODY)) is None
    # 書き換え（前方一致でない）＝ 向きが分からないので、この口は黙る
    assert cli.desc_appended({"description": "ちがう本文\n" + BRIDGE}, _S(BODY)) is None


def test_前後の空白だけの差では返さない():
    assert cli.desc_appended({"description": "\n" + BODY + "\n\n"}, _S(BODY)) is None


def test_meta_mark_は_update_meta_を勧めない():
    mark = cli.meta_mark(["説明欄"], "vid1", rows=[], added="【くわしい計算（長尺）】\n・https://x")
    assert "live のほうが新しい" in mark
    assert "その足した分が消えます" in mark
    assert "直すのは台本の `description`" in mark
    # **陽性対照** —— 足された分が無ければ、いままでどおり `update_meta` を出すこと
    plain = cli.meta_mark(["説明欄"], "vid1", rows=[], added=None)
    assert "yt.update_meta" in plain


def test_ほかの欄の食い違いは落とさない():
    mark = cli.meta_mark(["説明欄", "tags"], "vid1", rows=[], added="橋の行")
    assert "tags" in mark
