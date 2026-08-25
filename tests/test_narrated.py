"""`src/narrated.py` —— 読み上げが言った数が、絵に出ているか。

**故障注入を両向きに掛けます。** 当たりを見つけることと、
**当たっていないものを鳴らさないこと**は別の性質で、片方だけでは
「全部鳴らす検査」と区別がつきません（`docs/JOURNAL.md` 2026-08-16）。

実データ（`data/critique_queue/` の投稿済み84本）にも当てます。
**この道具を入れた根拠そのものが実測**なので、数が動いたら気づけるようにします。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src import narrated

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / "data" / "critique_queue"


# ---- 数の読み方 ----------------------------------------------------------

@pytest.mark.parametrize("tok,value", [
    ("1,000", 1_000),
    ("2万3000", 23_000),
    ("16万1782", 161_782),
    ("20万1千", 201_000),
    ("42万5千", 425_000),
    ("1億5000万", 150_000_000),
    ("1億5千万", 150_000_000),      # **同じ値。表記だけ違う**
    ("3億2万5千", 300_025_000),
])
def test_値に直せる(tok, value):
    got = narrated.parse(tok)
    assert got is not None, f"{tok} が読めていません"
    assert got[0] == pytest.approx(value)


def test_右の大きい位は左へ掛かる():
    """`1億5千万` の `5千` は 5,000 ではなく 5,000万。

    **左から順に足す書き方だと、ここで必ず落ちます**（2026-08-17 に踏んだ）。
    落ちると `1億5000万` と読んだ動画が「画面に無い」と誤報になります。
    """
    assert narrated.parse("1億5千万")[0] == narrated.parse("1億5000万")[0]


def test_言った桁の大きさを返す():
    """丸めて言うのは欠陥ではないので、**どこまで言ったか**が要ります。"""
    assert narrated.parse("16万")[1] == 10_000       # 16万〜17万のどこか
    assert narrated.parse("16万1782")[1] == 1        # 1円まで言った
    assert narrated.parse("42万5千")[1] == 1_000


# ---- 通す・鳴らす --------------------------------------------------------

def _bars(*pairs) -> list[dict]:
    return [{"kind": "chart", "headline": "",
             "bars": [{"label": lab, "display": disp} for lab, disp in pairs]}]


def test_絵にある数は鳴らさない():
    assert narrated.unshown("4日休むと6667円です", _bars(("4日休む", "6667円"))) == []


def test_丸めて言ったものは鳴らさない():
    """`16万円台` に対して画面が `16万1782円` —— **食い違っていません。**

    実物4件（`470i0hhnRx0` `hKCwPvuqviw` `KPGuqj5v1Qs` ほか）がこの形でした。
    ここを鳴らすと、**耳で7桁を読み上げる動画**しか通らなくなります。
    """
    frames = _bars(("医療費1000万円のとき", "16万1782円"))
    assert narrated.unshown("医療費1000万円でも残るのは16万円台。", frames) == []


def test_表記がちがうだけのものは鳴らさない():
    frames = _bars(("課税価格", "1億5千万"))
    assert narrated.unshown("1億5000万円なら1495万円。", frames) == ["1495万"]


def test_絵に無い数は鳴らす():
    """**故障注入**: 画面に出していない答えを読み上げに足す。"""
    frames = _bars(("70歳から", "1609万5643円"), ("65歳から", "1560万円"))
    assert narrated.unshown("85歳までの手取り差は49万5643円。", frames) == ["49万5643"]


def test_1000未満は見ない():
    """年・日数・等級番号・率。**下げると誤報だけが増えます**（`premise.py` と同じ）。"""
    assert narrated.unshown("42万5千円からは25等級です", _bars(("上限", "42万5千円"))) == []


def test_描かれていない棒は画面に数えない():
    """`scale_bars` は軸を固定するための控えで、**そのコマには描かれていません。**"""
    frames = [{"kind": "chart", "headline": "", "bars": [],
               "scale_bars": [{"label": "30日休む", "display": "18万9円"}]}]
    assert narrated.unshown("30日休むと18万9円です", frames) == ["18万9"]


# ---- 文と絵の対応 --------------------------------------------------------

def test_数が合わないときは見送る():
    """当てずっぽうで突き合わせない。"""
    assert narrated.scan(["a", "b"], [_bars(("x", "1円"))]) == []


def test_文ごとに当てる():
    got = narrated.scan(["差は49万5643円です"], [_bars(("累計", "1560万円"))])
    assert len(got) == 1 and "49万5643" in got[0]


# ---- 実データ ------------------------------------------------------------

def _books() -> list[tuple[str, list[str], list[dict]]]:
    out = []
    for meta_path in sorted(Q.glob("*.json")):
        if meta_path.name.endswith(".plan.json"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        plan_path = Q / f"{meta['video_id']}.plan.json"
        if not plan_path.exists():
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if isinstance(plan, list):
            out.append((meta["video_id"], meta.get("narration") or [], plan))
    return out


#: **読み上げが、絵に無い数を言っている本。** 増えたら目で確かめてから足すこと。
#:
#: 2026-08-17（84本 / 491行 → 4件・3本）に入れました。
#: **2026-08-26 に 3本 増えています。3本とも中身を見ました**（下の2つの型）。
KNOWN_UNSHOWN = {
    "9hqzUxqBjBE", "WSJAjK1Xo-I", "YBZFmrsL_kk",
    # --- 2026-08-26 に増えたぶん ---
    #
    # **(型1) 前提の言い直し。** 絵は**年額 21万120円**を出しているのに、
    # 読み上げが **月額 1万7510円**も言います（21万120 ÷ 12 の元の数）。
    # **同じ文が2本に出ています**（「国民年金保険料は月額…、年額…としています」）
    # ＝ 台本の型のほうです。次に触る回は `src/script_writer.py` の
    # 前提の言い回しを見ること —— **絵に出ている側（年額）だけ言えば消えます。**
    "DyEcaMK5ZU8", "mRisqvcqmm4",
    # **(型2) こちらは前提ではなく「答え」です。害が別物なので分けて書きます。**
    # 「還付にすると **2万5262円**、5年分では **12万6310円**」——
    # **どちらも絵に1度も出ません。** `CLAUDE.md` の根幹は
    # 「前提と計算式を、画面と説明欄に全部出す」で、**視聴者が追試できること**が
    # テンプレート量産との違いです。**答えを声だけで言うのは、その根幹に反します。**
    # 型1（前提の言い直し）より優先して直すこと。
    "plmBPZqqP1U",
    # --- 2026-08-26 夜（最適化の回）に、**理由が分かったので足したぶん** ---
    #
    # 8/26 朝の申し送りは、この4本を「**生きている漏れ**」と書き、
    # 「**門が通した理由が分からないまま allowlist に入れると、次の本も
    # 同じように通る**」として足すのを見送っていました。**理由は分かりました。**
    #
    # **門は長尺に1度も掛かっていませんでした。** `verify.check` が
    # `_check_narrated_shown` を `if portrait:` の中に置いていて、`portrait` は
    # `video_cfg["resolution"]` から来ます（＝ `--short` を付けたときだけ縦）。
    # **この4本は全部 長尺**です。控え430本で数えると、門が入った 08/17 より後の
    # 漏れは **ショート 0/397・長尺 7/33（21%）＝ 100% が長尺**でした。
    #
    # 申し送りが「4本とも縦なのに素通りした」と読んだ根拠は
    # `critique_queue` の `orientation` ですが、あれは
    # `script.get("short", True)` で、**台本に `short` という鍵はありません。**
    # 既定の `True` が必ず出るので、**控え469本が469本とも「縦」**です。
    # **向きではなく定数**でした（向きを見るならコマ数と文の数を比べること）。
    #
    # 同じ回に `verify` 側を `portrait` の外へ出し、
    # `script_writer.long_script_problems` にも入れました。**4本とも本物**です
    # （読み上げの数が `narrated.shown_values()` に1つも無い）:
    "a63FzIUV2wI",   # (型2) 声で言った 1544万8761 を、図が1点も持っていない
    "jeRBnxQjBvY",   # (型1) 公的年金等控除の適用条件 330万・110万 が画面に無い
    "jYoDuz0S9z4",   # (型1) 3級の最低保障から導いた 81万6000 が画面に無い
    "xQ2EzmkHRjw",   # (型2) 控除前の所得税額 37万2500 が画面に無い
}

#: **門が入る前に出た本**（`10d0028` 2026-08-16 17:42 より前）。
#: この3本は「門が漏らした」ではなく「まだ門が無かった」側です。
#: 下の `test_門は長尺にも掛かっている` が、その区別を使います。
BEFORE_GATE = {"9hqzUxqBjBE", "WSJAjK1Xo-I", "YBZFmrsL_kk"}


def test_実物で当たりが_見た本に収まっている():
    """**入れた根拠が実測です。**

    ここが増えたら、増えたぶんを**目で確かめてから** `KNOWN_UNSHOWN` に足すこと。
    減ったら、直った本があるということです（同じく確かめてから外すこと）。
    **数だけ緩めないこと** —— ID で持っているのは、
    「新しく増えた本」と「直った本」を区別するためです。
    """
    books = _books()
    assert len(books) >= 60, f"実物が {len(books)}本 しかありません"
    bad = {vid for vid, narr, plan in books
           if any(narrated.unshown(line, plan) for line in narr)}
    assert bad == KNOWN_UNSHOWN, sorted(bad)


def test_実物に故障を注入すると鳴る():
    """**当たりを見つける側**。無傷の本の読み上げに、絵に無い数を1つ足す。"""
    # **一覧を2か所で持たないこと**（2026-08-26 に寄せた）。ここは長らく
    # 上と同じ3件を書き写していて、**上だけ増やすと、こちらは増えた本を
    # 「無傷」として拾い**、注入する前から鳴ってしまいます。
    books = [b for b in _books() if b[0] not in KNOWN_UNSHOWN]
    assert books
    vid, narr, plan = books[0]
    hurt = list(narr) + ["差は98万7654円です"]
    assert any(narrated.unshown(line, plan) for line in hurt), vid


def test_文ごとに当てると厳しすぎる():
    """**採らなかった側を、数字で残しておく**（`docs/trigger_main.md` の決まり）。

    文ごとだと 13本が落ちます。抜き取った2件はどちらも**隣の文の絵**に
    出ていました。**誤報は不投稿**なので、確かめていない厳しさは置きません。
    """
    def groups(plan: list[dict]) -> list[list[dict]]:
        out: list[list[dict]] = []
        last = None
        for f in plan:
            h = re.sub(r"[　 ](＋.*|\d+/\d+)$", "", f.get("headline") or "")
            if h != last:
                out.append([])
                last = h
            out[-1].append(f)
        return out

    per_segment = {vid for vid, narr, plan in _books()
                   if narrated.scan(narr, groups(plan))}
    whole = {vid for vid, narr, plan in _books()
             if any(narrated.unshown(line, plan) for line in narr)}
    assert whole < per_segment
    assert len(per_segment) >= 10, len(per_segment)


def test_暦の年は量として数えない():
    """**`2026年4月分` の `2026` を「絵に無い数」と言わないこと**（2026-08-20 に踏んだ）。

    `UHo79-HCOWo` の前提の文がこれで鳴りました。画面に出しているのは
    「令和8年度」のほうで、**西暦は出しません。** 欠陥ではなく誤報です。

    締めているのは3つとも同時（4桁ちょうど・区切りも位もない・直後が「年」）
    なので、**`2026円` も `2,026年` も `2026万円` も、これまでどおり見ます。**
    """
    toks = [t for t, _, _ in narrated.numbers("令和8年度、2026年4月分からの額です")]
    assert "2026" not in toks
    assert [t for t, _, _ in narrated.numbers("2026円の差")] == ["2026"]
    assert [t for t, _, _ in narrated.numbers("2,026年ぶん")] == ["2,026"]
    assert [t for t, _, _ in narrated.numbers("2026万円")] == ["2026万"]


# ---- **門が長尺にも掛かっていること**（2026-08-26 に実測して足した）------------
#
# ここが本体です。上の一覧は「漏れた本」を数えるだけで、
# **漏れた理由**（門が長尺に掛かっていなかった）は数えません。
# 理由のほうを固定しないと、次に `verify.check` を触った回が
# `_check_narrated_shown` を `if portrait:` の中へ戻して、**また静かに全部通します。**

def test_門は長尺にも掛かっている():
    """`verify.check` が `if portrait:` の**外**でこの検査を呼ぶこと。

    2026-08-26 まで中にありました。`portrait` は動画の実物ではなく
    `video_cfg["resolution"]` から来る（＝ `--short` を付けたときだけ縦）ので、
    **長尺は1本も通っていませんでした。**

    実測（`data/critique_queue/` 430本・門が入った 08/17 より後）:

        ショート（コマ>文）  397本 → 漏れ **0本**
        長尺  （コマ=文）     33本 → 漏れ **7本（21%）**

    `CLAUDE.md`「**4,000時間の門に入るのは長尺だけ**」＝
    **収益化を背負っている側だけが無検査**でした。

    **見るのは字ではなく、字の位置です** —— 呼び出しが `if portrait:` の
    ぶら下がりより浅い字下げにあること。並べ替えでは落ちません。
    """
    import inspect
    import textwrap

    from src import verify

    src = textwrap.dedent(inspect.getsource(verify.check))
    depth = None
    called_at = None
    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if line.startswith("if portrait:"):
            depth = indent
            continue
        if depth is not None and indent <= depth:
            depth = None            # ぶら下がりが終わった
        if "_check_narrated_shown(" in line:
            called_at = (indent, depth)
    assert called_at is not None, "`verify.check` がこの検査を呼んでいません"
    _indent, inside = called_at
    assert inside is None, (
        "`_check_narrated_shown` が `if portrait:` の中にあります。"
        "**長尺が素通りします**（実測 7/33 = 21%）"
    )


def test_台本の段でも掛かっている():
    """**生成中に直させる口**があること（`script_writer.long_script_problems`）。

    `verify` だけに置くと、当たるのは `claude -p` 約250秒＋合成＋レンダリングの
    **後**で、そこには直す口がありません ＝ **1本まるごと捨て**。
    ここに置けば同じセッションが3回まで書き直せます
    （`_check_not_repeat` を 2026-08-24 にここへ移したのと同じ形）。

    **`work/slides_plan.json` はまだ無い**ので、`verify._plan_frames` が
    台本の `visual` で代用します。長尺は割らないので、同じものです。
    """
    from src import script_writer

    class _V:
        def __init__(self, d):
            self._d = d
            self.headline = d.get("headline", "")
            self.kind = d.get("kind", "")

        def model_dump(self):
            return dict(self._d)

    class _S:
        def __init__(self, seg):
            self.narration = seg["narration"]
            self.visual = _V(seg["visual"])

        def model_dump(self):
            return {"narration": self.narration,
                    "visual": self.visual.model_dump()}

    class _Script:
        def __init__(self, d):
            self.segments = [_S(s) for s in d["segments"]]
            self._d = d

        def model_dump(self):
            out = dict(self._d)
            out["segments"] = [s.model_dump() for s in self.segments]
            return out

    def _script(narration: str) -> _Script:
        return _Script({
            "title": "手取りはいくら減るか",
            "segments": [
                {"narration": narration,
                 # **`display` に入れること。** `narrated.shown_values()` は
                 # `label` と `display` を読み、`value`（棒の長さ）は読みません
                 # —— 画面に字として出るのはそちらだからです。
                 "visual": {"kind": "chart", "headline": "年収べつの手取り",
                            "bars": [{"label": "300万円", "value": 2_412_000,
                                      "display": "241万2000円"},
                                     {"label": "400万円", "value": 3_161_000,
                                      "display": "316万1000円"}]}},
            ],
        })

    said_on_screen = script_writer.long_script_problems(
        _script("300万円の手取りは241万2000円です"))
    said_nowhere = script_writer.long_script_problems(
        _script("300万円の手取りは241万2000円で、差は98万7654円です"))

    hit = "画面のどこにも出ていません"
    assert not [p for p in said_on_screen if hit in p], said_on_screen
    absent = [p for p in said_nowhere if hit in p]
    assert absent, said_nowhere
    assert "98万7654" in absent[0], absent
