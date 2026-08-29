"""`deadline_check.py --gate` —— **期限のずれを、Stop フックで止める。**

## なぜ、赤い検査の**上に**さらに門を置いたのか（2026-08-30・最適化の回）

`tests/test_deadline_check.py::test_遅すぎる期限が残っていないこと` は、
その docstring で**まさにこの問題を予言していました**:

> **印字は 666 commits 効きませんでした。赤い検査は同じ日に効きました。**

ところが 2026-08-30 に測ると、**その赤い検査自身が ship 358件 を素通り**して
いました（08/24〜08/30。そのあいだ到達予測は 2026-12-21 → 2027-01-10 ＝ **+20日
遠のいた**）。中身は `opening_motion` —— 判定できるのは 09-22 なのに期限 10-07 で
**15日**。`eta.py` は毎回「軌跡の腕が動くのは前提を1件閉じたときだけ」と印字して
いるので、**その 15日 は到達日がまるごと止まっていた日数**です。

**素通りした理由は、検査の中身ではなく「誰が撃つか」でした。**

    scripts/fast_tests.py   その回の `git diff` の basename から `-k` を組む
                            → `deadline_check` を触らない回は 1件も走らせない
    全体の pytest           16分。**どの回も撃たない**（`fast_tests.py` 冒頭の実測）
    docs/trigger_main.md    `fast_tests.py` の名前が**無い**
    scripts/stop_check.sh   `fast_tests.py` の名前が**無い**

**そしてこの検査が赤くなるのは「世界のほうが動いたとき」です** ——
予約が公開され、`src/settle.py` の落ち着きと Analytics の遅れの実測が動くと、
`ready` は**こちらが1行も書かなくても**手前へ来ます。**そのとき diff は空です。**
**diff から検査を選ぶ仕掛けは、構造上この赤を永久に選びません。**

だから置き場を、**毎周かならず走ると分かっている唯一の場所**へ移しました ——
`scripts/stop_check.sh`（Stop フック）です。

## この検査が守っているもの

1. `--gate` が両方の向き（遅すぎる／早すぎる）で 2 を返すこと
2. ずれが無いとき 0 を返すこと（＝ 毎周むやみに止めない）
3. `stop_check.sh` が実際にそれを読み、`--fit` を名指しすること

## 覆る条件

- `--fit` を撃った直後にまた赤いなら、効いていないのは門ではなく
  `Verdict.slack`（帯）の幅です。**帯を広げること。門を消さないこと。**
- `scripts/fast_tests.py` の `CORE` に `deadline_check` が入り、**かつ
  `fast_tests.py` 自身が手順のどこかから毎周 撃たれる**ようになったら、
  この門は重複です。そのときは消してよい ——
  **「CORE に入れた」だけでは足りません**（撃たれない道具の効果はゼロ）。
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as J  # noqa: E402


class _V:
    """`Verdict` の、門が読む欄だけを持った代役。"""

    def __init__(self, waits: int, slips: bool, deadline: date, ready: date, claim: str):
        self.waits = waits
        self.slips = slips
        self.deadline = deadline
        self.ready = ready
        self.claim = claim


def test_ずれが無ければ通すこと():
    """**毎周むやみに止めないこと。** 止めてよいのは、直す手が1つに決まるときだけ。"""
    assert J.gate([]) == 0


def test_遅すぎる期限で落ちること(capsys):
    """データは揃うのに期限が先 ＝ 到達日がまるごと止まっている日数。"""
    v = _V(15, False, date(2026, 10, 7), date(2026, 9, 22), "冒頭0.9秒の動き")
    assert J.gate([v]) == 2
    out = capsys.readouterr().out
    assert "15日" in out, "止まっている日数を言っていません"
    assert "--shrink" in out, "直す手を名指ししていません"


def test_早すぎる期限で落ちること(capsys):
    """早すぎる期限は「対照群が空のまま外れ」を確定させる ＝ 腕を測らずに捨てる形。"""
    v = _V(0, True, date(2026, 9, 1), date(2026, 9, 12), "早すぎる主張")
    assert J.gate([v]) == 2
    out = capsys.readouterr().out
    assert "--extend" in out, "直す手を名指ししていません"


def test_falsified_if_を緩めろとは言わないこと(capsys):
    """**逃げ道を塞ぐ。** 期限が守れないときに条件を緩めると、腕は動かないのに
    予測だけが「その日に閉じる」前提のまま残ります（＝到達日が早すぎる）。"""
    J.gate([_V(9, False, date(2026, 10, 7), date(2026, 9, 28), "何か")])
    out = capsys.readouterr().out
    assert "falsified_if" in out and "緩めない" in out


def test_gate_は_書き戻さないこと():
    """門は読むだけ。書くのは `--shrink` / `--extend` / `--fit` の側です。"""
    before = (ROOT / "config" / "hypotheses.yaml").read_bytes()
    J.gate([_V(9, False, date(2026, 10, 7), date(2026, 9, 28), "何か")])
    assert (ROOT / "config" / "hypotheses.yaml").read_bytes() == before


def test_gate_が_cli_から撃てること():
    """`stop_check.sh` は CLI 越しにしか呼べません。**旗が生きていること。**"""
    r = subprocess.run([sys.executable, "scripts/deadline_check.py", "--gate"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode in (0, 2), f"門が 0/2 以外を返しました: {r.returncode}\n{r.stderr[-2000:]}"


def test_stop_check_が_この門を読んでいること():
    """**置き場がここでなくなったら、この検査ごと考え直すこと。**

    赤い検査を1つ足すだけでは足りない、というのがこの回の発見です
    （赤いまま 358件 通過した）。**毎周かならず走る所に置いてあること**を
    ここで固定します。
    """
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert "deadline_check.py --gate" in src, \
        "stop_check.sh が期限のずれを見ていません（門が外れると、赤は diff からしか選ばれません）"
    assert "--fit" in src, "直す手（--fit）を名指ししていません"
    assert "falsified_if" in src, "逃げ道（条件を緩める）を塞いでいません"


def test_診断だけの道が壊れていないこと():
    """`--gate` を足したせいで、素の印字が死んでいないこと。"""
    src = (ROOT / "scripts" / "deadline_check.py").read_text(encoding="utf-8")
    i = src.index("if a.gate:")
    j = src.index("record_estimates(vs, as_of=as_of)")
    assert i < j, "門が印字の道より後ろにあります"
    assert "return gate(" in src[i:j], "門が gate() を呼んでいません"
