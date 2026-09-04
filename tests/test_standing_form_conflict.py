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


def test_処置が0本なら分母が処置を測っていないと言う():
    out = daily_pick.standing_form_conflict(
        _cur("長尺", "nenkin"),
        form_call=lambda **k: ("ショート", "道 ショート ＝ ×106・道 長尺 ＝ ×314"),
        treated_call=lambda form, **k: (0, 36))
    body = "\n".join(out)
    assert "36本" in body and "0本" in body
    assert "処置ではありません" in body
    assert "処置 n=0 の分母で処置を落とさない" in body


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
