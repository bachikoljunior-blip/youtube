"""**「待てば日が出ます」は、取り直せば増える計器には言ってはいけない。**

2026-08-27 夜（最適化の回）。同じ日の朝の回が `kind: on_date` にだけ
`needs.data_file:` を入れました ——「**時計は来ています。足りないのはデータの
ほうです**」。**`accrual` には同じ穴がそのまま残っていて、そちらのほうが
危ない**: 返す文が「**まだ数えはじめたところです。この回は何もしないのが
正解です**」だからです（`on_date` は少なくとも「待て」としか言わない）。

実測（前提「深い題のショートは `s-` の題のショートより上」）:

    `deep_short_days()` が読む `data/video_forms.json`  取り直したのは **08-26**
    その控えが分類し終えている いちばん新しい公開日      **08-24**
    深い題のショートを公開しはじめた日                  **08-25**
    08/25・08/26・08/27 の公開（両群とも在る）           控えに **1本も無い**

`falsified_if` が要る「両群がそろう公開日」は**もう3日ぶん公開済み**でした。
0 なのは日が足りないからではなく、**控えが 08-24 で止まっている**から。
その控えを書き直すのは `src/rpm_mix` の主処理だけで、**1周の中で誰も撃たない**
＝ **待っても永久に 0**。`python -m src.rpm_mix --forms` を撃つと **0日 → 1日**、
その場で判定日（08-31）が出ました。

この検査が守るのは2つ:

1. `data_file:` を申告した `accrual` が、計器が古いあいだ**取り直す手**を出すこと
2. その手が、数が 0 を離れた**あと**も出ること（＝日の出る道にも載ること）

**2 が要る理由**: 0 → 1 になった瞬間この要件は日の出る道へ移ります。そこに
載せないと、翌日また控えが古びても誰も言わず、**数は 1 のまま伸び率だけが
落ちて、判定日が毎日 後ろへ滑ります。理由はどこにも出ません。**

**この検査が落ちてよいとき**: 1周ごとに全計器を取り直す作りにしたなら、
`_stale_todo` は毎回 黙るので、この検査ごと外してよい。
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc                                    # noqa: E402


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    """`ROOT` を差し替えて、控え型の計器（ファイル全体で1つの JSON）を作る。"""

    def _make(hours_ago: float) -> dict:
        at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        p = tmp_path / "data" / "video_forms.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"at": at.isoformat(), "forms": {"a": "ショート"}},
                                ensure_ascii=False, indent=1), encoding="utf-8")
        monkeypatch.setattr(dc, "ROOT", tmp_path)
        return {"kind": "accrual", "count_expr": "0", "need": 3,
                "since": "2026-08-25", "data_file": "data/video_forms.json",
                "refresh": "python -m src.rpm_mix --forms"}

    return _make


def test_控えが古ければ取り直す手を出す(cache):
    need = cache(hours_ago=31)                                 # 実測と同じ 31時間
    todo = dc._stale_todo(need)
    assert todo, "古い控えを読んでいるのに、何も言っていません"
    assert "python -m src.rpm_mix --forms" in todo, \
        "`refresh:` に書いたコマンドが出ていません（次の回が撃てません）"
    assert "待っても増えません" in todo, \
        "「待てば出る」と読める文のままです ——それがこの穴そのものでした"


def test_控えが新しければ黙る(cache):
    """**毎周 取り直している計器で鳴らないこと。** 鳴れば、次の回は無視を覚えます。"""
    assert dc._stale_todo(cache(hours_ago=1)) == ""


def test_data_fileを書いていない要件には効かない(cache):
    """**書いていない要件は、今までどおり時計だけで通す**（`on_date` と同じ方針）。"""
    need = cache(hours_ago=99)
    need.pop("data_file")
    assert dc._stale_todo(need) == ""


def test_数が0のときの答えに手が載る(cache):
    """**「この回は何もしないのが正解です」に化ける道**（`Verdict.warming`）。"""
    need = cache(hours_ago=31)
    ans = dc._ans_accrual(need, date(2026, 8, 27))
    assert ans.ready is None and ans.todo, \
        "0 のまま日が出ないのに、取り直す手が載っていません"


def test_数が0を離れたあとも手が載る(cache):
    """**ここが 2026-08-27 に踏みかけたところ。**

    0 → 1 で日の出る道へ移った瞬間に黙ると、**翌日また古びても誰も言いません。**
    `why` にも `todo` にも載せます（日の出る道は `warming` ではないので、
    印字されるのは `why` のほう）。
    """
    need = cache(hours_ago=31)
    need["count_expr"] = "1"
    ans = dc._ans_accrual(need, date(2026, 8, 27))
    assert ans.ready is not None, "1件 積んでいるのに日が出ていません"
    assert ans.todo, "日が出る道で、古い計器の申告が消えています"
    assert "取り直す" in ans.why or "取り直すまで" in ans.why, \
        f"滑っている理由が同じ行に出ていません: {ans.why}"


def test_数が足りていれば黙る(cache):
    """**もう足りているなら、取り直す用がありません。**"""
    need = cache(hours_ago=99)
    need["count_expr"] = "5"
    ans = dc._ans_accrual(need, date(2026, 8, 27))
    assert ans.ready is not None and not ans.todo


def test_newest_pointが控え型を読む(tmp_path):
    """**1行1件でない計器**。前の版は全行 落ちて「1点も読めません」に化けた。"""
    p = tmp_path / "video_forms.json"
    p.write_text(json.dumps({"at": "2026-08-26", "forms": {}}, indent=1),
                 encoding="utf-8")
    got = dc.newest_point(p)
    assert got is not None, "控え型（ファイル全体で1つの JSON）が読めていません"
    assert got.date() == date(2026, 8, 26)


def test_jsonlはこれまでどおり読める(tmp_path):
    p = tmp_path / "views.jsonl"
    p.write_text('{"at": "2026-08-26T01:53:00+09:00"}\n'
                 '{"at": "2026-08-27T09:00:00+09:00"}\n', encoding="utf-8")
    got = dc.newest_point(p)
    assert got is not None and got.astimezone(timezone.utc).day == 27
