"""**積みが止まった要件が「あと1日」と言い続けないこと。**（2026-08-27・最適化の回）

## 何が見えていなかったか

`_ans_accrual` の `rate = have / (as_of - since).days` は**生涯の平均**です。
積みが完全に止まっても分母が伸びるぶんゆっくり下がるだけなので、
**止まった当日も「あと N日」と出続けます。**

実測 2026-08-27 22:3x（前提「長尺の生成が落ちる主因は『過去の図と重なっています』の
門で、公開が増えるほど落ちる率が上がる」）::

    台帳   要 6 ／ いま 5（3日で **1.67/日**）→ **あと 1日 ＝ 08-28**
    実物   この要件が数えるのは**長尺の生成失敗**（`data/batch_runs.jsonl`）:
           08/24  7/21 通過（失敗 14）／ 08/26  25/28（89%）／ **08/27  15/15（100%）**
           → **今日の失敗は 0件。** 1.67/日 は 08/24〜08/26 の平均

しかもこの要件は**失敗を数えている**ので、生成が直るほど**永久に満ちません** ——
それでも台帳は毎周「あと1日」と言います。**「待てば来る」と読めます。**

## 直し方（**日付は動かしません**）

控えに `have`（その回の実数）を足し、**日をまたいだ前の点との差**を出します。
差が 0 なら、その場で「**直近 N日 は1件も増えていません**」を同じ行に並べます。

**日付を 2点 の差で動かさないのは、churn を戻さないため**です
（`_rate_scatter` の註: 伸び率の見積りが揺れただけで **3日に4回** 期限が
書き換わり、前提もデータの来る日も1日も動きませんでした）。
`CLAUDE.md`「**裸の『届きません』を出さないこと。何を固定したせいでそう出たのかを
同じ行に並べること**」と同じ扱いです。

## 覆る条件

止まりを**日付に**反映してよくなるのは、`_recent_rate` が2点ではなく
**窓（3点以上）**で解けるようになったときです。それまでは印字だけ。
1日より速く動く要件が出てきたら、控えの鍵を「日」から「時」へ落とすこと。
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check                                          # noqa: E402

KEY = "sum(1 for r in rows('x.jsonl'))"


def _log(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "est.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return p


def test_stall_is_detected(tmp_path: Path) -> None:
    """前の点と同じ数なら、`delta <= 0` を返すこと。"""
    p = _log(tmp_path, [{"at": "2026-08-26", "key": KEY, "rate": 1.67, "have": 5}])
    got = deadline_check._recent_rate(KEY, 5, date(2026, 8, 28), path=p)
    assert got is not None, "日をまたいだ点が在るのに、直近の伸び率が出ていません"
    r_rate, r_days, r_delta = got
    assert r_delta == 0 and r_days == 2 and r_rate == 0.0, (
        f"止まりを見つけられていません: {got}")


def test_same_day_points_are_not_a_rate(tmp_path: Path) -> None:
    """同じ日の点どうしから「1日あたり」を作らないこと（0除算と偽の 0件）。"""
    p = _log(tmp_path, [{"at": "2026-08-27", "key": KEY, "rate": 1.67, "have": 5}])
    assert deadline_check._recent_rate(KEY, 5, date(2026, 8, 27), path=p) is None


def test_rows_without_have_are_dropped_not_guessed(tmp_path: Path) -> None:
    """`have` を控える前の行から、`rate × 経過` を逆算して埋めないこと。

    控えに `since` が無いので、逆算すると丸めのぶんだけ**偽の増減**が生まれます。
    """
    p = _log(tmp_path, [{"at": "2026-08-25", "key": KEY, "rate": 1.0},
                        {"at": "2026-08-26", "key": KEY, "rate": 1.5}])
    assert deadline_check._recent_rate(KEY, 5, date(2026, 8, 28), path=p) is None


def test_growth_is_reported_as_growth(tmp_path: Path) -> None:
    """伸びている回は、その伸び率をそのまま返すこと（止まり扱いにしない）。"""
    p = _log(tmp_path, [{"at": "2026-08-26", "key": KEY, "rate": 1.0, "have": 4}])
    r_rate, r_days, r_delta = deadline_check._recent_rate(KEY, 10, date(2026, 8, 28), path=p)
    assert (r_delta, r_days) == (6, 2) and abs(r_rate - 3.0) < 1e-9


def test_same_day_rows_count_as_one_point(tmp_path: Path) -> None:
    """**1鍵1日1行は、読む側でも守ること。**（2026-08-27・最適化の回）

    控えの「1鍵1日1行」は**書く側の約束**でしかありません。同じ日に2行 入る道が
    実際に出ました —— `have` を控え始めた回が、欄の足りない今日の行を
    書き直させたので、`have` 無しと `have` 付きが1日に2行 並びます
    （実測 2026-08-27: 3鍵 が2行ずつ）。

    `_rate_scatter` が数えているのは「**何日ぶん観測したか**」なので、
    同じ日を2回 数えると `n_pts` が水増しされ、
    「まだ N点 なので、この帯は下限です」の註が1回 早く消えます
    ——**帯を狭いと読ませる向き**です。
    """
    p = _log(tmp_path, [
        {"at": "2026-08-26", "key": KEY, "rate": 1.0},
        {"at": "2026-08-27", "key": KEY, "rate": 2.0},             # have 無しの旧行
        {"at": "2026-08-27", "key": KEY, "rate": 2.0, "have": 5},  # 書き直したほう
    ])
    got = deadline_check._rate_scatter(KEY, path=p)
    assert got is not None
    _spread, n_pts = got
    assert n_pts == 2, f"同じ日を2回 数えています（{n_pts}点）"


# --- **今日の点と比べないこと**（2026-08-29 に足した。**自分と比べていた**） ---
#
# `record_estimates()` は **1鍵1日1行**を、印字する道で毎回 書きます。
# だから**その日の最初の回**が今日の行を積んだ瞬間、`pts[-1]` は今日の行になり、
# `days = 0` → `days < 1` で **`None`** —— 上の警告は**その日の2回目以降、
# 1度も出ません。** この機械は毎日 15周 前後 走るので、
# **14/15 の回が警告なしの版**を読んでいました。
#
# 実測 2026-08-29 02:5x（この関数が 08-27 夜に作られた、まさにその前提）::
#
#     控え  08-27 have=5 ／ 08-28 have=5 ／ 08-29 have=5   ← **3日 動いていない**
#     印字  「要 6 ／ いま 5（5日で 1.00/日）→ **あと 1日**」（**警告なし**）
#     実物  長尺の生成失敗は 08/27 **0/15**・08/28 **0/7**・08/29 **0/4**
#           ＝ **26本 連続で失敗ゼロ**。1.00/日 は 08/24 と 08/26 の平均


def test_今日の行が在っても_前の日の点と比べる(tmp_path) -> None:
    """**その日の最初の回が控えを書いた後も、警告が出ること。**"""
    p = _log(tmp_path, [{"at": "2026-08-28", "key": KEY, "rate": 1.25, "have": 5},
                        {"at": "2026-08-29", "key": KEY, "rate": 1.0, "have": 5}])
    got = deadline_check._recent_rate(KEY, 5, date(2026, 8, 29), path=p)
    assert got is not None, "今日の行が在るだけで、止まりの警告が消えています"
    r_rate, r_days, r_delta = got
    assert (r_delta, r_days, r_rate) == (0, 1, 0.0)


def test_今日の行しか無ければ_これまでどおり出さない(tmp_path) -> None:
    # 日をまたいだ2点が無いので「率」になりません（元からの規則）
    p = _log(tmp_path, [{"at": "2026-08-29", "key": KEY, "rate": 1.0, "have": 5}])
    assert deadline_check._recent_rate(KEY, 5, date(2026, 8, 29), path=p) is None


def test_止まりの長さは_いちばん新しい点との差ではない(tmp_path) -> None:
    """3日 止まっていたら「3日」と言うこと（2点だけ見ると「1日」になります）。"""
    p = _log(tmp_path, [{"at": "2026-08-26", "key": KEY, "rate": 1.7, "have": 5},
                        {"at": "2026-08-27", "key": KEY, "rate": 1.6, "have": 5},
                        {"at": "2026-08-28", "key": KEY, "rate": 1.2, "have": 5},
                        {"at": "2026-08-29", "key": KEY, "rate": 1.0, "have": 5}])
    # 2点しか見ない側は「1日」
    assert deadline_check._recent_rate(KEY, 5, date(2026, 8, 29), path=p)[1] == 1
    # 連なりで数える側は 08-26 まで遡る（今日の行は入れない）
    assert deadline_check._stall_days(KEY, 5, date(2026, 8, 29), path=p) == 3


def test_止まっていなければ_止まりの長さは出ない(tmp_path) -> None:
    p = _log(tmp_path, [{"at": "2026-08-27", "key": KEY, "rate": 1.6, "have": 4},
                        {"at": "2026-08-28", "key": KEY, "rate": 1.2, "have": 5}])
    # 直前の点が 5、その前は 4 → 止まりは 1日 ぶんだけ
    assert deadline_check._stall_days(KEY, 5, date(2026, 8, 29), path=p) == 1
    # いまの数が控えのどれとも違えば、連なりは無い
    assert deadline_check._stall_days(KEY, 9, date(2026, 8, 29), path=p) is None


def test_止まりの長さは_日付を動かさない(tmp_path) -> None:
    """**印字だけ。** 日付に効かせてよくなるのは、窓で解けるようになったとき
    （このファイルの冒頭の「覆る条件」）。"""
    import inspect

    src = inspect.getsource(deadline_check._ans_accrual)
    i = src.index("_stall_days")
    # `days` を組み立てている行より後ろでしか使っていないこと
    assert "days = " not in src[i:i + 400].split("note +=")[0], \
        "止まりの長さが、判定日の計算に混ざっています"
