"""**`fix` の連の門**（`scripts/run_marker.FIX_RUN_CAP`）が生きていることを見る。

## なぜ要るか（2026-09-01・最適化の回）

`scripts/drift.py` は 2026-08-24 から、この輪が `fix` に流れていることを
**正しく印字し続けていました。** それでも 7日 後の実測（直近7日・ship 358件）は

    fix 269件（75%）／ verdict 16件（4%）／ **直近20回の verdict 0件**

で、**比は1つも動いていません。印字は行動を変えません。**
`scripts/run_marker.py` は自分の `--kind` の門の註で、同じことを
既に書いています ——「**註や警告ではなく、通さないことだけが効いています**」。

**この検査が守っているのは「通さないこと」のほう**です。
註だけ残して `ap.error` を外す直し方は、実測で3回 戻っています
（`run_marker.ship()` の docstring）。**だから門そのものを見ます。**

**覆る条件**: `FIX_RUN_CAP` の註にある3つ。とくに
**「`fix` 比が下がらないまま `fix_gate` の行だけ増える」**なら、
種別の語を書き換えて通されているので、この門ごと作り直すこと
（そのときは、この検査も一緒に書き直す）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import run_marker as rm  # noqa: E402


def _write(tmp_path: Path, kinds: list[str]) -> Path:
    p = tmp_path / "runs.jsonl"
    rows = []
    for k in kinds:
        rows.append({"at": "2026-09-01T00:00:00+09:00", "kind": "ship", "ship_kind": k})
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_連の数え方は末尾から_他の種別で止まる(tmp_path: Path) -> None:
    assert rm.fix_run_len(_write(tmp_path, ["fix"] * 9)) == 9
    # 途中に別の種別が入ったら、そこで切れる
    assert rm.fix_run_len(_write(tmp_path, ["fix"] * 9 + ["verdict"] + ["fix"] * 2)) == 2
    # **末尾が fix でなければ 0**
    assert rm.fix_run_len(_write(tmp_path, ["fix"] * 9 + ["upload"])) == 0
    assert rm.fix_run_len(tmp_path / "ない.jsonl") == 0


def test_ship以外の行は連に数えない(tmp_path: Path) -> None:
    """`--write` の印と、この門自身の `fix_gate` の行を数えたら、連が伸びてしまう。"""
    p = tmp_path / "runs.jsonl"
    rows = [{"kind": "ship", "ship_kind": "fix"} for _ in range(3)]
    rows.insert(1, {"kind": "fix_gate", "run_len": 3})
    rows.insert(2, {"kind": "run"})
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert rm.fix_run_len(p) == 3


def test_しきいは実測で置いた値のまま() -> None:
    """**4 は勘ではありません**（`fix` の連: 中央 2・平均 3.8・最長 15）。

    中央 2 の普通の連を触らず、長い連の後ろだけ止める値です。
    **上げるなら、`data/runs.jsonl` を数え直してからにすること。**
    """
    assert rm.FIX_RUN_CAP == 4


def test_連が上限に達したら_fixは通らない(tmp_path: Path, monkeypatch) -> None:
    """**この検査が本体です。** 註ではなく `ap.error` が生きているかを見ます。

    **枠は「開いている」に固定します**（2026-09-01）。実物の
    `data/api_calls.jsonl` を読ませると、**枠が尽きている窓で走らせた回だけ
    この検査が赤くなります** —— 見ているのは門であって、その日の枠ではありません。
    """
    p = _write(tmp_path, ["fix"] * rm.FIX_RUN_CAP)
    monkeypatch.setattr(rm, "MARKS", p)
    monkeypatch.setattr(rm, "quota_is_out", lambda: (False, ""))
    with pytest.raises(SystemExit) as e:
        rm.main(["--ship", "fix: 通ってはいけない", "--kind", "fix",
                 "--lever", "none", "--moves", "0", "--no-reflect"])
    assert e.value.code != 0
    # **止めたことが残っていること**（残らないと、効いたかを次の回が数えられない）
    tail = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert tail[-1]["kind"] == "fix_gate"
    assert tail[-1]["run_len"] == rm.FIX_RUN_CAP


def test_上限の1つ手前なら_fixは通る(tmp_path: Path, monkeypatch) -> None:
    """**`fix` の禁止ではありません。** 止めているのは連だけ。"""
    p = _write(tmp_path, ["fix"] * (rm.FIX_RUN_CAP - 1))
    monkeypatch.setattr(rm, "MARKS", p)
    calls: list = []
    monkeypatch.setattr(rm, "ship", lambda *a, **k: calls.append((a, k)) or 0)
    rm.main(["--ship", "fix: これは通る", "--kind", "fix",
             "--lever", "none", "--moves", "0", "--no-reflect"])
    assert calls, "上限の手前の `fix` は通らなければならない"


@pytest.mark.parametrize("kind", ["verdict", "upload", "means", "improve"])
def test_連が長くても_到達日を動かしうる種別は通る(kind, tmp_path, monkeypatch) -> None:
    """**逃げ場のない門にしないこと。** 規則（1日1本）は毎日 `upload` を要求している。"""
    p = _write(tmp_path, ["fix"] * 20)
    monkeypatch.setattr(rm, "MARKS", p)
    calls: list = []
    monkeypatch.setattr(rm, "ship", lambda *a, **k: calls.append((a, k)) or 0)
    rm.main(["--ship", f"{kind}: 通る", "--kind", kind,
             "--lever", "none", "--moves", "0", "--no-reflect"])
    assert calls, f"{kind} は連の長さに関係なく通らなければならない"


def test_代わりの手を名指ししている() -> None:
    """**名指しできない門は、種別の語を書き換えて通されるだけ**になる。"""
    alt = rm.near_deadlines()
    assert alt, "`config/hypotheses.yaml` から期限の近い前提が引けていない"
    assert all("[" in a for a in alt), "腕（lever）が出ていない"


def test_名指しに_閉じた前提を混ぜない() -> None:
    """**閉じた前提を「代わりの手」に出さないこと**（2026-09-01 に踏んだ）。

    実測: この関数は `verdict` / `closed` / `result` を見ていましたが、
    この台帳の印は **`closed_on:`** です。開いている前提は 25件 と出て、
    実物は 23件（`eta.py` / `deadline_check.py` と同じ数）。
    期限の近い順なので、**こぼれた2件がそのまま先頭**に来ていました ——
    門が名指しした3つのうち2つが、8日前・9日前に閉じた前提です。

    **正本は `src/judgeable.deadlines()` と同じ鍵**（`closed_on`）。
    """
    import yaml

    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    closed = {str(h.get("claim"))[:52] for h in doc["hypotheses"] if h.get("closed_on")}
    named = rm.near_deadlines(limit=8)
    assert named, "期限の近い前提が1件も引けていない"
    for line in named:
        claim = line.split("] ", 1)[-1]
        assert claim not in closed, f"閉じた前提を名指ししています: {line}"


def test_枠が尽きている窓では_連の門は止めない(tmp_path: Path, monkeypatch) -> None:
    """**逃げ場のない門にしないこと**（2026-09-01 に踏んだ）。

    **判定は観測した 403 です**（`upload_cap.day_quota().open`）——
    こちらの見積りでは緩められません。

    ## **この検査の前提を、2026-09-01 08:4x に直しました**

    ここには「門が名指しする4つは、どれも枠を要ります（`upload` 1,600単位／
    `improve` 50単位／…）」と書いてありました。**誤りです** ——
    `videos.insert` は日枠を1単位も使わず、尽きていても通ります
    （`tests/test_insert_never_marked_ok.py` に実測3度）。`improve` も
    **台本を書き直す・計算を厚くする**の2つは 0単位 で、残る 50単位 は
    `upload_cap.RESERVE_UNITS = 400` が**その improve のために**残しています。

    **代金は `fix` 23連**（`run_marker.fix_run_len()` の実測 2026-09-01 08:4x）。

    **だから免除は「枠が尽きた」だけでは効きません** ——
    `free_alternatives()` が**空のとき**だけです。ここはその「空」の側、
    つまり**次に公開される1本が無い窓**を見ています
    （在るときに止まることは `tests/test_fix_gate_free_alternatives.py`）。
    """
    p = _write(tmp_path, ["fix"] * 20)
    monkeypatch.setattr(rm, "MARKS", p)
    monkeypatch.setattr(rm, "quota_is_out", lambda: (True, "**尽きています**（テスト）"))
    # **次の枠の1本が無い窓**（＝ 0単位 で撃てる手も残っていない）。
    # ここを実物のままにすると、この検査は repo の予約表しだいで色が変わります。
    monkeypatch.setattr(rm, "free_alternatives", lambda: [])
    calls: list = []
    monkeypatch.setattr(rm, "ship", lambda *a, **k: calls.append((a, k)) or 0)
    rm.main(["--ship", "fix: 枠が尽きた窓なので通る", "--kind", "fix",
             "--lever", "none", "--moves", "0", "--no-reflect"])
    assert calls, "枠が尽きている窓では、連の門は止めてはいけない"
    # **通したことが残ること。** 残らないと、次の回は `fix_gate` の行数を
    # 「門が効いた回数」と読みます。
    tail = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    gates = [r for r in tail if r.get("kind") == "fix_gate"]
    assert gates and gates[-1].get("waived") is True, (
        "枠のせいで通した回に `waived` が立っていない"
    )


def test_枠が読めない回は_門は今までどおり止める(monkeypatch) -> None:
    """**読めないことを「尽きている」と読まないこと**（`upload_cap.day_quota()` と同じ姿勢）。

    ここが逆向きだと、**帳面が壊れた回は毎回この門を素通り**します。
    """
    from src import upload_cap

    def boom(*a, **k):
        raise RuntimeError("帳面が読めない（テスト）")

    monkeypatch.setattr(upload_cap, "day_quota", boom)
    out, line = rm.quota_is_out()
    assert out is False, "読めない回を『尽きている』と読んではいけない"
    assert "読めません" in line
