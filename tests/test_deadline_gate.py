"""`deadline_check.py --gate` —— **期限のずれを、Stop フックで止める。**

## なぜ、赤い検査の**上に**さらに門を置いたのか（2026-08-30・最適化の回）

`tests/test_deadline_check.py::test_遅すぎる期限が残っていないこと` は、
その docstring で**まさにこの問題を予言していました**:

> **印字は 666 commits 効きませんでした。赤い検査は同じ日に効きました。**

ところが 2026-08-30 に測ると、**その赤い検査自身が ship 358件 を素通り**して
いました（08/24〜08/30。そのあいだ到達予測は 2026-12-21 → 2027-01-10 ＝ **+20日
遠のいた**・**verdict は 6件**）。中身は `opening_motion` —— 判定できるのは 09-22
なのに期限 10-07 で **15日**。

**その 15日 が何の日数かは、下の3件で測り直しました**（最初はここにも
「到達日がまるごと止まっていた日数」と書いていて、**それは偽でした**）。
`eta.py` の印字は `ready` 側で解かれているので、`deadline` を 15日 縮めても
1日も動きません。動くのは `drift.overdue()` ——
**「この回は verdict を出せ」と回に言う唯一の仕掛け**だけが `deadline` を読みます。
だから 15日 は、**データが揃っているのに誰も閉じに行かない日数**です。
**閉じる回が 1.7%（6/358）しかない輪で、閉じる合図を 15日 遅らせていました。**

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
    """データは揃うのに期限が先 ＝ **誰も閉じに行かない日数**（`Verdict.waits` の実測）。"""
    v = _V(15, False, date(2026, 10, 7), date(2026, 9, 22), "冒頭0.9秒の動き")
    assert J.gate([v]) == 2
    out = capsys.readouterr().out
    assert "15日" in out, "遅れている日数を言っていません"
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


# --- **この門が乗っている前提を、字で固定する**（2026-08-30・同じ回に測り直した） ---
#
# この門を足した最初の版は、`Verdict.waits` の docstring をそのまま根拠にして
# 「**この日数は到達日がまるごと止まっている日数そのもの**」と書いていました。
# **同じ回に撃って、それが偽だと分かりました** ——
# `deadline` を 15日 縮めても `eta.py --alloc` は1つも動きません。
#
# 書き置かれた結論は、それを書いた回の姿でできています。
# `waits` の一文は 2026-08-25 22:5x には本当で、**その翌日**（08-26 20:4x に
# `ready` が `arm_speed` へ配線された時点）に本当でなくなりました。
# **結論より先に、その根拠のほうが腐ります。**
#
# だから、この門が実際に乗っている2つの事実を字で留めます。


def test_到達日は_ready_側で解かれていること():
    """**`deadline` を動かしても `eta.py` の印字は動きません。**

    `src/arm_speed.py` は `ready` を `deadline` より優先し、
    `forward()` / `forward_by_arm()` は `ready` だけを読みます。

    **覆る条件**: ここが `deadline` に戻ったら、`waits` は再び
    「到達日が止まっている日数」になります。そのときは
    `Verdict.waits` と `gate()` と `stop_check.sh` の3か所を戻すこと。
    """
    src = (ROOT / "src" / "arm_speed.py").read_text(encoding="utf-8")
    i = src.index("def next_close(")
    j = src.index("def forward(")
    body = src[i:j]
    assert 'src = "ready"' in body or '"ready"' in body, \
        "arm_speed が ready を持っていません（waits の意味が変わります）"
    fwd = src[src.index("def forward_by_arm("):]
    assert "ready.get(claim)" in fwd, "forward_by_arm が ready を読んでいません"


def test_閉じろと言う門だけが_deadline_を読んでいること():
    """**`drift.overdue()` が `deadline` だけを読む** —— これがこの門の存在理由です。

    `overdue()` は `stop_check.sh` (1.7)「期限の来た問いの置き去り」の入力で、
    **「この回は verdict を出せ」と回に言う唯一の仕掛け**。だから期限が
    `ready` より先にあるあいだ、**データは揃っているのに誰も閉じに行きません。**

    **覆る条件**: `overdue()` が `ready` を読むようになったら、`deadline` は
    どの門の入力でもなくなります。**そのときは `--gate` ごと畳んでよい** ——
    残す理由が無くなるので。
    """
    import inspect
    import importlib.util
    spec = importlib.util.spec_from_file_location("dg_drift", ROOT / "scripts" / "drift.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dg_drift"] = mod
    spec.loader.exec_module(mod)
    body = inspect.getsource(mod.overdue)
    assert 'h.get("deadline")' in body, "overdue が deadline を読んでいません"
    assert "ready" not in body, (
        "overdue が ready を読むようになりました —— `deadline` はもうどの門の"
        "入力でもありません。`deadline_check.py --gate` と stop_check.sh (1.9) を畳むこと")


def test_止まっている日数だとは言わないこと():
    """**測り直した結果を、字で戻させない。**

    「到達日がまるごと止まっている」は、2026-08-26 以降は偽です。
    この文言が戻ったら、次に来た側はまた `eta.py` で確かめて
    「効かなかった」と結論し、門ごと捨てます。
    """
    for rel in ("scripts/deadline_check.py", "scripts/stop_check.sh"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "到達日がまるごと止まっている日数**そのもの" not in src, \
            f"{rel} に測り直す前の文言が戻っています（`Verdict.waits` の実測を読むこと）"
