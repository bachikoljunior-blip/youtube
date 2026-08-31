"""**動画を作らなくても分かる不備で、22本のクリップを焼かないこと。**（2026-08-29）

## 実害（同じ本で2回）

`kouki-jougen-89000-sagaru`・2026-08-29 18:5x。**両方の回とも**
クリップ 22/22 を焼き、音声を合成し、字幕を焼き込んだあとで:

    src.verify.VerificationError: 投稿前の検査に落ちました:
      **前提として『率』を出しているのに、その値が画面のどこにもありません。**

引数は `script` **だけ**の検査（`verify._check_assumption_value_shown`）で、
**動画も画像も見ていません。16分 前に同じ答えが出せました。**
`batch_build` は1回 作り直すので、**1本の失敗に 30分**かかっていました。

`src/script_writer.generate()` は書き直しの輪を3回まわしたあと、こう印字して
台本をそのまま返します —— **その約束が守られていませんでした**:

    [script] 警告: N件がまだ残っています。パイプラインが合成前に止めます

## ここで固定するもの

1. `verify.script_only_problems` が在り、**`check()` がそれを呼ぶこと**
   （2か所に並べると、片方だけ増えたときに静かにずれます）
2. **`work` や `duration` を要る検査を、そこに入れないこと**
   （作らないと分からないので、早く当てようがない）
3. `src/pipeline.py` が、**レンダリングの前に**それを撃つこと
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from src import verify

ROOT = Path(__file__).resolve().parent.parent


def test_check_は_script_だけの検査をこの関数から呼ぶ():
    """**`check()` の中に、素の `_check_*(script)` を並べ直さないこと。**"""
    src = inspect.getsource(verify.check)
    assert "script_only_problems(script, portrait)" in src, (
        "`check()` が `script_only_problems` を呼んでいません")
    for name in ("_check_visual_wrap", "_check_count_matches",
                 "_check_adjacent_repeat", "_check_formula_shown",
                 "_check_assumption_value_shown", "_check_yomi",
                 "_check_short_opening"):
        assert f"problems += {name}(" not in src, (
            f"`{name}` が `check()` に直接 並んでいます。"
            "`script_only_problems` の側へ移すこと（2か所に並べるとずれます）")


def test_scriptだけで判定できるものしか入れないこと():
    """**`work` や `duration` を取る検査を入れたら、早く当てようがありません。**"""
    src = inspect.getsource(verify.script_only_problems)
    called = set(re.findall(r"(_check_[a-z_]+)\(", src))
    assert called, "検査を1つも呼んでいません"
    for name in sorted(called):
        fn = getattr(verify, name)
        params = list(inspect.signature(fn).parameters)
        assert "work" not in params, f"{name} は `work` を要ります（作る前には当てられません）"
        assert "duration" not in params, f"{name} は `duration` を要ります（同上）"


def test_pipelineがレンダリングの前に撃つこと():
    """**「合成前に止めます」を、本当に止まる形にしておくこと。**"""
    src = (ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert "verify.script_only_problems(" in src, (
        "`src/pipeline.py` が `script_only_problems` を撃っていません")
    gate = src.index("verify.script_only_problems(")
    synth = src.index("synthesize_segments(")
    assert gate < synth, (
        "門が音声合成より後ろにあります。**焼いてから落とすなら、早く当てた意味がありません**")


def test_値の無い前提を早い門が見逃さないこと():
    """**早い門が、遅い門より緩くならないこと。**（緩いと、結局あとで落ちます）"""
    script = {"segments": [
        {"narration": "ここでの手取り率は仮定です。",
         "visual": {"kind": "text", "lines": ["手取り率で計算する"]}},
    ]}
    early = verify.script_only_problems(script, True)
    assert any("手取り率" in p for p in early), (
        "値の無い前提を、早い門が見逃しています: " + repr(early))
