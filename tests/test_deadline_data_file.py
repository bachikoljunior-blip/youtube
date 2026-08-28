"""**時計が来た ≠ データが在る**（2026-08-27・最適化の回）。

`scripts/deadline_check.py` の `at_time_jst` は、その 14時間 前に
「その日でも時刻が来るまでは日を返さない」ところまで直りました。
**それでも見ているのは時計だけ**でした。実測 2026-08-27 **14:24 JST**
（＝ 要件の 14:00 は過ぎている）:

    `data/views.jsonl` のいちばん新しい点   **08-26 01:53 JST**（**37時間 前**）
    `scripts/deadline_check.py`             [OK] 判定できるのは **08-27**
    `scripts/drift.py`                      **この回は verdict を出すこと**

要るのは「05/06/07/08時に足した4本の、**公開から6時間の読み**」で、
その点は1つも在りません。同じ前提の `note` には、前回この門が早撃ちして
「`verdict='count' confounded=False` を印字しました —— **確信つきで逆**です」
と残っています。**時計だけの門は、同じ穴を時刻の粒で作り直しただけ**でした。

直し方は、`_ans_after` の註が自分で書いた覆る条件そのものです ——
「時刻の粒でも足りない要件が出てきたら、**その計器に直接 訊く `kind`** を足すこと」。
`needs` の `data_file:` が、その「直接 訊く」欄です。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as J  # noqa: E402


def _open_items() -> list[dict]:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return [h for h in doc["hypotheses"]
            if not any(k in h for k in ("verdict", "closed_on", "outcome"))]


def test_data_file_がまだその点を持っていなければ日を出さない(tmp_path):
    """時計が過ぎていても、**計器にその点が無ければ** `ready` は出さない。"""
    p = tmp_path / "views.jsonl"
    p.write_text('{"at": "2020-01-01T00:00:00Z", "id": "x", "views": 1}\n', encoding="utf-8")
    need = {"kind": "after", "on_date": "2020-06-01", "at_time_jst": "14:00",
            "data_file": str(p), "what": "6時間の読み",
            "refresh": "python scripts/snapshot.py"}
    a = J._ans_after(need, lag=3)
    assert a.ready is None, "点が無いのに判定できる日を出しています"
    assert "まだ在りません" in a.why
    assert "snapshot" in a.todo, "**待っても出ない側なのに、次の手が渡っていません**"


def test_data_file_がその点を持っていれば今までどおり日が出る(tmp_path):
    """**在るときに止めないこと。** 止めると、こんどは判定できる回を殺します。"""
    p = tmp_path / "views.jsonl"
    p.write_text('{"at": "2020-06-01T06:00:00Z", "id": "x", "views": 1}\n', encoding="utf-8")
    need = {"kind": "after", "on_date": "2020-06-01", "at_time_jst": "14:00",
            "data_file": str(p), "what": "6時間の読み"}
    a = J._ans_after(need, lag=3)
    assert a.ready == date(2020, 6, 1)
    assert not a.todo


def test_data_file_を書いていない要件は今までどおり時計だけで通る():
    """**既にある要件を巻き込まないこと**（`data_file` は書いた要件にだけ効く）。"""
    need = {"kind": "after", "on_date": "2020-06-01", "what": "その日のデータ"}
    a = J._ans_after(need, lag=3)
    assert a.ready == date(2020, 6, 1)


def test_実物の台帳で_views_を要る前提には_data_file_が書いてある():
    """**合成では捕まりません。** 実物の台帳で、時計だけの門に戻ったら落とす。

    `data/views.jsonl` の点が要ると `falsified_if` が散文で言っている前提は、
    **機械が読む欄（`data_file`）にもそう書いてあること。**
    散文にしか無かった 14時間 が、この repo で7回目の同じ形でした。
    """
    bad = []
    for h in _open_items():
        if "views.jsonl" not in str(h.get("falsified_if") or ""):
            continue
        if not any(n.get("data_file") for n in (h.get("needs") or [])):
            bad.append(str(h.get("claim"))[:40])
    assert not bad, f"`views.jsonl` を散文でだけ要求している前提: {bad}"


def test_点の無いファイルでも落ちない(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert J.newest_point(p) is None
    assert J.newest_point(tmp_path / "no-such-file.jsonl") is None


def test_待ち方が2つに分かれて印字される(tmp_path):
    """**「待てば出ます」を一律に出さないこと。**

    時計待ちと「データを取っていない」は、次の回のやることが正反対です。
    """
    p = tmp_path / "views.jsonl"
    p.write_text('{"at": "2020-01-01T00:00:00Z", "id": "x"}\n', encoding="utf-8")
    h = {"claim": "テスト用", "deadline": "2020-06-01",
         "needs": [{"kind": "after", "on_date": "2020-06-01", "at_time_jst": "14:00",
                    "data_file": str(p), "what": "6時間の読み",
                    "refresh": "python scripts/snapshot.py"}]}
    vs = J.check([h])
    out = "\n".join(J.lines(vs, lag=3))
    assert "その時刻まで待つこと" not in out, "時計は過ぎているのに、待てと言っています"
    assert "足りないのはデータのほうです" in out


# --------------------------------------------------------------------------
# **その門は、いま何件に当たっているか**（2026-08-28 の2周目に足した）
#
# `data_file:` の申告は**任意**です（`_stale_todo` / `_on_date_todo` の
# 「書いていない要件は、今までどおり時計だけで通します」）。実測 08/28:
#
#     前提 39件 ／ `data_file:` を申告している **3件**（**8%**）
#
# **門は正しく、当たる範囲が 8% でした。** 埋めるのは推測になるので
# （どの計器かは要件ごとに違う）、**数を出すだけ**にしてあります。
# ここはその行が消えないようにする門です。
# --------------------------------------------------------------------------


def test_時計だけの要件の数を_印字に出すこと():
    """裸で「判定できます」と言うたびに、何を確かめていないかを並べること。

    `eta.py` の (イ)（裸の「届きません」を出さない）と同じ形です。
    """
    import scripts.deadline_check as dc

    # **`kind` は `answer()` が知っているものを書くこと**（2026-08-29 に直した）。
    # ここは長らく `kind: "on_date"` と書いていました —— `answer()` の分岐に
    # **その名前はありません**（`after` です）。分母が「この欄の効く kind だけ」に
    # なった瞬間、この検査は 0/0 を数えて落ちました。
    # **検査の側が、実物に無い形を組み立てていた**わけで、直すのは検査のほうです。
    class _V:
        needs = [{"kind": "after"}, {"kind": "accrual", "data_file": "data/x.jsonl"}]

    got = dc._data_file_coverage([_V()])
    text = "\n".join(got)
    assert "1/2件" in text, text
    assert "推測で埋めないこと" in text


def test_全部が申告していれば_黙ること():
    """**覆る条件がそのまま検査になっていること。** 申告が揃えば行は出ません。"""
    import scripts.deadline_check as dc

    class _V:
        needs = [{"kind": "accrual", "data_file": "data/x.jsonl"}]

    assert dc._data_file_coverage([_V()]) == []


def test_needs_が無い回に_割り算をしないこと():
    import scripts.deadline_check as dc

    class _V:
        needs = None

    assert dc._data_file_coverage([_V()]) == []


# ---------------------------------------------------------------------------
# **計器そのものが嘘の点を返していた**（2026-08-28 13:5x・最適化の回）
#
# 上の門は正しく作られました。**訊かれた計器のほうが嘘を返していました。**
# 実測 2026-08-28 13:4x JST（`newest_point()` を全計器に当てた）:
#
#     data/uploaded.jsonl  **2026-10-12 09:00**（**1,075時間 先**）  ← 申告済みの3件の1つ
#     data/reach.jsonl     **(1点も読めません)**                     ← 226KB・数千行
#
# `uploaded.jsonl` の `at` は「**予約した公開時刻**」（未来）で、
# 同じ行の `uploaded_at` が「実際に上げた時刻」です。読み手は2つとも
# 「新しいほど良い」向きに使うので、**この計器だけ永久に「新しい」**と答えます:
#
#     `_ans_after`   `newest < when_data` が偽   → 門を素通り
#     `_stale_note`  `(now-newest) < hours` が真 → 「新しい。待つのが正しい」
#
# `reach.jsonl` は `at`/`ts`/`time` を1つも持たず、`_report_end`（Reporting API の
# 「この時刻までのぶん」）しか持ちません。向きは安全側ですが、
# **在るデータを「取り直せ」と言い続ける**ので Reporting の単位が毎回 出ていきます。
# ---------------------------------------------------------------------------


def test_a_future_stamp_is_not_an_observation(tmp_path):
    """**未来の時刻を「いちばん新しい点」にしないこと。**

    落ちたら、予約の時刻を持つ計器（`data/uploaded.jsonl`）は
    **何週間 取り直さなくても「新しい」**と答え続けます。
    """
    import json
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    f = tmp_path / "uploaded.jsonl"
    f.write_text(
        json.dumps({"at": (now + timedelta(days=45)).isoformat(),
                    "uploaded_at": (now - timedelta(hours=3)).isoformat()}) + "\n",
        encoding="utf-8")

    got = J.newest_point(f)
    assert got is not None, "観測の欄（`uploaded_at`）が在るのに読めていません"
    assert got < now, f"未来の点を返しています: {got}"
    assert (now - got).total_seconds() / 3600 < 4


def test_only_a_future_stamp_means_no_observation(tmp_path):
    """未来しか無い計器は **`None`**（＝観測を1点も持っていない）。

    **`None` は安全側**です（「取り直せ」と同じ向き）。
    未来をそのまま返すと、**逆向き**に外れます。
    """
    import json
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    f = tmp_path / "sched.jsonl"
    f.write_text(json.dumps({"at": (now + timedelta(days=9)).isoformat()}) + "\n",
                 encoding="utf-8")
    assert J.newest_point(f) is None


def test_report_end_counts_as_a_point(tmp_path):
    """`_report_end` しか持たない計器（`data/reach.jsonl`）を読めること。

    落ちたら、数千行 在る計器が「**1点も読めません**」に化けます。
    """
    f = tmp_path / "reach.jsonl"
    f.write_text('{"date": "20260815", "video_id": "x", '
                 '"_report_end": "2026-08-16T07:00:00Z"}\n', encoding="utf-8")
    got = J.newest_point(f)
    assert got is not None and got.year == 2026 and got.month == 8 and got.day == 16


def test_the_plain_at_still_wins_where_it_is_the_observation(tmp_path):
    """**`at` が観測時刻の計器は、今までどおり**（`data/views.jsonl` ほか）。"""
    import json
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    when = now - timedelta(hours=5)
    f = tmp_path / "views.jsonl"
    f.write_text(json.dumps({"at": when.isoformat(), "video_id": "x"}) + "\n",
                 encoding="utf-8")
    got = J.newest_point(f)
    assert got is not None and abs((got - when).total_seconds()) < 2


# ---------------------------------------------------------------------------
# **古さを問えるのは、その時刻が来てからだけ**（2026-08-28 14:2x・最適化の回）
#
# `data_file:` の枝は、`on_date` が未来でも回っていました。いま `data_file:` を
# 持つ `after` の要件は1件だけで、その `on_date` は過ぎているので**今日までは
# 一度も踏んでいません** —— ところが同じ日の回が、足す候補を **6件** 数えており
# （散文が計器を1つだけ名指ししている要件）、**うち5件の `on_date` は未来**です。
# 足した瞬間、5件ともこう答えます:
#
#     「時計は来ています。足りないのはデータのほうです ——
#       取り直すまで、待っても永久に出ません」
#
# **2つとも偽**（時計は来ていないし、待てば出る）。しかも `ready=None` なので
# 「判定できる日が出せません」＝ **収益化の審査待ちと同じ棚**に落ち、
# `refresh:` を撃つ回は**在りようのないデータに Reporting の単位を捨てます。**
# ---------------------------------------------------------------------------


def test_a_future_on_date_does_not_ask_the_instrument(tmp_path):
    """**`on_date` が未来なら、計器の古さを訊かないこと。**

    落ちたら、未来の要件が全部「取り直すまで永久に出ません」になります。
    """
    from datetime import date, timedelta

    later = date.today() + timedelta(days=10)
    p = tmp_path / "reach.jsonl"
    # **わざと古い点**（4日 前）。それでも、時刻が来ていないので訊いてはいけない。
    old = date.today() - timedelta(days=4)
    p.write_text('{"_report_end": "%sT07:00:00Z"}\n' % old.isoformat(), encoding="utf-8")

    ans = J._ans_after({"on_date": later.isoformat(), "data_file": str(p),
                        "what": "その日の面"}, 3)
    assert ans.ready is not None, f"未来の要件に計器を訊いています: {ans.why}"
    assert "取り直す" not in (ans.todo or ""), ans.todo


def test_a_past_on_date_still_asks_the_instrument(tmp_path):
    """**過ぎた要件は、今までどおり計器に訊くこと**（この門の本体）。"""
    from datetime import date, timedelta

    passed = date.today() - timedelta(days=2)
    p = tmp_path / "reach.jsonl"
    old = date.today() - timedelta(days=9)
    p.write_text('{"_report_end": "%sT07:00:00Z"}\n' % old.isoformat(), encoding="utf-8")

    ans = J._ans_after({"on_date": passed.isoformat(), "data_file": str(p),
                        "what": "その日の面"}, 0)
    assert ans.ready is None, "点が無いのに日を出しています"
    assert "取り直す" in (ans.todo or "")


# --------------------------------------------------------------------------
# **門は、それが守っている日に立っているか**（2026-08-29 05:0x・最適化の回）
#
# `plus_lag: true` の要件が「判定できる」と言う日は `on_date + lag` です
# （`_after_tail`）。ところが `data_file:` の門は `on_date` の 00:00 に
# 立っていました —— **`lag` 日 早い。**
#
# `plus_lag` の意味は「**その日ぶんの点は `lag` 日 あとに届く**」なので、
# `on_date` に計器へ訊けば、**要件自身の定義により、まだ在りません。**
# 返るのは `ready=None`（＝「判定できる日が出せません」）で、その claim は
# `arm_speed.forward()` と `next_when()` の両方から消えます。
#
# 実物で当たっていたのは 09-19「1本あたり再生の天井は配信の側で決まっている」
# （`on_date: 2026-09-15` ＋ `plus_lag` ＋ `data/views.jsonl`）——
# **09/15〜09/18 の 4日 が、その窓**でした。
#
# ff1a8c1 は「**未来の** `on_date` には訊かない」を入れています。**足りません**
# —— `on_date` が過ぎていても、`on_date + lag` が来ていなければ同じ話です。
# --------------------------------------------------------------------------


def _stale_reach(tmp_path, days_old: int):
    from datetime import date as _d, timedelta as _td
    p = tmp_path / "reach.jsonl"
    old = _d.today() - _td(days=days_old)
    p.write_text('{"_report_end": "%sT07:00:00Z"}\n' % old.isoformat(),
                 encoding="utf-8")
    return p


def test_plus_lag_の要件は遅れのぶん待ってから計器に訊く(tmp_path):
    """`on_date` は過ぎたが `on_date + lag` はまだ ＝ **訊いてはいけない。**

    落ちたら、`plus_lag` の要件は遅れの日数だけ「判定できる日が出せません」に
    化け、予定表から消えます。
    """
    from datetime import date, timedelta

    passed = date.today() - timedelta(days=2)          # 時計は過ぎている
    p = _stale_reach(tmp_path, days_old=9)             # 計器はわざと古い
    ans = J._ans_after({"on_date": passed.isoformat(), "plus_lag": True,
                        "data_file": str(p), "what": "その日の面"}, 4)
    assert ans.ready == passed + timedelta(days=4), (
        f"**遅れの窓の中で計器に訊いています**: ready={ans.ready} why={ans.why}")
    assert "取り直す" not in (ans.todo or ""), ans.todo


def test_plus_lag_の窓を過ぎたら今までどおり計器に訊く(tmp_path):
    """**門を消してはいけません。** 遅れが明けたら、点の有無を訊くこと。"""
    from datetime import date, timedelta

    passed = date.today() - timedelta(days=10)
    p = _stale_reach(tmp_path, days_old=9)
    ans = J._ans_after({"on_date": passed.isoformat(), "plus_lag": True,
                        "data_file": str(p), "what": "その日の面"}, 4)
    assert ans.ready is None, "点が無いのに日を出しています"
    assert "取り直す" in (ans.todo or "")


def test_plus_lag_が無ければ門の位置は変わらない(tmp_path):
    """遅れを足さない要件は、今までどおり `on_date` に立つこと。"""
    from datetime import date, timedelta

    passed = date.today() - timedelta(days=2)
    p = _stale_reach(tmp_path, days_old=9)
    ans = J._ans_after({"on_date": passed.isoformat(),
                        "data_file": str(p), "what": "その日の面"}, 4)
    assert ans.ready is None, "`plus_lag` の無い要件まで待たせています"


def test_この欄が届かない_kind_を分母に入れないこと():
    """**分母は「`data_file:` が実際に読まれる kind」だけ。**

    `_DATA_FILE_KINDS` に無い kind に `data_file:` を書いても、`answer()` は
    1文字も読みません。分母に入れると (1) 穴が実際より大きく見え、
    (2) 覆る条件（分母＝申告数）が永久に成り立たず、
    (3) 「その1件だけ足すのが安い」に従った回が**足しても何も変わらない要件**を
    引き当てます。

    **ここは名簿を写すのではなく、`answer()` の実際のふるまいで確かめます** ——
    名簿だけを見る検査は、分岐が増えた日に黙って外れます。
    """
    from datetime import date

    missing = "data/__no_such_instrument__.jsonl"
    probes = {
        "group_key": {"kind": "group_key", "key": "title_form"},
        "published_group": {"kind": "published_group", "count": 8,
                            "created_after": "2026-08-16",
                            "published_after": "2026-09-08", "settle_days": 4},
        "external": {"kind": "external", "what": "収益化の審査"},
    }
    for kind, need in probes.items():
        assert kind not in J._DATA_FILE_KINDS, f"{kind} を分母から外しています"
        plain = J.answer(dict(need), as_of=date.today(), lag=4)
        withf = J.answer(dict(need, data_file=missing), as_of=date.today(), lag=4)
        assert (plain.ready, plain.todo) == (withf.ready, withf.todo), (
            f"**{kind} は `data_file:` を読んでいます。**"
            f" `_DATA_FILE_KINDS` に足すこと: {plain} / {withf}")

    for kind in J._DATA_FILE_KINDS:
        assert kind in ("accrual", "after"), (
            "kind を足したなら、この検査に『書くと変わる』側の実測を足すこと")
