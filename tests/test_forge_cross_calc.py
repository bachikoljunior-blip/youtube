"""**ずれるのは節だけではありません。calc ごとずれます。**

2026-08-25 に実物で踏んだ穴です。`--count 5`（kokuho・kaigo・taishoku・
tsukin・zangyo）を頼んだところ、書き手が **4件しか返さず**、
2件目から**まるごと1つずれました**:

    書いた中身        貼られた calc     直しの前の結果
    kokuho の節       kokuho            ✓
    zangyo の節       kaigo             ✗ 一致1で「当たった」ことになり、通る
    kaigo の節        taishoku          ✗ 同上
    taishoku の節     tsukin            ✗ 同上

`realign` は **`all_sections[mod]` の中だけ**を探し直していたので、
**calc そのものがずれた件は、どこにも直しようがありませんでした。**
`top == 0` の門も止めません —— `20` のようなありふれた数はどの表にも出るので、
**別の calc でも一致1が出ます。**

`calc_sections` は画面に出す表そのものを選ぶ鍵（`src/script_writer.py`）なので、
すり抜ければ **語っている制度と、画面に出る表が別の制度**になります。

ここで使っている題と狙いは、**そのとき実際に返ってきた文そのもの**です。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)


class _Item:
    def __init__(self, tid: str, title: str, angle: str):
        self.id, self.title_seed, self.angle = tid, title, angle


class _Set:
    def __init__(self, topics):
        self.topics = topics


# ---- 2026-08-25 に実際に返ってきた文（`--count 5 --dry-run` の出力そのもの）----
ZANGYO_TEXT = (
    "年間休日105日と125日で残業代が年43,269円ちがう",
    "ショート。1つのことだけ言う。主役の数字は、年間所定休日が20日ちがうと"
    "残業代の年額が43,269円ちがうこと。前提として「月給300,000円・一律手当なし・"
    "1日所定8.0時間・残業月20時間・どちらの会社も正しく計算」を画面に出す。"
    "単価2,163円と2,344円を並べ、105日の会社は125日の1時間に届くのに"
    "1.0833時間かかると添える。1枚目は「休みが多い会社は残業も高い」（22文字以内）。",
)


def _sections(module: str) -> dict[str, str]:
    """実物の `src/calc/` から節を取る。**突き合わせる相手は本物でないと意味がない。**"""
    return forge.sections(module)


def test_calcごとずれた件を中身の数字で貼り直す():
    """zangyo の題が kaigo に貼られている。**zangyo へ戻ること。**"""
    item = _Item("s-zangyo-kyujitsu-43269", *ZANGYO_TEXT)
    all_sections = {m: _sections(m)
                    for m in ("kokuho", "kaigo", "taishoku", "tsukin", "zangyo")}
    # この回で頼んだ5つの calc。`picked` は「書かせた順」なので、ずれている
    picked = [("kaigo", list(all_sections["kaigo"])[0])]
    for m in ("kokuho", "taishoku", "tsukin", "zangyo"):
        picked.append((m, list(all_sections[m])[0]))
    dropped: list[str] = []
    got = forge.realign(_Set([item]), picked, all_sections, dropped)

    assert dropped == []
    assert got[0] is not None
    mod, head = got[0]
    assert mod == "zangyo", f"calc が直っていません: {mod}"
    assert "年間所定休日" in head, f"節が中身と合っていません: {head}"


def test_正しく貼られている件は動かさない():
    """同じ題を **zangyo に正しく貼った**状態で渡す。**1文字も動かないこと。**"""
    item = _Item("s-zangyo-kyujitsu-43269", *ZANGYO_TEXT)
    all_sections = {m: _sections(m)
                    for m in ("kokuho", "kaigo", "taishoku", "tsukin", "zangyo")}
    right = next(h for h in all_sections["zangyo"] if "年間所定休日" in h)
    picked = [("zangyo", right)]
    for m in ("kokuho", "kaigo", "taishoku", "tsukin"):
        picked.append((m, list(all_sections[m])[0]))
    got = forge.realign(_Set([item]), picked, all_sections, [])
    assert got[0] == ("zangyo", right)


def test_1個差ではcalcをまたがない(monkeypatch):
    """**弱い証拠で動かさない。** 制度の定数は calc をまたいで同じ数が出る。

    `CROSS_MARGIN` を1に下げれば動くことを確かめて、
    **既定の2では動かない**ことを裏から示します。

    ## **`money_owner` を黙らせてから測ること**（2026-08-30 に足した）

    2026-08-30 に、`realign` の**手前**へもう1つ門が入りました
    （`money_owner` —— 貼られた calc が題の**金額を1つも持たない**ときだけ動かす。
    `tests/test_forge_money_owner.py`）。**あちらは段をそろえて見るので、
    この題では正しく `zangyo` を名指しします**（kaigo は金額0個・zangyo は4個）。

    つまり**この検査の題は、もう `CROSS_MARGIN` まで届きません。**
    そのままだと、この検査は「`money_owner` が動いた」ことを見て
    **`CROSS_MARGIN` について何も言わなくなります** ——
    名前と中身が食い違う検査は、`best_section` の docstring が
    3回 記録している事故と同じ形です。

    **だから、ここでは手前の門を黙らせます。** 測る対象は `CROSS_MARGIN` だけ。
    **緩めてはいません** —— 実物では手前の門が先に、より強い証拠で答えます。
    """
    item = _Item("s-zangyo-kyujitsu-43269", *ZANGYO_TEXT)
    all_sections = {m: _sections(m) for m in ("kaigo", "zangyo")}
    kaigo_head = list(all_sections["kaigo"])[0]
    picked = [("kaigo", kaigo_head), ("zangyo", list(all_sections["zangyo"])[0])]

    scores = {m: forge.best_section(f"{item.title_seed} {item.angle}",
                                    all_sections[m])[0][0]
              for m in ("kaigo", "zangyo")}
    assert scores["zangyo"] >= scores["kaigo"] + forge.CROSS_MARGIN, (
        f"この題では差が {scores} しかなく、この検査が何も言えていません")

    monkeypatch.setattr(forge, "money_owner", lambda *a, **k: None)
    old = forge.CROSS_MARGIN
    try:
        forge.CROSS_MARGIN = scores["zangyo"] - scores["kaigo"] + 1
        got = forge.realign(_Set([item]), picked, all_sections, [])
        # **`None`（落とす）も「またがなかった」です**（2026-08-25 22:xx）。
        # 割合の門が入る前は、`kaigo` での一致が偶然1個あったので
        # **間違った calc に貼られたまま残っていました。** いまは
        # 「この calc の表が裏付けていない」＝ 0 なので落ちます。
        # **落ちるほうが安全側です** —— 語る制度と画面の表が別物になりません。
        assert got[0] is None or got[0][0] == "kaigo", "差が足りないのに calc をまたいだ"
    finally:
        forge.CROSS_MARGIN = old


def test_金額の門は_CROSS_MARGIN_より先に効く():
    """2026-08-30 に足した順番そのものを固定する。

    同じ題・同じ `picked` で、**手前の門だけで `zangyo` に戻ること**
    （`CROSS_MARGIN` をあり得ない大きさにしても動くこと）。
    """
    item = _Item("s-zangyo-kyujitsu-43269", *ZANGYO_TEXT)
    all_sections = {m: _sections(m) for m in ("kaigo", "zangyo")}
    picked = [("kaigo", list(all_sections["kaigo"])[0]),
              ("zangyo", list(all_sections["zangyo"])[0])]
    old = forge.CROSS_MARGIN
    try:
        forge.CROSS_MARGIN = 999
        got = forge.realign(_Set([item]), picked, all_sections, [])
        assert got[0] is not None and got[0][0] == "zangyo"
    finally:
        forge.CROSS_MARGIN = old
