"""`daily_pick.standing_form_conflict()` —— 立っている決めを、毎周 門の算と突き合わせる。

## なぜ要るか（2026-09-04・最適化の回）

`and_path_form()`（門の算）は在ったのに、呼ばれる場所が `outside_long_readout()` の
`"stop"` 枝の2か所だけで、その判定は外の作りの長尺に 24h の観測が要りました。
実測でその観測は 6本とも 0件 ＝ **門の算は一度も印字されていない。**
毎周 印字されていたのは立っている決めの `why`（＝前の回の散文）だけで、
`data/daily_pick.jsonl` は 09-03T02:03 から 11回 連続で同じ形を追認していました。

ここが守るのは 3つだけ:
  1. 立っている形と門の算が **同じなら 1行も出さない**（形を決め打ちしない）
  2. **違うときは必ず出す** —— 観測が 0件 でも、`outside_long_readout()` に関係なく
  3. 門の算が `None`（脚が立たない）なら 1行も出さない（推測で埋めない）
"""

from __future__ import annotations

import json

from src import daily_pick


def _cur(form: str = "長尺", topic: str = "t-1") -> dict:
    return {"form": form, "topic": topic, "video_id": "V1",
            "at": "2026-09-04T14:42:03+09:00", "why": "07:42 の決めを数字で追認"}


def test_agree_is_silent():
    """立っている形と門の算が同じ回は、1行も出さないこと（形を決め打ちしない）。"""
    out = daily_pick.standing_form_conflict(
        _cur("ショート"), form_call=lambda **k: ("ショート", "（検査の値）"))
    assert out == []


def test_disagree_names_both_forms_and_the_numbers():
    """食い違う回は、両方の形と門の算の理由と、上書きのコマンドを出すこと。"""
    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "道 ショート ＝ ×106・道 長尺 ＝ ×314"))
    body = "\n".join(out)
    assert "長尺" in body and "ショート" in body
    assert "×106" in body and "×314" in body
    # 上書きのコマンドは、門の算が返した形で出ること
    assert "--pick ショート nenkin" in body
    # 立っている `why` を根拠にしないと、はっきり言うこと
    assert "根拠にしない" in body


def test_no_leg_is_silent():
    """門の算が `None`（門1 の脚が立たない）回は、推測で埋めず 1行も出さないこと。"""
    out = daily_pick.standing_form_conflict(
        _cur(), form_call=lambda **k: (None, "脚が立ちません"))
    assert out == []


def test_no_standing_pick_is_silent():
    """まだ決めていない日は、突き合わせる相手が無いので 1行も出さないこと。"""
    assert daily_pick.standing_form_conflict(None,
                                             form_call=lambda **k: ("ショート", "x")) == []


def test_raising_gate_does_not_break_the_round():
    """門の算が飛んでも、回の印字を落とさないこと。"""
    def boom(**k):
        raise RuntimeError("shorts_subs.json が読めません")
    out = daily_pick.standing_form_conflict(_cur(), form_call=boom)
    assert len(out) == 1 and "出せませんでした" in out[0]


def test_chain_len_counts_the_trailing_same_form(tmp_path):
    """鎖の長さは、後ろから同じ形が続いている本数（形が変わったところで止まる）。"""
    p = tmp_path / "picks.jsonl"
    rows = [{"form": "ショート"}, {"form": "ショート"},
            {"form": "長尺"}, {"form": "長尺"}, {"form": "長尺"}]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert daily_pick._standing_chain_len(p) == 3


def test_chain_len_empty(tmp_path):
    """控えが空でも落ちないこと。"""
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert daily_pick._standing_chain_len(p) == 0


def test_lines_prints_the_conflict_when_a_pick_stands(monkeypatch, tmp_path):
    """`lines()` は、立っている決めの直後に食い違いの行を出すこと。

    ここが本体 —— `outside_long_readout()` の判定に関係なく出ること
    （観測が 0件 で判定が `None` の回でも出る、が直したかった穴）。
    """
    p = tmp_path / "picks.jsonl"
    day = daily_pick.for_day()
    p.write_text(json.dumps({
        "for_day": f"{day:%Y-%m-%d}", "form": "長尺", "topic": "nenkin",
        "video_id": "V1", "at": "2026-09-04T14:42:03+09:00",
        "why": "07:42 の決めを数字で追認"}, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(daily_pick, "and_path_form",
                        lambda **k: ("ショート", "道 ショート ＝ ×106・道 長尺 ＝ ×314"))
    st = lambda m: {"n": 10, "median": m, "p90": m, "max": m}     # noqa: E731
    cmp = {"rule": {"ショート": st(1049), "長尺": st(1)},
           "recent": {"ショート": st(110), "長尺": st(1)},
           "all": {"ショート": st(173), "長尺": st(1)},
           "life": {"ショート": st(200), "長尺": st(4)},
           "rows": []}
    out = daily_pick.lines(None, cmp=cmp, picks_path=p,
                           topics=set(), cands=[], untried=[])
    body = "\n".join(out)
    assert "食い違います" in body
    assert "×106" in body
    # 立っている `why` は「前の回の散文」と札を貼って出すこと
    assert "前の回の散文" in body


# ----------------------------------------------------------------------
# **[数] の行**（2026-09-04 16:4x に足した）
#
# `[!!]` は「どちらが正しいか」を言いません。実測 09/04 16:2x の回は、この行を読んでから
# **20分** かけて `config/hypotheses.yaml` の5脚の表まで降りて答えを出しました ——
# **門の算の負けている側（長尺）の分母 36本 に、外の型を全部 写した本が 0本**。
# **その 0本 は機械が数えられる**ので、`[!!]` の隣に出します。
# ----------------------------------------------------------------------


# **【2026-09-04 23:5x・最適化の回で、この検査は向きが変わりました】**
# 下の検査は `treated_call` が**どちらの形にも (0, 36) を返す**ので、
# 「立っている形の分母が処置 0本」と同時に「門の算の形の分母も処置 0本」です。
# それでも `[数]` は**立っている形の側にだけ**「処置 n=0 の分母で処置を落とさないこと」を
# 印字していました ＝ **同じ事実を、片側の逃げ道としてだけ配っていた。**
# 実測（09/04 23:5x に撃った）: `treated_count('長尺')=(0,36)`・`('ショート')=(0,216)` で
# **両方 0本**。そして `data/daily_pick.jsonl` の 33行 のうち **10行** が、
# この印字の文言（「処置 n=0 の分母で処置は落とせない」）を `why` に写して
# 門の算（ショート）を外し、09/05 は **21回 連続**で長尺に決め直されています。
# そのあいだ `data/eta.jsonl` の 再生/日(7d) は 6,299（08-25）→ **943**（09-04）。
# **いまは、両側とも 0本 の回は「この事実は形を選びません」と言い、
# 残った測った量（齢48h の中央値）を並べます。**


def test_両方の形とも処置0本なら片側の逃げ道にしない():
    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "道 ショート ＝ ×106・道 長尺 ＝ ×314"),
        treated_call=lambda form, **k: (0, 36))
    body = "\n".join(out)
    assert "両方の形が処置 0本" in body
    assert "どちらの形も選びません" in body
    # **片側だけの逃げ道の文言は、この枝では出ないこと**（出た瞬間に元の壊れ方に戻る）
    assert "処置 n=0 の分母で処置を落とさないこと" not in body


def test_相手側に処置が在るときだけ立っている形を守る():
    """**非対称のときは、元どおり立っている形の側を守ること。**

    `want`（門の算の形）の分母が処置を測れていて、`have` の側が 0本 なら、
    「その脚は処置ではない」は**本当に片側だけの事実**なので、そう言ってよい回です。
    """
    def _treated(form, **k):
        return (0, 36) if form == "長尺" else (9, 216)

    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "道 ショート ＝ ×106・道 長尺 ＝ ×314"),
        treated_call=_treated)
    body = "\n".join(out)
    assert "処置ではありません" in body
    assert "処置 n=0 の分母で処置を落とさないこと" in body
    assert "**9本 が処置ずみ**" in body


def test_中央値の対は測れない側を推測で埋めない():
    line = daily_pick._median_pair_line(
        "長尺", "ショート",
        median_call=lambda f: 1.0 if f == "長尺" else None)
    assert "長尺 1回" in line
    assert "ショート 測れず" in line


def test_処置が在るなら門の算を根拠にしてよいと言う():
    """**逆向きも出ること。** 片方しか出ないと、この行は「長尺を守る札」になります。"""
    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "x"),
        treated_call=lambda form, **k: (7, 36))
    body = "\n".join(out)
    assert "**7本**" in body
    assert "門の算のほうを根拠にしてよい" in body


def test_数えられない回は推測で埋めない():
    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "x"),
        treated_call=lambda form, **k: (0, 0))
    assert "推測で埋めないこと" in "\n".join(out)


def test_数えるほうが飛んでも回の印字を落とさない():
    def boom(form, **k):
        raise RuntimeError("控えが読めません")
    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "x"), treated_call=boom)
    assert "食い違います" in "\n".join(out)


def test_treated_count_は実物で数える():
    """**実物で撃つこと。** 2026-09-04 の実測は 長尺 (0, 36) ／ ショート (0, 216)。

    ここが見るのは「分母が 0 でないこと」と「写した本が分母を超えないこと」だけ ——
    数そのものは毎日 動きます（**写さないこと**）。
    """
    treated, total = daily_pick.treated_count("長尺")
    assert total > 0
    assert 0 <= treated <= total


def test_型を持たない題材は処置に数えない(monkeypatch):
    """`style: outside_long` でない題材は、写しようがないので処置の外。"""
    monkeypatch.setattr(daily_pick, "aged_views",
                        lambda *a, **k: [{"video_id": "V1", "form": "長尺", "topic": "t-plain"}])
    monkeypatch.setattr(daily_pick, "_topics", lambda: [{"id": "t-plain", "style": None}])
    assert daily_pick.treated_count("長尺") == (0, 1)


# ----------------------------------------------------------------------
# **枠の代金**（2026-09-04 23:5x・最適化の回）
# 枠は 1日 1本 なので、試す本を1本 出すことは別の形を1本 出さないこと。
# ところが前提の当たりの門（`OUTSIDE_48H_GATE` ＝ 100回）は「自分の記録の何倍か」
# だけで置かれ、**譲る側の実測と並べた回が1度もありませんでした。**
# 実測（この回に撃った）: `form_median_48h('ショート')` ＝ 164回 ＞ 門 100回
# ＝ **当たっても、譲ったショートの中央値に届きません。**
# ----------------------------------------------------------------------


def test_当たりの門が譲る側の中央値より低いなら枠の代金を払えないと言う():
    out = daily_pick.win_pays_for_slot(
        "ショート", gate=100.0, median_call=lambda f: 164.0)
    body = "\n".join(out)
    assert "当たっても枠の代金を払えません" in body
    assert "100回" in body and "164回" in body


def test_門が譲る側より上なら1行も出さない():
    """**当たれば代金を払える回は、この行は自分で消えること。**"""
    assert daily_pick.win_pays_for_slot(
        "ショート", gate=500.0, median_call=lambda f: 164.0) == []


def test_譲る側が読めない回は推測で埋めない():
    for bad in (None, 0, float("nan")):
        assert daily_pick.win_pays_for_slot(
            "ショート", gate=100.0, median_call=lambda f, b=bad: b) == []
    assert daily_pick.win_pays_for_slot(
        "ショート", gate=100.0,
        median_call=lambda f: (_ for _ in ()).throw(RuntimeError("読めない"))) == []
