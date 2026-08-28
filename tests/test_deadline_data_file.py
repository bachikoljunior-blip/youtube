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

    class _V:
        needs = [{"kind": "on_date"}, {"kind": "accrual", "data_file": "data/x.jsonl"}]

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
