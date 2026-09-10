# -*- coding: utf-8 -*-
"""`scripts/output_growth.py` —— **`trend` が毎周 印字する字数**を、道具が数えて門を引くこと。

2026-09-10 22:5x JST（optimizer・Opus）。`method_growth.py` は `docs/METHOD.md` の
「毎回 読む」側に門を置きましたが、**毎周 読む物はそれだけではありません** ——
`trend` の**出力**（optimizer が毎周 頭から読む）には、門が 1つもありませんでした。

**いちばん大事な検査は `test_この回が撃った_3点_と_1字も違わないこと`** ——
道具が別の数を出すなら、置いた門は別の物を測っています。

**陽性対照は撃って落としてある**（§5 の教訓の形3つ目）:
  (1) 台帳を写しではなく本物へ向けると、`output_at` は本物を書き換えうる ＝ 写しであることを見る
  (2) 字を `len()` ではなくバイトで数えると 3点 とも合わなくなる（この回に `wc -m` で踏んだ 1.97倍）
  (3) 門の「2窓 続いたら」を「1窓でも」にすると、この回の 3点 で判定が変わる
"""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("output_growth", ROOT / "scripts" / "output_growth.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


O = _mod()


def _at(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=O.JST)


#: 22:5x の回が撃って `scripts/output_growth.py` の冒頭へ書いた 3点（窓の端は周の刻・JST）。
#: **この表を道具から作らないこと** —— 借りると、道具と一緒に間違えます。
点 = [
    ("2026-09-10 10:17", "2026-09-10 14:27", 3310, 4996),
    ("2026-09-10 14:27", "2026-09-10 18:35", 4996, 6893),
    ("2026-09-10 18:35", "2026-09-10 22:32", 6893, 8088),
]

#: **その 3点 を撃ったときの台帳の刻**（2026-09-10 23:2x に足した）。
#: 22:5x はこれを書き残さず、検査は**いまの台帳ぜんぶ**に当てていました ——
#: 台帳は毎周 伸びるので、**コードを 1行も触っていない次の周に、4点 とも外れます**
#: （実測 23:1x: 3,836 / 5,178 / 7,256 / 8,107）。**赤が既定になると、次の回は
#: 自分が壊したのかを見分けられません**（METHOD §6）。
#: **刻を渡せば、何周 経っても 1字も違わずに再現します**（この回に 4点 とも確かめた）。
台帳の刻 = "2026-09-10 22:55"


@pytest.mark.parametrize("a,b,n_a,n_b", 点)
def test_この回が撃った_3点_と_1字も違わないこと(a, b, n_a, n_b):
    cut = _at(台帳の刻)
    for when, want in ((a, n_a), (b, n_b)):
        sha = O.sha_at(_at(when))
        assert sha, f"{when} より前に studio/ の commit が在りません"
        got = len(O.output_at(sha, ledger_cut=cut))
        assert got == want, f"{when} の出力が {want}字 ではありません（{got}字）"


def test_positive_control_台帳の刻を渡さなければ数は動くこと():
    """**陽性対照**（2026-09-10 23:2x）: `ledger_cut` が本当に効いていること。

    切らずに当てた数が 22:5x の数と**同じ**なら、それは台帳が 1行も伸びていないか、
    引数が配線されていないかのどちらかです。**どちらでも、この検査は 3点 を守れていません。**
    """
    sha = O.sha_at(_at("2026-09-10 22:32"))
    assert len(O.output_at(sha, ledger_cut=_at(台帳の刻))) == 8088
    assert len(O.output_at(sha)) != 8088, "台帳が伸びていないか、`ledger_cut` が効いていない"


def test_字はバイトではなく文字で数えること():
    """陽性対照 (2): この環境の locale は `C` なので `wc -m` はバイトを返す。

    日本語の出力では **バイト ÷ 文字 が 1.9 倍 を越えます** —— 道具がバイトで数えていたら、
    門は 2倍 甘くなります（この回に踏んだ: 8,088字 を 15,912 と読んだ）。
    """
    out = O.output_at(O.sha_at(_at("2026-09-10 22:32")), ledger_cut=_at(台帳の刻))
    assert len(out.encode()) / len(out) > 1.9
    assert len(out) == 8088
    # **窓を数える側も文字であること** —— `points()` が `.encode()` を挟めば門は 2倍 甘くなる。
    body = (ROOT / "scripts" / "output_growth.py").read_text().split('"""', 2)[2]
    assert "cache[s] = len(output_at(s))" in body
    assert ".encode()" not in body


def test_台帳は写しを渡すこと():
    """陽性対照 (1): 古いコードに**本物の台帳**を渡さない。

    `output_at` は tempdir に `data/studio/ledger.jsonl` を**コピー**し、
    それ以外の `data/` は symlink にする。写しでなければ、古いコードの書き込みが本物へ届きます。
    """
    src = (ROOT / "scripts" / "output_growth.py").read_text()
    body = src.split('"""', 2)[2]           # docstring より後だけを見る（註の字は数えない）
    assert "shutil.copy2" in body, "台帳を写していません"
    assert 'f.name == "ledger.jsonl"' in body, "写す先が台帳に絞られていません"


def test_門は_2窓_続いたときだけ引く():
    """陽性対照 (3): 「1窓でも越えたら」にすると、この回の 3点 で判定が変わる。"""
    over = {"per_lap": O.CHAR_GATE + 1}
    under = {"per_lap": O.CHAR_GATE - 1}
    # **直近 2窓 の片方だけ**が越えている並びでは引かない（この回の実物がこの形: +281 / +316 / +199）
    assert "引かれません" in O.verdict([under, over, under])[0]
    assert "引かれません" in O.verdict([over, under, over])[0]
    # 直近 2窓 が続けて越えたときだけ引く
    assert "引かれました" in O.verdict([under, over, over])[0]


def test_門は_METHOD_の字の門と同じ数であること():
    """物差しを 2つ 持たない（読むのは同じ 1体・同じ枠）。**変えるなら註の覆る条件 (2) から。**"""
    spec = importlib.util.spec_from_file_location("method_growth", ROOT / "scripts" / "method_growth.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert O.CHAR_GATE == m.CHAR_GATE


def test_窓の端は周の刻で_method_growth_と同じ物を使うこと():
    """窓の取り方が 1点ごとに違うと、点は比べられません（`method_growth` の 05:5x の決め）。"""
    assert O.mg.rounds()[-1] == O.mg.rounds()[-1]
    ps = O.points(laps=6, n=1)
    assert ps and ps[0]["from"] in O.mg.rounds() and ps[0]["to"] in O.mg.rounds()


def test_落ちた点を_0字_として並べないこと():
    """註の覆る条件 (1)。**黙って 0 を返すほうが、外れた数を配るより高く付きます。**"""
    with pytest.raises(RuntimeError):
        O.output_at("0" * 40)


def test_長い行の名指しが出ること():
    """門が引かれたときに「吸った所」を名指しできること（`--lines`）。"""
    got = O.line_sizes("あ" * 50 + "\n" + "い" * 10 + "\n\n" + "う" * 30, top=2)
    assert [n for n, _ in got] == [50, 30]


def test_status_は測らないと書いてあること():
    """`cmd_status` は API を撃つので、古いコードで走らせると単位を使います（註）。"""
    assert "`status` は測れません" in O.__doc__


def test_positive_control_実時計も凍らせていること():
    """**陽性対照**（2026-09-11 02:3x）: 台帳を切るだけでは再現しません。

    `trend` は「引いたのは N時間 前」や 0回 の本の齢を **実時計**から出すので、
    `ledger_cut` だけでは**走らせた時刻**で字数が動きます
    （実測: 同じ sha・同じ刻で 8,088 → 8,089字。増えた 1字 は 9時間 → 10時間）。
    凍らせが効いていれば、**刻を 12時間 ずらすと字数が変わる**はずです
    —— 変わらなければ、渡した `now` はどこにも届いていません。
    """
    sha = O.sha_at(_at("2026-09-10 22:32"))
    cut = _at(台帳の刻)
    a = O.output_at(sha, ledger_cut=cut)
    # **台帳は 1行も動かさず、時計だけ 12時間 進める**（差が出るなら、凍らせは届いている）
    b = O.output_at(sha, ledger_cut=cut, now=cut + O.timedelta(hours=12))
    assert len(a) == 8088
    assert a != b, "台帳が同じで時計だけ動かしても 1字も動かない ＝ 凍らせが届いていません"
