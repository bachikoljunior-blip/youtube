"""**人間の専門家を装った台本を、レンダリングの前に落とすこと。**（2026-08-30）

## なぜ要るか

2026-08-30、オーナーが `AUTOMATION_PAUSED.md` を `origin/main` へ直接 push して、
生成・投稿・予約の変更を止めました。挙がっている理由の中心は2行です。

    - AI-generated personas presenting themselves as human experts on sensitive topics
    - AI personas providing financial guidance or interpreting legal rules

実物がありました。`config/channel.yaml` の `persona` が
**「元・事業会社の経理／人事で、制度を実務で回してきた立場」**と名乗り、
`src/script_writer.py:1086` から**毎本の台本の指示文**に入っていました。

**設定を直すだけでは閉じません。** `persona` は指示文の一部でしかなく、
書き手（LLM）はそこに無い経歴を自分で足せます —— 「元・経理」を消しても
narration に「私が担当していたころは」と書かれれば、視聴者から見える形は同じです。
**設定は入口、`verify` は出口**です。この検査は出口のほうを固定します。

## ここで固定するもの（4つ）

1. `config/channel.yaml` の `persona` が、**人間の実務経歴を名乗らないこと**
2. `verify._check_no_human_expert_claim()` が、名乗っている台本を**落とすこと**
3. それが `script_only_problems()` に入っていること
   （＝ **22本のクリップを焼く前**に当たる。`tests/test_script_gate_before_render.py`）
4. **実物で偽陽性を出さないこと** —— 投稿済み735本の題を全部通す。
   `CLAUDE.md`「投稿が途切れるのが最大の損失」より、
   **偽陽性のほうが偽陰性より高くつきます**

## 覆る条件

**実在する人間が実名で出演し、その経歴が事実になったら**、これは「装う」に
当たりません。**そのときはこのファイルごと消すこと**（`config/channel.yaml` の
`persona` に置いた「覆る条件」と対です）。
それまでは、**`persona` に経歴を戻すことで偽陽性を直さないこと** —— それが元の穴です。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src import verify

ROOT = Path(__file__).resolve().parent.parent


# --- 1. 設定の側 ---------------------------------------------------------

def test_persona_が人間の実務経歴を名乗っていない():
    """`config/channel.yaml` の `persona` を、そのまま検査に通す。

    **停止の理由に名指しされていた文字列そのもの**を、ここで固定します。
    """
    cfg = yaml.safe_load((ROOT / "config" / "channel.yaml").read_text(encoding="utf-8"))
    persona = cfg["channel"]["persona"]
    assert "元・事業会社の経理" not in persona
    assert "実務で回してきた" not in persona
    # **同じ検査を、人格そのものにも当てる**（入口と出口で物差しを分けない）
    problems = verify._check_no_human_expert_claim(
        {"segments": [{"narration": persona}]})
    assert problems == [], problems


def test_persona_は計算という根幹を落としていない():
    """**落とすのは経歴であって、企画ではありません。**

    `CLAUDE.md` の根幹は「制度を解説するのではなく、自分で計算した結果を発表する」。
    経歴を消したついでに、そこを薄めていないかを見ます。
    """
    cfg = yaml.safe_load((ROOT / "config" / "channel.yaml").read_text(encoding="utf-8"))
    persona = cfg["channel"]["persona"]
    assert "前提" in persona
    assert "計算" in persona


# --- 2. 検査の側 ---------------------------------------------------------

@pytest.mark.parametrize("narration", [
    "元・経理として言うと、ここは間違えやすい所です。",
    "私は人事の担当でした。だから分かります。",
    "税理士としての経験から言うと、この扱いは変わります。",
    "実務で回してきたので、ここが落とし穴だと分かります。",
    "自分の経験上、これは通りません。",
    "私は10年間、経理を担当してきました。",
    "専門家として断言します。",
])
def test_名乗っている台本は落ちる(narration):
    problems = verify._check_no_human_expert_claim(
        {"segments": [{"narration": narration}]})
    assert problems, f"素通りした: {narration}"


@pytest.mark.parametrize("narration", [
    # 相手が専門家。話し手の名乗りではない
    "税理士に確認してください。",
    # 主語が視聴者
    "会社員として働く人は、ここが変わります。",
    "あなたが経理に出す書類は1枚です。",
    # 説明欄の定型文（config/channel.yaml の footer）
    "この動画は一般的な情報提供を目的としたもので、個別の助言ではありません。"
    "制度は改正されます。実行前に必ず公式情報・専門家にご確認ください。",
    # 普通の計算の話
    "前提を年収500万円、扶養なしと置いて計算します。",
    "人事部に申請すると、翌月から反映されます。",
    "元本が減るわけではありません。",
    "この計算式は、課税所得×税率−控除額です。",
])
def test_名乗っていない台本は通る(narration):
    problems = verify._check_no_human_expert_claim(
        {"segments": [{"narration": narration}]})
    assert problems == [], problems


def test_題と説明欄と画面も見ている():
    """narration だけ見ても足りません。**視聴者に見えるのは全部です。**"""
    for field, script in [
        ("title", {"title": "元・経理が教える年末調整"}),
        ("description_body", {"description_body": "専門家として解説します。"}),
        ("title_alternatives", {"title_alternatives": ["私は人事でした"]}),
    ]:
        assert verify._check_no_human_expert_claim(script), field


# --- 3. 焼く前に当たること ------------------------------------------------

def test_レンダリングの前に当たる():
    """`script_only_problems()` に入っていること。

    ここから漏れると、`check()` が**22本のクリップを焼いたあと**に落とします
    （実測 1本 15分・作り直しを入れて 30分。`tests/test_script_gate_before_render.py`）。
    """
    assert "_check_no_human_expert_claim" in \
        verify.script_only_problems.__code__.co_names
    script = {"segments": [{"narration": "元・経理として言うと、ここが要点です。",
                            "visual": {"kind": "stat", "lead": "100万円"}}]}
    assert any("装って" in p for p in verify.script_only_problems(script, portrait=False))


# --- 4. 実物で偽陽性を出さない --------------------------------------------

def test_投稿済みの題を全部通しても偽陽性が出ない():
    """**735本の実物**（`data/uploaded.jsonl`）で0件であること。

    偽陽性は投稿を止めます。`CLAUDE.md`「投稿が途切れるのが最大の損失」より、
    **こちらのほうが偽陰性より高くつきます。**
    **覆る条件**: ここが赤くなったら、まずパターンを狭めること
    （`persona` に経歴を戻すことでは直さない）。
    """
    path = ROOT / "data" / "uploaded.jsonl"
    if not path.is_file():
        pytest.skip("投稿の控えがありません")
    titles = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        titles[row["video_id"]] = row.get("title") or ""
    assert len(titles) > 100, "控えが薄すぎます（この検査の意味が無い）"
    flagged = {v: t for v, t in titles.items()
               if verify._check_no_human_expert_claim({"title": t})}
    assert flagged == {}, flagged
