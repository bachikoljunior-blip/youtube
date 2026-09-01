"""**枠が尽きていても、0単位 で撃てる手が残っていれば `fix` の連の門は止める。**

## なぜこの検査が要るか（2026-09-01 に踏んだ）

`run_marker.quota_is_out()` は 2026-09-01 03:5x に足された免除で、
**日枠が尽きた窓では `fix` の連の門を無条件で通していました。**
その理由として註が引いていたのは `docs/trigger_main.md` §4 の表:

    upload   `videos.insert` 1,600単位          ← 枠
    fix      ← **枠が尽きている回に残るのは、事実上これだけ**

**この repo は、その表を3度 実測で否定しています** ——
`videos.insert` は日枠を1単位も使わず、尽きていても通ります
（`tests/test_insert_never_marked_ok.py` に 8/17 05:2x と 08/27 の3本）。
`improve` も、5つの道のうち **台本を書き直す・計算を厚くする** の2つは 0単位 で、
残る 50単位 は `upload_cap.RESERVE_UNITS = 400` が**その improve のために**
残しています（`_ledger_hold()` の返り文が、そう印字します）。

**いちばん強い証拠は、免除を書いた関数の隣の枝です** —— 免除しなかったときの
`ap.error` は「**`improve` は、いつでも在ります**（規則3）。
**この門は、そこへ戻す門です。**」と印字していました。
**同じ関数の2つの枝が、逆のことを言っていた**ということです。

## 代金（実測 2026-09-01 08:4x）

    `run_marker.fix_run_len()`  **23**   ← 23回 続けて `fix`。全部この免除で通った
    規則3 が固定された 08-31 以降の ship 88件: `improve` 4.5% ／ `upload` **0件**

## 覆る条件

- `videos.insert` が同じ 403 で落ちるようになったら（＝枠が1つに統合された）、
  `free_alternatives()` の `upload` の行を落とすこと
- **次に公開される1本が無い窓では、`free_alternatives()` は空を返します。**
  そのときは免除が今までどおり効きます（この検査の3件目が、そこを見ます）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import run_marker  # noqa: E402


def test_free_alternatives_is_wired_into_the_waiver() -> None:
    """**免除は `free_alternatives()` が空のときだけ。**

    ここが外れると、門は 2026-09-01 08:4x 以前の「無条件で通す」に戻ります
    （そのとき `fix` は 23回 続いていました）。
    """
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert "_free = free_alternatives() if _out else []" in src, (
        "免除の手前で `free_alternatives()` を撃っていません")
    assert "and _out and not _free:" in src, (
        "免除の条件に `not _free` が入っていません —— "
        "**枠が尽きただけで無条件に通す形に戻っています**")


def test_free_alternatives_names_improve_and_upload_when_a_next_video_exists() -> None:
    """**次の枠の1本が在れば、`improve` と `upload` を名指しする。**

    名指しできない門は、種別の語を書き換えて通されるだけです
    （`near_deadlines()` の註と同じ理由）。
    """
    out = run_marker.free_alternatives()
    if not out:
        # 次に公開される1本が無い窓。**そのときは空が正しい**（下の検査が見ます）。
        from src import next_slot
        assert next_slot.next_video() is None
        return
    joined = "\n".join(out)
    assert "improve" in joined, "0単位 の `improve` が名指しされていません"
    assert "upload" in joined, "日枠を使わない `upload` が名指しされていません"
    assert "0単位" in joined, "**値段**が出ていません（名指しは値段まで）"


def test_premise_is_always_there(monkeypatch) -> None:
    """**`premise` は、次の1本が無くても在ります**（2026-09-01 に足した）。

    ## なぜ、この2件の期待を裏返したか

    ここには「次の1本が無ければ空」「読めない回も空（＝緩む側）」の2件が
    ありました。**どちらも `next_slot` の話です。**
    `premise`（`config/hypotheses.yaml` に前提を1件 立てる）は
    `next_slot` を1度も見ません —— **ファイルを1つ書くだけで、
    YouTube に1単位も触りません。**

    **だから「打つ手が無い回」は、もう在りません。**
    それは門の骨抜きではなく逆です: `eta.py` が毎周 名指ししている
    **唯一の到達日を動かす手**を、`fix` を通すために「無い」ことにしていたのが
    前の姿でした（実測 08-25 以降の ship 326件 ＝ `fix` 76%・`verdict` 6%、
    台帳は 21件・**09-12 に空**）。

    **覆る条件**: `config/hypotheses.yaml` が読めない回は、この行は出ません
    （下の検査）。台帳が空になっても行は出ます —— **空の台帳こそ、
    立てるべき回です。**
    """
    from src import next_slot

    monkeypatch.setattr(next_slot, "next_video", lambda *a, **k: None)
    out = run_marker.free_alternatives()
    assert out, "次の1本が無い回でも `premise` は在ります"
    assert "premise" in "\n".join(out)
    assert "0単位" in "\n".join(out), "**値段**が出ていません（名指しは値段まで）"


def test_next_slot_failure_does_not_take_premise_down(monkeypatch) -> None:
    """`next_slot` が落ちても `premise` は残る（**別々の入力です**）。"""
    from src import next_slot

    def boom(*a, **k):
        raise RuntimeError("読めません")

    monkeypatch.setattr(next_slot, "next_video", boom)
    out = run_marker.free_alternatives()
    assert [x for x in out if "premise" in x], (
        "`next_slot` の失敗が `premise` まで落としています —— 別の入力です")
    assert not [x for x in out if "improve" in x], (
        "`next_slot` が読めないのに `improve` を名指ししています（推測で門を締めない）")


def test_premise_is_gone_when_the_ledger_file_is_gone(monkeypatch, tmp_path) -> None:
    """**在りもしない手を「在る」と言わないこと。** 台帳が無ければ黙る。"""
    from src import next_slot

    monkeypatch.setattr(next_slot, "next_video", lambda *a, **k: None)
    monkeypatch.setattr(run_marker.Path, "exists", lambda self: False)
    assert run_marker.free_alternatives() == []


def test_the_false_quota_table_is_gone_from_the_docstring() -> None:
    """**免除の理由に、否定ずみの表を貼り直さないこと。**

    `videos.insert` を「← 枠」と書いた表が `quota_is_out()` の註に戻ったら、
    次に来た回はまた「5つのうち4つが選べなかった」と読みます。
    """
    doc = run_marker.quota_is_out.__doc__ or ""
    assert "upload   `videos.insert` 1,600単位          ← 枠" not in doc, (
        "否定ずみの表が註に戻っています（`tests/test_insert_never_marked_ok.py`）")
    assert "枠の向こう側なのは `means`" in doc, (
        "**本当に枠の向こう側なのは何か**が書かれていません")
