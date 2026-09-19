"""`scripts/for_owner.py` —— **窓の本文は「最小手順」であること**（上限 `BODY_MAX`）。

**2026-09-19 06:2x・optimizer・Opus 5・ultracode・1周 1体。** derivation は `docs/JOURNAL.md` 同刻。

**なぜこの検査が在るか（オーナー原文・受け取り帳 `476e04fa`・2026-09-19 06:2x JST）**:

    「操作依頼出す時は最小手順出すようにしてくれない？」

**`docs/FOR_OWNER.md`「子が守ること」には 2026-08-16 から
「引用の中に『操作依頼』以外を書かないこと」と書いてありました。**
06:2x に数えたら、**生きていた窓 3つ は全部その字を破っていました**:

    09/19 09:00  **1,920字**   手順 3行 ＋「なぜ、これがいま一番大事か」「この1枚で決まること」「距離」
    09/19 20:00  **1,188字**   手順 3行 ＋「なぜ、いま一番これなのか」
    09/20 09:00  **1,145字**   手順 4行 ＋ (A)/(B) の分かれ目
    書き直したあと **512 / 412 / 233字**

**＝ 字で書いても守られないので、形の検査にしました**（`quote_runs` と同じ理由）。

**陽性対照つき**（落ちるまで撃つ）: 長い本文で **必ず** NG が出ること・
いまの `docs/FOR_OWNER.md` では **1件も** 出ないことの両方を見ます。
"""
import datetime as _dt
import importlib.util
from pathlib import Path

#: 窓の刻（`scripts/for_owner.py` と同じ JST）。**陽性対照の作り物にだけ使います。**
_JST = _dt.timezone(_dt.timedelta(hours=9))


def _DT(y: int, m: int, d: int, h: int) -> "_dt.datetime":
    return _dt.datetime(y, m, d, h, 0, tzinfo=_JST)

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "for_owner_min", ROOT / "scripts/for_owner.py")
for_owner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(for_owner)

_HEAD = "### 出す 2026-09-19 09:00〜10:00 JST"


def _md(body: str) -> str:
    return "## 出す\n\n" + body + "\n\n## 出した（記録）\n"


def _problems(body_lines: str):
    return for_owner.parse(_md(f"{_HEAD}\n\n{body_lines}\n"))[1]


def _long(p):
    return [x for x in p if "最小手順ではありません" in x]


def test_上限は原文の根拠つきで在る():
    assert isinstance(for_owner.BODY_MAX, int)
    assert for_owner.BODY_MAX == 700, "変えるなら `docs/JOURNAL.md` に理由と覆る条件を書くこと"


def test_短い手順は問題を出さない():
    """**陰性対照** —— 手順だけの窓は通ること。"""
    body = "> **Studio → カスタマイズ → 基本情報 → ハンドル → 変更**（30秒）"
    assert _long(_problems(body)) == []


def test_ちょうど上限は通る():
    """境目は「越えたら NG」＝ `BODY_MAX` ちょうどは通ること。"""
    body = "> " + "あ" * for_owner.BODY_MAX
    assert _long(_problems(body)) == []


def test_上限を1字越えたら名指しされる():
    """**陽性対照** —— 越えた窓は、字数と見出しの両方を出して落ちること。"""
    body = "> " + "あ" * (for_owner.BODY_MAX + 1)
    p = _long(_problems(body))
    assert len(p) == 1, p
    assert str(for_owner.BODY_MAX + 1) in p[0], "実際の字数を出すこと"
    assert _HEAD in p[0], "どの窓かを名指しすること"


def test_06_2x_に踏んだ長さは落ちる():
    """**実物** —— 書き直す前の 09/19 09:00 の窓（1,920字）は、この検査で落ちること。"""
    body = "> " + "あ" * 1920
    assert len(_long(_problems(body))) == 1


def test_いまの_FOR_OWNER_の窓は全部_最小手順に収まっている():
    """**実物**（この検査を足した回に書き直した側）。"""
    md = (ROOT / "docs/FOR_OWNER.md").read_text(encoding="utf-8")
    blocks, problems = for_owner.parse(md)
    assert blocks, "窓が 1つ も無いのは、見出しの書式が壊れた形（別の検査と同じ入口）"
    over = [(b.head, len(b.body)) for b in blocks if len(b.body) > for_owner.BODY_MAX]
    assert over == [], over
    assert _long(problems) == []


def test_消した字は同じ窓の下に残っていて_親には出ない():
    """**原文を捨てないこと** —— `>` の付かない塊に落としたので、`body` には出ない。

    **【2026-09-19 23:0x】1つの窓を名指しするのをやめ、形そのものを固定しました**
    （optimizer・Opus 5・ultracode・1周 1体）。

    **なぜ**: この検査は `### 出す 2026-09-19 09:00` の窓を名指ししていました。
    **ところが `for_owner.parse()` は「出す」節しか読みません** ——
    オーナーが答えると窓は「**出した（記録）**」へ移り、**parse の返りから消えます**。
    ＝ **窓が仕事を終えた瞬間に、この検査が落ちる形**でした
    （実測: 09/19 10:51 にオーナーが「これで全部やった」と答えてから、毎周 赤）。

    **＝ 検査が、守りたい決めではなく「いま在る1つの窓」を掴んでいた**という欠陥です。
    **守りたい決めは 1つ**: **引用（`>`）の外に落とした字は、`lines` に残り、`body` には出ない。**
    窓が開いていようが閉じていようが、この形は同じです。**だから形のほうを固定します。**

    **陽性対照を先に置きます**（この file の他の検査と同じ形）——
    **落ちるまで撃てる作り物**で、門が生きていることを先に見ます。

    **覆る条件**: `Block.body` が「`>` の中だけ」をやめたら（例: 全部 出すようになったら）、
    ここが鳴ります。そのときは **決めのほうが動いた**ので、`scripts/for_owner.py` の註を読むこと。
    """
    # (1) **陽性対照**: `>` の外の字は `lines` に在って `body` に無いこと
    b = for_owner.Block(
        "### 出す 2026-01-01 09:00〜10:00 JST",
        _DT(2026, 1, 1, 9), _DT(2026, 1, 1, 10), "",
        ["> 手順1: 画面をひらく", "", "**なぜ、これがいま一番大事か**: ここは親に出ない字です。"])
    assert "なぜ、これがいま一番大事か" in "\n".join(b.lines), "元の字を消していないこと"
    assert "なぜ、これがいま一番大事か" not in b.body, "その字は親に出ないこと"
    assert "手順1: 画面をひらく" in b.body, "引用の中は親に出ること"

    # (2) **実物**: いま在る窓ぜんぶで、`body` の行が **引用の行そのもの**だけであること。
    #     **「外の字が body に無い」では挟めません** —— 同じ文が引用の中にも外にも
    #     書かれている窓が実際に在り（`yt_quota_increase`）、字で挟むと偽陽性が出ます。
    #     **挟むのは出どころのほう**: body の各行は、必ずどれかの `>` 行を剥いだ字である。
    md = (ROOT / "docs/FOR_OWNER.md").read_text(encoding="utf-8")
    blocks, _ = for_owner.parse(md)
    assert blocks, "「出す」節に窓が 1つ もありません"
    for blk in blocks:
        quoted = {(ln[1:].lstrip(" ") if ln[1:2] == " " else ln[1:])
                  for ln in blk.lines if ln.startswith(">")}
        for ln in blk.body.splitlines():
            if ln.strip():
                assert ln in quoted, (blk.head, ln)
