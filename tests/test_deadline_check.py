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

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _machine_is_running(monkeypatch):
    """**このファイルは「機械が動いているとき」の話をしています。**

    2026-08-30 から `AUTOMATION_PAUSED.md` が在り、`deadline_check._paused_supply()`
    が「床に足りない群は、停止中は埋まらない」で打ち切ります（`unreachable`）。
    **それは正しい振る舞い**ですが、下の検査が守っているのは
    **走っているときに `_project_nth()` が日を出すこと**（出さないと
    `arm_speed.forward()` の `undated` に落ちて腕が丸ごと凍る）です。

    **止めないと、`test_群が足りなくても_伸び率から判定日を出す` は
    停止のあいだ赤のままになり、`test_1本も作っていない群には_日を出さない` は
    「停止だから None」で**空回りして通ります。** どちらも守っているものを
    測らなくなるので、ここで世界を1つに固定します。

    **停止中の振る舞いは `tests/test_paused_supply.py` が別に見ています。**
    """
    import src.pause_guard as PG

    monkeypatch.setattr(PG, "is_paused", lambda: False)


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


def test_endcard_を書くと処置群だけを数える():
    """**対照が混ざったまま満たすと、効きが薄まって「外れ」に化けます。**

    2026-08-26 夕の実測 —— 期限 10/11「ショートの最後で登録を直接1回頼む」の
    `created_after: 2026-08-24` に当たっていた 51本 のうち、**依頼の型は 5本**で、
    残りは問いかけ 25本（＝対照）・長尺の「明日やること」20本 でした。
    依頼が出はじめたのは **08/26 02:50** で、**同じ束の中にも問いかけが3本**
    混ざっています ——**日付では切れません。**

    その前提の `next_if_false` は「登録率の腕を**動画の外**へ移す」なので、
    誤って外れると、**律速の門（登録者1,000人）を誤った理由で手放します。**

    ## 数を散文から拾わないこと（2026-08-26 に踏んだ）

    ここは長らく `ans.why` から `**N本** ／ 要` を正規表現で抜いていました。
    **その字は「まだ 72本 に足りていない」枝にしか出ません。** 在庫が増えて
    `loose` が 72本 に届いた日、`why` は「**72本目の公開 10/11**」に変わり、
    検査は「絞り込みが効いていない」ではなく **`AttributeError`** で落ちました
    （`re.search(...)` が `None`）。**症状から原因が読めない形**です。

    **見るのは `Answer` そのもの**にします。絞れば標本は減るので、
    **`tight` は `loose` より早くなりようがありません** ——
    72本目が後ろへ動くか、そもそも 72本 に届かなくなる（`ready is None`）。
    **この不等号は、どちらの枝でも同じ向きです。**
    """
    need = {"created_after": "2026-08-24", "count": 72, "settle_days": 0}
    loose = J._ans_published_group(dict(need), date(2026, 8, 26), lag=3)
    tight = J._ans_published_group(dict(need, endcard="request"), date(2026, 8, 26), lag=3)

    def rank(ans):
        """**遅いほど大きい。** 届かない（`ready is None`）はいちばん遅い側。"""
        return date.max if ans.ready is None else ans.ready

    assert rank(tight) >= rank(loose), (
        "`endcard: request` で絞ったのに、判定できる日が**早く**なっています —— "
        "処置群の絞り込みが効いていない（`src/endcard_verdict.form_of`）"
    )
    assert rank(tight) > rank(loose) or tight.why != loose.why, (
        "`endcard: request` を書いても、答えが1文字も変わっていません —— "
        "絞り込みがどこにも効いていない（`src/endcard_verdict.form_of`）"
    )
    assert "終端が request" in tight.why, "何で絞ったかが出力に出ていません"
    assert "終端が" not in loose.why, "`endcard:` の無い要件まで絞ってはいけません"


def test_群が足りなくても_伸び率から判定日を出す():
    """**`None` は「判定できる日が出せない」であって、「まだ足りない」ではありません。**

    2026-08-26 夕の実測 —— 期限 10/11「ショートの最後で登録を直接1回頼む」
    （腕 `sub_rate`・処置は既に生成に入っていて**予約に 21本**）は、
    72本 に足りないというだけで **`ready is None`** に落ちていました。その結果:

        `src/arm_speed.forward()`   `undated` に落ちる ＝ **θ に数えられない**
        `scripts/queue_lag.py`      判定日を持たない前提は**手前へ倒せない**
        `scripts/deadline_check.py` `[!!] 判定できる日が出せません` で終わる

    同じ回の `python scripts/eta.py --alloc` は
    「**次の1件は `sub_rate` がいちばん早い（5日）**」と出しています ——
    **いちばん速い腕の、唯一 走っている実験が、機械から見えていませんでした。**

    **`_ans_group_key` は同じ形をとっくに解いています**
    （`要 1000 ／ いま 78（7日で 11.14/日）→ あと 83日`）。
    諦めていたのは、こちらの1関数だけです。
    """
    need = {"created_after": "2026-08-24", "count": 10_000, "settle_days": 0}
    ans = J._ans_published_group(dict(need), date(2026, 8, 26), lag=3)
    assert ans.ready is not None, (
        "群が足りないだけで `ready is None` に落ちています —— "
        "`_project_nth` が伸び率から日を出していません"
    )
    assert ans.slack > 0, "推定なのに帯が 0 です（点として読まれ、毎回 期限が書き換わります）"
    assert "推定" in ans.why, "推定だと分かる字が出力に出ていません"


def test_1本も作っていない群には_日を出さない():
    """**伸び率がゼロの群に日を付けないこと。**

    0 は「まだ来ていない」とも「こちらが作らないかぎり永久に来ない」とも読めます
    （`zero_means_never`）。**式からは区別できない**ので、ここでは日を出しません。
    """
    need = {"created_after": "2099-01-01", "count": 5, "settle_days": 0}
    ans = J._ans_published_group(dict(need), date(2026, 8, 26), lag=3)
    assert ans.ready is None, "1本も作っていない群に、判定できる日が付いています"


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
    """**数え方が実物で回ること。**（主張しているのは下の
    `test_遅すぎる期限が残っていないこと` のほうです —— ここは形だけ見ます）"""
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


def test_遅すぎる期限が残っていないこと():
    """**印字は 666 commits 効きませんでした。赤い検査は同じ日に効きました。**

    2026-08-25 13:54Z、`scripts/deadline_check.py` が
    「期限が遅すぎる N件 —— 合計 **46日** の待ち」を印字しはじめ、
    同じ日の 22:5x に `scripts/status.py` も、**毎回の最初に読まれる場所**で
    「→ `deadline` をその日まで**縮めること**。**この回の成果になります**」
    と出すようになりました。**それから 666 commits のあいだ、1件も縮んでいません**
    （待ちは 46日 → **67日** に増えました）。

    **同じ 20時間 に、逆向きの書き換えは 2回 起きています。**
    `e664d5a`（08-25 21:46Z）は stat_split を 09-14 → 10-06 へ **22日 延ばし**、
    commit がその理由をそのまま書いています ——「**赤い検査が2件**」。

        延ばす向き  赤い検査あり（`test_期限が_判定できる日より前に置かれていない`）
                    → 20時間で 2回 起きた
        縮める向き  印字のみ（`assert total >= 0` ＝ 何も主張していない）
                    → 666 commits で 0回

    **印字が読まれていないのではありません。印字は「判断」を要求します。**
    毎周「1件 出す」に追われている側にとって、
    **判断の要る行は、要らない行に必ず負けます。**
    赤い検査は判断を要求しません（直すか、直さないかしかない）。

    **直し方は1つ**（判断は要りません。API 0単位・本は0本）:

        python scripts/deadline_check.py --shrink

    **`falsified_if` を緩めて逃げないこと。** もっと n が要るなら、
    動かすのは **`needs.count` のほう**です —— 期限を水増しして待つと、
    `src/arm_speed.forward()` は **`ready` の側**を読むので、
    **予測だけが「その日に閉じる」前提のまま**残ります（＝到達日が早すぎる）。

    ## 覆る条件（**次に来た側へ**）

    - この検査が**毎周 赤くなる**（＝ `--shrink` の後すぐまた赤い）なら、
      効いていないのは検査ではなく **`Verdict.slack`（帯）の幅**です。
      帯を広げること。**この検査を消して印字に戻さないこと** ——
      印字に戻した結果が、上の 666 commits です
    - 「期限を意図して先に置きたい」回が出てきたら、そのときは
      **`needs` に書くこと**。期限は日付の欄で、設計の欄ではありません
    """
    vs = J.check(_open_items())
    late = sorted((v for v in vs if v.waits), key=lambda v: -v.waits)
    total = sum(v.waits for v in late)
    detail = " / ".join(f"{v.claim[:28]} 判定 {v.ready} なのに期限 {v.deadline}（{v.waits}日）"
                        for v in late)
    assert not late, (
        f"**データは揃うのに期限が先の前提が {len(late)}件・合計 {total}日。**"
        f" 到達日はそのぶん止まっています: {detail}"
        "  → `python scripts/deadline_check.py --shrink`"
        "（`falsified_if` は緩めないこと）")


def _mini_yaml(deadline: str, on_date: str) -> str:
    """註つきの小さな台帳。**註が残るかを見るために入れてあります。**"""
    return f"""# 先頭の註。**消えたら `yaml.dump` で書き戻しています。**
hypotheses:
  - claim: "縮める側の前提"
    # 中の註。ここも残ること
    deadline: "{deadline}"
    lever: per_video
    needs:
      - kind: after
        on_date: "{on_date}"
    falsified_if: "触らないこと"
  - claim: "閉じている前提"
    deadline: "2026-01-01"
    closed_on: "2026-01-01"
    lever: none
    effect: 1.0
    needs:
      - kind: now
confirmed:
  - "ここも残ること"
"""


def test_shrink_は_期限だけを縮めて_註を残すこと(tmp_path):
    """**`yaml.dump` で書き戻したら、3,300行の註が全部 消えます。**

    註には「なぜ外れたか」「しきい値をどう引いたか」が入っていて、
    **次に来た側が判断できるのは、その註があるからです。**
    """
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-12-31", "2026-08-01"), encoding="utf-8")
    done = J.shrink(path=p, as_of=date(2026, 8, 26), lag=0)
    assert [(b, a) for _c, b, a in done] == [("2026-12-31", "2026-08-01")]
    out = p.read_text(encoding="utf-8")
    assert 'deadline: "2026-08-01"' in out
    assert "# 先頭の註" in out and "# 中の註" in out, "註が消えました（`yaml.dump` で書いています）"
    assert 'falsified_if: "触らないこと"' in out, "`falsified_if` に触っています"
    assert "confirmed:" in out and "ここも残ること" in out


def test_shrink_は_期限が早すぎる側を動かさないこと(tmp_path):
    """**`--shrink` は縮める向き専用です。** 延ばす側は `--extend`（下）。

    **2つを1つの旗にまとめないこと。** 向きが違えば意味も違います ——
    縮めるのは「もう判定できるのに待っている」、
    延ばすのは「その日にはデータが無い」。`--fit` は両方を順に撃つだけです。
    """
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-08-05", "2026-09-30"), encoding="utf-8")
    assert J.shrink(path=p, as_of=date(2026, 8, 26), lag=0) == []
    assert 'deadline: "2026-08-05"' in p.read_text(encoding="utf-8")


def test_extend_は_期限だけを延ばして_註を残すこと(tmp_path):
    """**早すぎる期限に、印字ではなく手を当てる**（2026-08-28 に足した）。

    この道具は `slips` の1件ごとに「`deadline:` へ延ばすこと」と印字し、
    `test_期限が_判定できる日より前に置かれていない` が赤で止めます。
    **それでも 5件が赤のまま残っていました** —— 3,300行の YAML を
    手で5か所 直す作業だからです（手で動かした跡が台帳に 33件）。
    """
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-08-05", "2026-09-30"), encoding="utf-8")
    done = J.extend(path=p, as_of=date(2026, 8, 26), lag=0)
    assert [(b, a) for _c, b, a in done] == [("2026-08-05", "2026-09-30")]
    out = p.read_text(encoding="utf-8")
    assert 'deadline: "2026-09-30"' in out
    assert "# 先頭の註" in out and "# 中の註" in out, "註が消えました"
    assert 'falsified_if: "触らないこと"' in out, "`falsified_if` に触っています"


def test_extend_は_期限が遅すぎる側を動かさないこと(tmp_path):
    """**延ばす手が縮めたら、判定を先送りできてしまいます。**"""
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-12-31", "2026-08-01"), encoding="utf-8")
    assert J.extend(path=p, as_of=date(2026, 8, 26), lag=0) == []
    assert 'deadline: "2026-12-31"' in p.read_text(encoding="utf-8")


def test_extend_の_dry_run_は書かないこと(tmp_path):
    p = tmp_path / "h.yaml"
    before = _mini_yaml("2026-08-05", "2026-09-30")
    p.write_text(before, encoding="utf-8")
    done = J.extend(path=p, as_of=date(2026, 8, 26), lag=0, dry_run=True)
    assert done, "何を書くかは返すこと"
    assert p.read_text(encoding="utf-8") == before, "--dry-run なのに書きました"


def test_extend_は_閉じた前提を書き換えないこと(tmp_path):
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-08-05", "2026-09-30"), encoding="utf-8")
    J.extend(path=p, as_of=date(2026, 8, 26), lag=0)
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    closed = next(h for h in doc["hypotheses"] if h.get("closed_on"))
    assert str(closed["deadline"]) == "2026-01-01", "閉じた前提の期限を書き換えました"


def test_extend_は_ready_より先へは置かないこと(tmp_path):
    """**寄せ先は `ready` だけ。** 1日でも先へ置けるなら、それは水増しです。"""
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-08-05", "2026-09-30"), encoding="utf-8")
    J.extend(path=p, as_of=date(2026, 8, 26), lag=0)
    vs = J.check(yaml.safe_load(p.read_text(encoding="utf-8"))["hypotheses"],
                 as_of=date(2026, 8, 26), lag=0)
    v = next(x for x in vs if x.ready is not None)
    assert v.deadline == v.ready, "`ready` ちょうどに置くこと"
    assert not v.slips and not v.waits


def test_fit_は両方の向きを1手で寄せること(tmp_path):
    """`--fit` ＝ `--shrink` と `--extend` を順に。**普通の回はこれでよい。**"""
    p = tmp_path / "h.yaml"
    p.write_text("""hypotheses:
  - claim: "早すぎる側"
    deadline: "2026-08-05"
    lever: per_video
    needs:
      - kind: after
        on_date: "2026-09-30"
    falsified_if: "触らないこと"
  - claim: "遅すぎる側"
    deadline: "2026-12-31"
    lever: per_video
    needs:
      - kind: after
        on_date: "2026-08-01"
    falsified_if: "触らないこと"
""", encoding="utf-8")
    # **`main(["--fit"])` をここから撃たないこと** —— あれは実物の
    # `config/hypotheses.yaml` を書きます。ここでは `--fit` が呼ぶ2手を、
    # 同じ順で仮の台帳に当てます。
    J.shrink(path=p, as_of=date(2026, 8, 26), lag=0)
    J.extend(path=p, as_of=date(2026, 8, 26), lag=0)
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    got = {h["claim"]: str(h["deadline"]) for h in doc["hypotheses"]}
    assert got == {"早すぎる側": "2026-09-30", "遅すぎる側": "2026-08-01"}


def test_shrink_の_dry_run_は書かないこと(tmp_path):
    p = tmp_path / "h.yaml"
    before = _mini_yaml("2026-12-31", "2026-08-01")
    p.write_text(before, encoding="utf-8")
    done = J.shrink(path=p, as_of=date(2026, 8, 26), lag=0, dry_run=True)
    assert done, "何を書くかは返すこと"
    assert p.read_text(encoding="utf-8") == before, "--dry-run なのに書きました"


def test_shrink_は_閉じた前提と同じ_claim_で取り違えないこと(tmp_path):
    """**`check()` は閉じた前提を飛ばします。** 行の対応を順番で取ると、
    閉じた行の `deadline:` を書き換えます（そちらが先に並んでいるため）。"""
    p = tmp_path / "h.yaml"
    p.write_text(_mini_yaml("2026-12-31", "2026-08-01"), encoding="utf-8")
    J.shrink(path=p, as_of=date(2026, 8, 26), lag=0)
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    closed = next(h for h in doc["hypotheses"] if h.get("closed_on"))
    assert str(closed["deadline"]) == "2026-01-01", "閉じた前提の期限を書き換えました"


def _verdict(need: dict, deadline: str = "2026-12-31"):
    items = [{"claim": "x", "deadline": deadline, "lever": "none", "needs": [need]}]
    return J.check(items, as_of=date(2026, 8, 26), lag=3)[0]


def test_まだ数えはじめたところを_判定できないに混ぜないこと():
    """**直し方が正反対のものに、同じ札を付けないこと。**

    2026-08-26 19:08 JST にきょうだいの回が前提を1件 立て、その **11分後** に
    `[!!] 判定できる日が出せません` と並びました。**正しく走っている前提**で、
    `since` から 1日 しか経っていないから伸び率が出ないだけです ——
    **明日には日が出ます。何もしないのが正解。**

    同じ札の下にいたもう1件は「収益化の審査（登録者があと 999人）」で、
    **こちらの手では起こせません。** 前提の立て方ごと変えるしかない。

    **同じ回に `test_遅すぎる期限が残っていないこと` を入れて、
    この道具の出力に赤い検査を付けました。** 読まれる度合いが上がったぶん、
    **紛らわしい札の危険も上がります** —— 直す必要のない前提を
    「判定できない」と読んで畳む回が出ます。
    """
    warm = _verdict({"kind": "accrual", "count_expr": "0", "need": 72,
                     "since": "2026-08-26"})
    assert warm.ready is None
    assert warm.warming and not warm.unreachable
    assert warm.mark == "[..]", "まだ数えはじめたところに [!!] を付けています"

    never = _verdict({"kind": "accrual", "count_expr": "0", "need": 72,
                      "since": "2026-08-26", "zero_means_never": True})
    assert never.unreachable and not never.warming
    assert never.mark == "[!!]"


def test_まだ数えはじめたところは_出力で何もするなと言うこと():
    warm = _verdict({"kind": "accrual", "count_expr": "0", "need": 72,
                     "since": "2026-08-26"})
    body = "\n".join(J.lines([warm], 3))
    assert "まだ数えはじめたところ" in body
    assert "判定できる日が出せません" not in body, "待てば出るものに『出せません』と言っています"
    assert "何もしないのが正解" in body


def test_status_も_2つを分けて出すこと():
    """**読む側が混ぜたら、数えていても同じです。**"""
    src = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "v.warming" in src, "status.py が『まだ数えはじめたところ』を分けていません"
    assert "まだ数えはじめたところ" in src, "分けても印字していません"


def test_1日の窓から伸び率を出さないこと():
    """**3本 から 72本 を見通して、期限を 38日 縮めろと出しました。**（2026-08-26 夕）

    実測。`since: 2026-08-26` の前提が、立った **1時間後** に:

        要 72 ／ いま **3**（**1日で 3.00/日**）→ あと 23日（**±14日**）
        → 判定できるのは 09-18 なのに、期限は 38日 後ろ  → 縮めること

    帯（±14日）は `1/√have` ＝ **`have` の数え上げ誤差**だけを見ていて、
    **窓の短さ**を見ていません。同じ `have` でも、
    **1日で3本と7日で3本は別の話**です。

    **同じ回に「遅すぎる期限は赤」を入れたので、ここが効きます** ——
    1日の窓の見通しが `waits` を作ると、
    **赤 → 縮める → データが追いつかず `slips` → 延ばす**の往復になります。
    **縮める側の入力が推定でしかないときは、縮めないほうが速い。**
    """
    base = {"kind": "accrual", "count_expr": "3", "need": 72}
    one = J.answer({**base, "since": "2026-08-26"}, date(2026, 8, 26), 3)
    assert one.ready is None, "1日の窓から日を出しています"
    assert "伸び率を出しません" in one.why

    two = J.answer({**base, "since": "2026-08-24"}, date(2026, 8, 26), 3)
    assert two.ready is not None, "2日 たっても出していません"


def test_足りているなら_窓の長さは要らないこと():
    """**もう `need` に届いている**なら、伸び率は要りません（今日 判定できます）。"""
    a = J.answer({"kind": "accrual", "count_expr": "16", "need": 16,
                  "since": "2026-08-26"}, date(2026, 8, 26), 3)
    assert a.ready == date(2026, 8, 26)


# --- **判定できる日が出せない claim を、`deadline` へ落とさないこと** ---
#
# 2026-08-26 20:4x。同じ1件について、3つの道具がこう言っていました:
#     scripts/eta.py          「期日の来た前提があります → **この回は `verdict` で
#                               日付が動かせます**」
#     scripts/status.py       「[!] **外れています。** この回は verdict を出すこと」
#     scripts/deadline_check.py
#                             「[..] まだ数えはじめたところです。
#                               **この回は何もしないのが正解**」
# 正しいのは3つ目。要 8本 に対し公開済み 7本、両群がそろう公開日は 3日 要るのに 0日。
# 原因は `ready_by_claim()` が `ready is None` を**黙って落とす**こと ——
# 落ちた claim は `next_close()` で `deadline`（置いた回の勘）へ流れます。


def test_判定できる日が出せない_claim_を数え上げられること():
    warming = _one("2026-08-26", count=0, need=8, since="2026-08-25")
    assert J.check(warming, as_of=date(2026, 8, 26), lag=3)[0].warming
    got = J.unready_claims(warming, as_of=date(2026, 8, 26), lag=3)
    assert got == {"A"}
    # 数えられる側は入らない
    ready = _one("2026-08-26", count=99, need=8, since="2026-08-20")
    assert J.unready_claims(ready, as_of=date(2026, 8, 26), lag=3) == set()


def test_needsの無い前提は_判定できない側に数えないこと():
    """**書かなければ赤が消える、を作らないこと。**

    `needs:` が無いのは「判定できない」ではなく「**何が要るか誰も書いていない**」。
    ここに入れると、`needs:` を書かないほうが得になります。
    """
    bare = [{"claim": "A", "deadline": "2026-08-26"}]
    assert J.check(bare, as_of=date(2026, 8, 26), lag=3)[0].unchecked
    assert J.unready_claims(bare, as_of=date(2026, 8, 26), lag=3) == set()


def test_next_close_は判定できない前提をdeadlineへ落とさないこと():
    """`src/arm_speed.next_close(unready=...)`。**開いた件数には残すこと。**"""
    from src import arm_speed

    doc = {"hypotheses": [
        {"claim": "判定できない", "deadline": "2026-08-26"},
        {"claim": "先の話", "deadline": "2026-09-20"},
    ]}
    today = date(2026, 8, 26)
    bare = arm_speed.next_close(doc=doc, today=today)
    assert bare["on"] == today and bare["days"] == 0

    got = arm_speed.next_close(doc=doc, today=today, unready={"判定できない"})
    assert got["on"] == date(2026, 9, 20), "**deadline のほうへ落ちています**"
    assert got["days"] == 25
    # **開いている件数からは外さないこと**（開いてはいます）
    assert got["open"] == bare["open"] == 2
