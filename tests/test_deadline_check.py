"""`scripts/deadline_check.py` —— **期限が、データの来る日より前に置かれていないか。**

なぜこの検査が要るか（2026-08-25）。この道具が無かったあいだ、
**判定できないと最初から決まっている期限**が並んでいました:

    「量産テンプレート判定を避けられる」  期限 09/01・条件は「収益化の審査に落ちる」
                                          申請には登録者1,000人 → あと 999人
    「冒頭の stat は前提を先」            期限 09/05・処置群の16本目の公開は 09/01
                                          落ち着く7日 ＋ 遅れ3日 → 判定できるのは 09/11

**期限が来た日に「まだ分からない」と言うことが、置いた時点で決まっていました。**
`scripts/drift.py` が出す「直近20回の verdict 0件」は、その帰結です。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as J  # noqa: E402


def _open_items() -> list[dict]:
    items = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return [h for h in items["hypotheses"] if not h.get("closed_on") and not h.get("verdict")]


def test_開いている前提には全部_needs_が書いてある():
    """**`needs:` の無い前提を足さないこと。**

    期限は、置いた回の勘では決められません。「その日までにデータが在るか」を
    書かずに置くと、**判定できない期限が黙って積みます**（実測: 16件中16件）。
    """
    missing = [h["claim"][:40] for h in _open_items() if not h.get("needs")]
    assert not missing, f"`needs:` が無い前提: {missing}"


def test_期限が_判定できる日より前に置かれていない():
    """**この検査が落ちたら、期限を延ばすこと。`falsified_if` は緩めないこと。**

    緩めると、外れない条件になります（このファイルが防ごうとしているのは
    「判定しないまま持ち越す」ほうで、「甘く判定する」ほうではありません）。
    """
    vs = J.check(_open_items())
    slips = [f"{v.claim[:32]} 期限 {v.deadline} < 判定できる日 {v.ready}"
             for v in vs if v.slips]
    assert not slips, "期限が早すぎる前提: " + " / ".join(slips)


def test_yaml_の_on_を_真偽値として読ませない():
    """**YAML 1.1 は `on:` を `True` として読みます。**

    最初この欄を `on:` にして、値がまるごと消えました（`需要 needs` の4件が
    `on が読めません` になった）。**同じ形の穴です** ——
    書いた欄と、読まれる欄が違いました。
    """
    raw = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert "\n        on: " not in raw, "`on:` は YAML で True になります。`on_date:` にすること"
    parsed = yaml.safe_load(raw)
    for h in parsed["hypotheses"]:
        for n in h.get("needs") or []:
            assert True not in n, f"`on:` が真偽値の鍵になっています: {h['claim'][:30]}"


def test_遅れを必ず足す():
    """**「公開から7日」に Analytics の遅れを足さないと、4日ぶんで判定します。**"""
    a = J._ans_published_group(
        {"created_after": "1970-01-01", "count": 1, "settle_days": 7}, date(2026, 8, 25), lag=3)
    b = J._ans_published_group(
        {"created_after": "1970-01-01", "count": 1, "settle_days": 7}, date(2026, 8, 25), lag=0)
    assert a.ready is not None and b.ready is not None
    assert a.ready - b.ready == timedelta(days=3)


def test_遅れが読めないときは_0_に倒れない():
    """**遅れを 0 と言い切るのが、いちばん危ない側です。**"""
    assert J.FALLBACK_LAG_DAYS > 0


def test_外の出来事は_判定できる日を出さない():
    a = J.answer({"kind": "external", "what": "収益化の審査"}, date(2026, 8, 25), 3)
    assert a.ready is None and a.unreachable


def test_0本のまま来ないのは_宣言したときだけ():
    """まだ公開していない本の再生は、いま 0 でも後から積みます。
    **`zero_means_never` を書いたときだけ**「来ません」と言うこと。"""
    base = {"kind": "accrual", "count_expr": "0", "need": 8, "since": "2026-08-23"}
    assert not J.answer(dict(base), date(2026, 8, 25), 3).unreachable
    assert J.answer({**base, "zero_means_never": True}, date(2026, 8, 25), 3).unreachable


def test_伸び率から解いた日は帯で見る():
    """**推定の日を点で見ると、書き換えの churn が毎回1件生まれます**（2026-08-26）。

    実例: 同じ前提の判定日が 11-13 → 11-09 → 11-16 → 11-22 と動き、
    そのたびに「期限がずれています」と言われて期限だけを3回書き換えました。
    **動いたのは伸び率の見積りで、届く日は1日も動いていません。**
    """
    need = {"kind": "accrual", "count_expr": "74", "need": 1000, "since": "2026-08-19"}
    a = J.answer(need, date(2026, 8, 26), 3)
    assert a.slack > 0, "伸び率から解いた日には、必ず帯を付けること"
    v = J.Verdict("t", a.ready + timedelta(days=a.slack - 1), a.ready, [a])
    assert not v.slips and not v.waits, "**帯の中の期限を「ずれ」と言わないこと**"
    far = J.Verdict("t", a.ready + timedelta(days=a.slack + 5), a.ready, [a])
    assert far.waits == 5, "帯の外に出たぶんだけを、待ちとして数えること"
    early = J.Verdict("t", a.ready - timedelta(days=a.slack + 3), a.ready, [a])
    assert early.slips, "帯の外に早すぎる期限は、これまでどおり止めること"


def test_点で決まる要件の帯は_遅れのゆらぎちょうど():
    """**帯は推定にだけ。** ——ここまでは正しく、そのままです。

    **ただし「予約の実物から数えた日」に、推定が1つ混ざっていました**（2026-08-26）。
    `_ans_published_group` が返すのは

        （台帳にある本当の公開日）＋ 落ち着く日数 ＋ **実データの遅れ**

    で、最後の項は実物ではありません。**遅れは1日の中で動きます** ——
    Analytics が日の途中で新しい日を出すからで、実測（438観測）は
    **3日が 381・4日が 57、1日のうちに両方を見た日が 6日**あります。

    この行はもともと `slack == 0` を要求しており、その結果
    `deadline_check` は**遅れを足す種類の前提を、走った時刻しだいで
    毎回「期限が1日 ずれています。縮めること」と言って**いました。
    実測（2026-08-26 06:0x）: そう言われた **5件が5件とも遅れを足す種類**
    （`after` ×2・`group_key` ×2・`published_group` ×1）。**例外なし。**
    書き換えれば、早い時刻に走った次の回が逆向きに書き換えます ——
    `Answer.slack` の docstring がまさに禁じている churn です。

    **だから 0 ではなく「遅れのゆらぎ ちょうど」を要求します。**
    台帳の側（公開日・本数）には幅を付けません —— そこは実物なので、
    幅を付けると本物の待ちが見えなくなります。**元の意図はそちらでした。**
    """
    band = J.analytics_lag_band()
    a = J._ans_published_group(
        {"created_after": "1970-01-01", "count": 1}, date(2026, 8, 25), lag=3)
    assert a.slack == band, "帯は、遅れのゆらぎ ちょうど（台帳の側に幅を付けない）"


def test_遅れを足す種類は_1日のずれを_ずれと言わない():
    """**この回に潰した churn そのもの。**

    遅れが 3日 と 4日 の間を動くので、同じ期限が走った時刻しだいで
    「1日 後ろ」にも「ちょうど同じ」にも見えます。**帯の中は黙ること。**
    """
    band = J.analytics_lag_band()
    assert band >= 1, ("実測の遅れは 3日 と 4日 の両方が観測されています。"
                       "帯が 0 に落ちたら、`data/analytics_lag.jsonl` の窓を疑うこと")

    for a in (J._ans_after({"on_date": "2026-08-29", "plus_lag": True}, lag=3),
              J._ans_published_group({"created_after": "1970-01-01", "count": 1},
                                     date(2026, 8, 25), lag=3)):
        assert a.slack == band, "遅れを足したなら、そのゆらぎを帯に載せること"
        ちょうど1日後ろ = J.Verdict("t", a.ready + timedelta(days=band), a.ready, [a])
        assert not ちょうど1日後ろ.waits, "**帯の中の1日を「待ち」と数えないこと**"
        ずっと後ろ = J.Verdict("t", a.ready + timedelta(days=band + 4), a.ready, [a])
        assert ずっと後ろ.waits == 4, "帯の外は、これまでどおり数えること"
        早すぎる = J.Verdict("t", a.ready - timedelta(days=band + 2), a.ready, [a])
        assert 早すぎる.slips, "**帯の外に早すぎる期限は、これまでどおり止めること**"


def test_遅れを足さない要件には帯を付けない():
    """`plus_lag` の無い `after` は、その日が来るだけ。**推定は1つも入っていません。**"""
    a = J._ans_after({"on_date": "2026-09-01"}, lag=3)
    assert a.slack == 0


@pytest.mark.parametrize("kind", ["now", "external", "accrual", "published_group",
                                  "after", "group_key"])
def test_知っている_kind_は落ちない(kind: str):
    """**状態を見る道具が、状態のせいで死んではいけない。**"""
    a = J.answer({"kind": kind}, date(2026, 8, 25), 3)
    assert isinstance(a, J.Answer)


def test_count_expr_は台帳を読める():
    a = J.answer({"kind": "accrual", "count_expr": "len(uploaded())",
                  "need": 1, "since": "2026-08-01"}, date(2026, 8, 25), 3)
    assert a.ready is not None, a.why


# ---- **逆向き: データはもう揃うのに、期限がまだ先**（2026-08-25 22:5x）------
#
# ここは長らく `slips`（期限が早すぎる）**だけ**を見ていて、逆向きは
# 「**期限に間に合います**」という緑の行で流れていました。
# **軌跡の腕は前提を1件閉じたときだけ動く**ので、その待ちは
# **到達日がまるごと止まっている日数**です。
# 実測（2026-08-25・開いている16件）: **10件・合計 46日・平均 4.6日・最大 14日**。


def _one(deadline: str, count: int, need: int, since: str) -> list[dict]:
    return [{"claim": "A", "deadline": deadline,
             "needs": [{"kind": "accrual", "count_expr": str(count),
                        "need": need, "since": since}]}]


def test_期限が遅すぎる側も数えること():
    """**緑の行にしないこと。** ここが「もう判定できるのに待っている」側です。"""
    items = _one("2026-09-30", count=100, need=1, since="2026-08-20")
    v = J.check(items, as_of=date(2026, 8, 25), lag=3)[0]
    assert v.ready is not None
    assert v.waits > 0, "**期限が遅すぎる側を 0日 と数えています**"
    assert v.waits == (v.deadline - v.ready).days
    assert not v.slips


def test_期限が早すぎる側は_待ちに数えないこと():
    """2つの向きを混ぜないこと。**押し出す側は 0日** です。"""
    items = _one("2026-08-26", count=0, need=1_000_000, since="2026-08-20")
    v = J.check(items, as_of=date(2026, 8, 25), lag=3)[0]
    if v.ready is not None:
        assert v.waits == 0 or not v.slips


def test_待ちの合計を出力に出すこと():
    """**数えていても黙っていたら、同じことです。**"""
    items = _one("2026-09-30", count=100, need=1, since="2026-08-20")
    vs = J.check(items, as_of=date(2026, 8, 25), lag=3)
    txt = "\n".join(J.lines(vs, 3))
    assert "期限が遅すぎる" in txt
    assert "縮めること" in txt


def test_ready_by_claim_は_claimごとの最早の日を返す():
    """`src/arm_speed.next_close` がここを読みます。"""
    items = _one("2026-09-30", count=100, need=1, since="2026-08-20")
    got = J.ready_by_claim(items, as_of=date(2026, 8, 25), lag=3)
    assert got["A"] == J.check(items, as_of=date(2026, 8, 25), lag=3)[0].ready


def test_実物にも待ちが残っていないか_数えられること():
    """**実物で回ること。**（件数そのものは日々動くので固定しません）"""
    vs = J.check(_open_items())
    total = sum(v.waits for v in vs)
    assert total >= 0
    assert all(v.waits == 0 or v.ready < v.deadline for v in vs if v.ready and v.deadline)


def test_status_も_遅すぎる側を出すこと():
    """**読む側が黙っていたら、数えていても同じです。**

    `scripts/status.py` は毎回の最初に読まれます。ここは長らく
    `slips`（期限が早すぎる）／`unk`／`non` の3つしか出しておらず、
    **「データは揃うのに期限がまだ先」は1行も出ていませんでした。**
    実測 10件・合計46日 ——**腕は前提を1件閉じたときだけ動く**ので、
    その待ちは到達日ごと止まります。
    """
    src = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "v.waits" in src, "status.py が遅すぎる側を数えていません"
    assert "期限が遅すぎる" in src, "数えても印字していません"
    assert "縮めること" in src, "何をすればいいかを言っていません"
