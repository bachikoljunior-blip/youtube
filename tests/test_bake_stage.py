"""**焼きがどこまで進んだかは、log ではなく `build/<題材>/` で見ること**（2026-09-04 22:0x）。

`data/rebake.log` の末尾は **最大 20分 古い**です（子が 8KB ずつためる・`_run_out()` の註）。
実測: 末尾が「分かりやすさの輪 2周目」のまま止まって見えた 20分 の間に、実物は
3周目・4周目 を終え、**音 62本 まで焼き終えていました。**

**待つ側が log だけを見ると「固まった」と読んで降ります** —— この回がまさに読みかけ、
`ps -o time=`（CPU 29分）と `build/` の mtime で、初めて生きていると分かりました。
`build/<題材>/` の mtime は子の buffer を通らないので、**そこだけは嘘をつきません。**
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ahead_sweep


def _mk(root: Path, topic: str, names: list[str]) -> None:
    d = root / "build" / topic
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        p = d / n
        if n in ("audio", "clips"):
            p.mkdir(exist_ok=True)
        else:
            p.write_text("x", encoding="utf-8")


def test_いちばん進んだ段を返す(tmp_path) -> None:
    _mk(tmp_path, "t", ["script.json", "clarity_loop.json", "audio", "clips", "final.mp4"])
    got = ahead_sweep.bake_stage("t", root=tmp_path)
    assert "焼き上がり" in got and "build/t/final.mp4" in got


def test_音まで来ていれば読み照合の輪(tmp_path) -> None:
    _mk(tmp_path, "t", ["script.json", "clarity_loop.json", "audio"])
    got = ahead_sweep.bake_stage("t", root=tmp_path)
    assert "読み照合の輪" in got


def test_台本だけなら分かりやすさの輪(tmp_path) -> None:
    _mk(tmp_path, "t", ["script.json"])
    assert "分かりやすさの輪" in ahead_sweep.bake_stage("t", root=tmp_path)


def test_無い題材は空(tmp_path) -> None:
    assert ahead_sweep.bake_stage("nope", root=tmp_path) == ""
    assert ahead_sweep.bake_stage("", root=tmp_path) == ""


def _ledger(tmp_path, monkeypatch, clarity: str, rebake: str) -> None:
    monkeypatch.setattr(ahead_sweep.config, "ROOT", str(tmp_path))
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    if clarity is not None:
        (d / "clarity_loop.jsonl").write_text(clarity, encoding="utf-8")
    if rebake is not None:
        (d / "rebake.jsonl").write_text(rebake, encoding="utf-8")


def test_done_が在れば本物の長さを返す(tmp_path, monkeypatch) -> None:
    """**`done` が 1件でも在れば、`seconds` の中央値**（焼き始め → 終わりの本物の長さ）。

    2026-09-04 07:40 に、この repo で初めて焼き直しが最後まで通りました
    （`seconds` 4692 ＝ **78.2分**）。それまで返していた下限は 37分 で、
    **2.1倍 外れて**いました。`rc` は見ません —— 落ちた焼きも、
    そこまでに同じ時間を使っています（測っているのは「成功したか」ではなく
    「**どれだけ待たされるか**」）。
    """
    _ledger(tmp_path, monkeypatch,
            '{"seconds": 600}\n',
            '{"kind": "start"}\n'
            '{"kind": "done", "rc": 1, "seconds": 4692}\n'
            '{"kind": "done", "rc": 0, "seconds": 4800}\n')
    mins, n = ahead_sweep.bake_minutes()
    assert n == 2
    # 中央値（偶数なら上側）＝ 4800秒 ＝ 80.0分。輪だけの下限（10分 ＋ 焼き）ではない
    assert mins == 80.0


def test_done_が無ければ輪の下限へ落ちる(tmp_path, monkeypatch) -> None:
    """**まだ1件も終わっていない間だけ**、分かりやすさの輪 ＋ 焼き の**下限**。"""
    _ledger(tmp_path, monkeypatch, '{"seconds": 600}\n', '{"kind": "start"}\n')
    mins, n = ahead_sweep.bake_minutes()
    assert (mins, n) == (10.0 + ahead_sweep.BAKE_RENDER_MIN, 1)


def test_どちらも無ければ何も返さない(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ahead_sweep.config, "ROOT", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    assert ahead_sweep.bake_minutes() == (None, 0)


#: 焼き上がってから枠までに要る余白（`videos.insert` ＋ 予約の置き換え）。
#: `REBAKE_LEAD` の註の「上げの余裕（20分）」と同じ数。
BAKE_UPLOAD_MARGIN_MIN = 20.0


def test_枠までの線は実測より長いこと() -> None:
    """**`REBAKE_LEAD` は「1回の焼きの長さ ＋ 上げ」より長くなければ意味がありません。**

    100分 の線は、実測 78.2分 ＋ 上げ に対して余裕が 20分 しかなく、しかも
    読み照合の輪の 32分 は**誤読 0件 で1周**の値でした（誤読が出れば +30分）。
    この検査は、次に誰かが線を実測へ近づけたときに鳴ります。

    ## **`× 1.5` を「＋ 上げの余裕」へ替えました**（2026-09-04 21:3x）

    同じ日に 2つ 変わり、**掛け算のほうは満たせない形**になっていました:

        1. `REBAKE_RUN_TIMEOUT = int(REBAKE_LEAD.total_seconds())`
           ＝ **焼きは `REBAKE_LEAD` を超えたところで必ず殺される**
           （実測 16:39 の `rc=124`）。だから `bake_minutes()` の**最大は
           構造上 `REBAKE_LEAD` を超えられません。**
        2. `bake_minutes()` は `done` 5件 で**中央値から最大へ**切り替わった。

    その2つが重なると `lead >= max * 1.5` は「**最大が lead の 2/3 を超えたら赤**」
    という意味になり、超えた回の直し方は **`REBAKE_LEAD` を上げる**しかありません。
    ところが上げると殺す線も一緒に上がるので、**次はもっと長い `done` が出て、
    また 2/3 を超えます** —— 追いつけない検査です。
    実測でいうと、いまの最大 90.0分 に対して線 150分 は通りますが、
    **オーナー指示の読み照合の輪が 2周 した焼き（＞90分）が1件 最後まで通れば、
    100分 を超えて赤**になります。**輪が正しく回った日にだけ赤くなる検査**でした。

    要るのは倍率ではなく「**焼き上がってから枠までに、上げるぶんが残っているか**」で、
    それは足し算です（`BAKE_UPLOAD_MARGIN_MIN` ＝ `REBAKE_LEAD` の註と同じ 20分）。

    **覆る条件**: `REBAKE_RUN_TIMEOUT` が `REBAKE_LEAD` と切り離されたら、
    最大は線に張り付かなくなるので、倍率へ戻してよい。
    """
    mins, n = ahead_sweep.bake_minutes()
    if mins is None or not n:
        pytest.skip("焼きの長さがまだ 1件も測れていない")
    lead = ahead_sweep.REBAKE_LEAD.total_seconds() / 60.0
    assert lead >= mins + BAKE_UPLOAD_MARGIN_MIN, (
        f"線 {lead:.0f}分 が実測 {mins:.1f}分 ＋ 上げ {BAKE_UPLOAD_MARGIN_MIN:.0f}分 に届いていません")


def test_done_が5件_に届いたら上側_最大_を返す(tmp_path, monkeypatch) -> None:
    """**待つ側にとって、外れて痛いのは短い側だけ。**

    この数の使い道は1つで、`src/next_slot.py` が回に
    「**この回は、終わるまで待つこと。N分 は要ります**」と刷ります。
    短い側へ外れた回は差し替えの前に降り、焼く側は**その回の道連れで死にます**
    （焼く側はこの器の中の背景プロセス）。

    実測（`data/rebake.jsonl`・2026-09-04・5件 とも同じ1本）は
    中央値 78.2分／最大 90.0分 で、**中央値は 11.8分（13%）短く言って**いました。
    しかも最大の 5,400秒 は `rc=124`（`REBAKE_RUN_TIMEOUT` に殺された）＝
    「90分 かかった」ではなく「**90分 では終わらなかった**」ので、まだ下限です。
    """
    rows = "".join(f'{{"kind": "done", "rc": 0, "seconds": {s}}}\n'
                   for s in (4692, 3325, 5400, 4977, 3737))
    _ledger(tmp_path, monkeypatch, '{"seconds": 600}\n', rows)
    mins, n = ahead_sweep.bake_minutes()
    assert n == 5
    assert mins == 90.0, "5件 に届いたら中央値（78.2）ではなく最大（90.0）"


def test_done_が4件_までは中央値のまま(tmp_path, monkeypatch) -> None:
    """**切り替えの線は `BAKE_UPPER_AT`。** n が小さいうちの最大は 1件 の外れ値そのもの
    なので、そこまでは中央値で読みます（`bake_minutes()` の註）。"""
    rows = "".join(f'{{"kind": "done", "rc": 0, "seconds": {s}}}\n'
                   for s in (4692, 3325, 5400, 4977))
    _ledger(tmp_path, monkeypatch, '{"seconds": 600}\n', rows)
    mins, n = ahead_sweep.bake_minutes()
    assert n == 4 and n < ahead_sweep.BAKE_UPPER_AT
    # 中央値（偶数なら上側）＝ 4977秒 ＝ 83.0分。最大（5400 ＝ 90.0分）ではない
    assert mins == 83.0
