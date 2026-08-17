"""**総覧の節が、割り当てを全部吸い込む形**（2026-08-18 に実測して足した）。

`realign` は「一致数が厳密に多い節へ貼り直す」で動きます。ところが
**全部の行を1つの表に並べた節**（総覧）は、他の節の数字を丸ごと持っているので、
**どの題に対しても一致数が最大**になります。すると割り当てがどこであっても
そこへ吸い込まれ、`survey()` から見て**残りの節は永久に未使用**になります。

実測（`src/calc/keihi.py` を足した回）—— `--count 1` を6回まわして
**6回とも同じ節に割り当てられ、6件とも総覧へ貼り直され**、
**5件は言っていることまで同じ**でした（同じ2つの数字の逆転）。
「続けて数本見たときに繰り返しに感じられる」判定に、そのまま当たります。
"""
from __future__ import annotations

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "topic_forge", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)


class _Item:
    def __init__(self, tid, title, angle):
        self.id, self.title_seed, self.angle = tid, title, angle


class _Set:
    def __init__(self, topics):
        self.topics = topics


def _sections():
    """1節目が総覧。**2節目の数字を丸ごと含み、さらに多い。**"""
    return {
        "=== 総覧 ===": ("所得 7,000,000円 値打ち 4,533円 正味 5,467円\n"
                        "所得 9,000,000円 値打ち 4,308円 正味 5,692円"),
        "=== 逆転 ===": "所得 7,000,000円 45.33% ＞ 所得 9,000,000円 43.08%",
    }


def test_総覧の節は一致数が多くても割り当てを奪わない():
    item = _Item("s-x-gyakuten", "所得700万と900万で経費の効きが逆転する",
                 "主役の数字は、所得700万円のとき45.33%、所得900万円のとき43.08%。"
                 "その差2.25ポイントだけを言う")
    got = forge.realign(_Set([item]), [("m", "=== 逆転 ===")], {"m": _sections()}, [])
    assert got == [("m", "=== 逆転 ===")]


def test_部分的に重なっているだけなら今までどおり貼り直す():
    """**総覧かどうかで分けています。**「一致が多い＝動かさない」ではありません。"""
    sections = {"=== A ===": "40日 と 120時間", "=== B ===": "40日 と 250時間"}
    item = _Item("s-x-250", "40日と250時間", "主役は250時間。片方の節にしか出ない")
    got = forge.realign(_Set([item]), [("m", "=== A ===")], {"m": sections}, [])
    assert got == [("m", "=== B ===")]


def test_swallows_は節どうしの包含だけを見る():
    s = _sections()
    assert forge.swallows(s, "=== 総覧 ===", "=== 逆転 ===")
    assert not forge.swallows(s, "=== 逆転 ===", "=== 総覧 ===")


def test_割り当ての無い余りの件には掛からない():
    """比べる相手が無いので、**総覧へ落ちるのが正しい。**"""
    first = _Item("s-x-gyakuten", "所得700万と900万で経費の効きが逆転する",
                  "主役の数字は、所得700万円のとき45.33%、所得900万円のとき43.08%。"
                  "その差2.25ポイントだけを言う")
    amari = _Item("s-x-amari", "所得700万で経費1万円は4,533円ぶん",
                  "主役の数字は4,533円と正味5,467円。所得700万円のときの値打ち")
    got = forge.realign(_Set([first, amari]),
                        [("m", "=== 逆転 ==="), (None, None)],
                        {"m": _sections()}, [])
    assert got == [("m", "=== 逆転 ==="), ("m", "=== 総覧 ===")]


def test_実物の_keihi_で総覧が他の節を飲み込む形になっている():
    """**この検査が緑のまま落ちたら、表の作りが変わったということ。**"""
    sections = forge.sections("keihi")
    heads = list(sections)
    assert forge.swallows(sections, heads[0], heads[1])
