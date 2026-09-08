"""`studio/script.BARE_YEAR` が「年に」＋数字 も拾うこと（2026-09-09 02:5x・optimizer・Opus）。

**なぜ足したか**（§5 の申し送り: `hourly` が名指しし、optimizer が撃った・METHOD §12 02:5x）:
09/10 の本（`2026-09-10-izoku-kosei-4bunno3`・455字）は lint を `[?]` 0 で通り、
**hear が 11コマ中 5コマ しか一致しませんでした**。外れた 6コマ は全部
`予定「ねん」 聞こえた「とし」` で、「年に」を含む say は **[2,3,5,8,9,10]** ＝ hear が割った 6コマ と一致。

**原因は門ではなく、門の助言文でした** —— `warnings()` の助言が「『1年で』『年に』に」と
**「年に」へ書き換えろ**と言っており、書き手はそのとおり書きました（「夫の厚生年金は年に120万円」）。
§3 の 9 が挙げているのは「1年で」「12か月で」だけで、**助言だけが §3 と食い違っていた**。

だから検査も2つ要ります: **門が「年に」を拾うこと**と、**助言が「年に」を勧めないこと**。
後者が無いと、regex だけ直して助言文を戻した回に気づけません（＝ 元の穴がそのまま開き直る）。

**陽性対照**: `年(?:に)?` を `年` に戻すと `test_年にを拾う` と
`test_09_10_の本で6コマ鳴る` が落ちる（撃って確かめた）。
"""
import re

from studio import script as sc


def _say_warnings(say: str) -> list[str]:
    seg = sc.Segment(say=say, show="x", sub=say)
    s = sc.Script(id="t", title="t", date="2026-09-10", segments=[seg], takeaway="t")
    return [w for w in s.warnings() if "年" in w]


def test_年にを拾う():
    # 09/10 の本が実際に書いた形（hear が「としに」と聞いた）
    assert _say_warnings("夫の厚生年金は年に120万円、妻の厚生年金は年に40万円です。")


def test_裸の年と数字は前から拾う():
    # 2026-09-05 に Chirp3-HD で測った元の形。広げても落とさないこと
    assert _say_warnings("ひと月5万5千円、年66万円です。")


def test_毎年は拾わない():
    # 「毎年」は janome が まいとし と読む ＝ 正しい。鳴らせると書き手が直しにいって壊れる
    assert not _say_warnings("毎年6月にとどく年金額改定通知書の金額を見てください。")
    assert not _say_warnings("毎年10月に見直されます。")


def test_数字の直後の年は拾わない():
    # 「5年」「1年に」は 数字＋年 ＝ ねん と読む（COUNTER_RUN の側）。書き換え先そのものなので、
    # ここが鳴ると助言が自分の勧める形を否定する（＝ 書き手が回れなくなる）
    assert not _say_warnings("70歳まで5年おくらせると42%増えます。")
    assert not _say_warnings("夫の厚生年金は1年に120万円です。")


def test_助言は年にを勧めない():
    """**助言文の側の検査**（regex だけ直しても、この文が戻れば同じ本がまた出る）。"""
    w = _say_warnings("年に120万円です。")
    assert w, "門が鳴らなければ助言も出ない"
    assert "「年に」に" not in w[0], "助言が「年に」へ書き換えろと言っている（09/10 の本を出した当の文）"
    assert "1年で" in w[0] and "毎年" in w[0]


def test_09_10_の本で6コマ鳴る():
    """陽性対照つきの実物（`hourly` が「6コマ で鳴るはず」と先に書いた予測）。"""
    s = sc.load("2026-09-10-izoku-kosei-4bunno3")
    hit = [w for w in s.warnings() if "年" in w]
    assert len(hit) == 6, f"6コマ のはず: {hit}"
    # hear が割ったのと同じコマ番号であること（数だけ合って別のコマなら、原因が違う）
    assert [int(re.search(r"コマ(\d+)", w).group(1)) for w in hit] == [2, 3, 5, 8, 9, 10]


def test_09_09_の本は鳴らない():
    """同じ日に出る本（`c29a2a3a`）は 0件 —— 誤報で公開前の本を触らせないこと。"""
    s = sc.load("2026-09-09-kakyu-nenkin-42man3700")
    assert [w for w in s.warnings() if "年" in w] == []
