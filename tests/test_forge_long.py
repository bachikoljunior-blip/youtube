"""**この道具は長らくショートの企画しか書けませんでした**（2026-08-25 に足した）。

`scripts/eta.py` の逆算はこう言っています ——
**門2b（ショート90日1,000万回）は、API の上限 1日92本を全部出しても
111,111回/日 に対し 58,696回/日 ＝ 0.53倍。届きません。**
残る道は **門2a（長尺4,000時間）だけ**で、しかも受け取り帳 `88e9fb44`
（YouTube 公式ヘルプの原文）のとおり、**ショートの視聴時間はそこに1分も入りません。**

ところが在庫を作る道具は、`PROMPT_HEAD` が「YouTube ショート（縦・30秒前後）」で
始まり、id を `s-` に強制していました。**唯一の門を開ける形を、
在庫の側が1件も作れない**作りです（実測: 待ち行列は長尺11本 / ショート310本 ＝ 3.4%）。

**`s-` はショートの印です**（`src/pipeline.py:39` / `scripts/eta.py:316`）。
長尺に付けると pipeline が「`topics.yaml` に置かず、その場で作る」道へ入り、
**`calc_sections` を渡さないまま台本を書かせます。**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)


class _Item:
    def __init__(self, tid, title, angle):
        self.id, self.title_seed, self.angle = tid, title, angle


class _Set:
    def __init__(self, topics):
        self.topics = topics


LONG_ANGLE = (
    "長尺。表を最後まで読み切る。主役の数字は、年間所定休日が20日ちがうと"
    "残業代の年額が43,269円ちがうこと。前提として月給300,000円・一律手当なし・"
    "1日の所定8.0時間・残業は月20時間・どちらの会社も計算は正しい、の4点を画面に出す。"
    "棒にするのは105日・115日・125日の3行（単価2,163円・2,250円・2,344円）。"
    "途中で残業時間を月20時間から月45時間へ動かし、差がどう開くかを1段入れる。"
    "単価の分母が (365 − 年間所定休日) × 8.0時間 ÷ 12 であることを式のまま出す。"
    "最後の問いかけは「あなたの会社の年間所定休日は何日ですか」。"
)


def _sections():
    return {"zangyo": forge.sections("zangyo")}


def _picked():
    head = next(h for h in forge.sections("zangyo") if "年間所定休日" in h)
    return [("zangyo", head)]


def test_長尺の指示文に切り替わる():
    prompt = forge.build_prompt(_picked(), _sections(), [], long_form=True)
    assert "`s-` で始めないこと" in prompt
    assert "縦・30秒前後" not in prompt
    # 既定はショートのまま（他の呼び出し元を巻き込まない）
    short = forge.build_prompt(_picked(), _sections(), [])
    assert "縦・30秒前後" in short


def test_尺は決め打ちではなく設定から来る():
    """**2026-08-25 に踏んだ。** 最初の版は「8分30秒以上」と書いていましたが、
    実物は 2026-08-09 から **4分**です（`config/channel.yaml` に
    「通っていない門（ミッドロール広告の8分）のための制約だった」と理由ごとある）。
    **決め打ちは、覆った側の判断を静かに巻き戻します。**
    """
    from src import config

    vid = config.load_channel()["video"]
    prompt = forge.build_prompt(_picked(), _sections(), [], long_form=True)
    assert f"{float(vid['min_minutes']):g}分を下回ると" in prompt
    assert f"{float(vid['target_minutes']):g}分前後" in prompt
    # **古い決め打ちが残っていないこと**（戻したら赤になる）
    assert "8分30秒" not in prompt


def test_長尺のidにsハイフンを付けたら落とす():
    """**`s-` はショートの印。** 付いたまま通ると pipeline が別の道へ入る。"""
    item = _Item("s-zangyo-kyujitsu-43269", "年間休日20日で残業代が43,269円ちがう",
                 LONG_ANGLE)
    rows, dropped = forge.validate(_Set([item]), _picked(), _sections(),
                                   set(), long_form=True)
    assert rows == []
    assert dropped and "`s-` で始めないこと" in dropped[0]


def test_長尺のidはsハイフン無しで通る():
    item = _Item("zangyo-kyujitsu-43269", "年間休日20日で残業代が43,269円ちがう",
                 LONG_ANGLE)
    rows, dropped = forge.validate(_Set([item]), _picked(), _sections(),
                                   set(), long_form=True)
    assert dropped == [], dropped
    assert rows[0]["id"] == "zangyo-kyujitsu-43269"
    assert rows[0]["calc"] == "zangyo"
    assert "年間所定休日" in rows[0]["calc_sections"][0]


def test_ショートは今までどおりsハイフンが要る():
    """**既定の道は1文字も変えていない**ことを、裏から押さえる。"""
    ok = _Item("s-zangyo-kyujitsu-43269", "年間休日20日で残業代が43,269円ちがう",
               LONG_ANGLE)
    rows, dropped = forge.validate(_Set([ok]), _picked(), _sections(), set())
    assert dropped == [], dropped
    assert rows[0]["id"] == "s-zangyo-kyujitsu-43269"

    ng = _Item("zangyo-kyujitsu-43269", "年間休日20日で残業代が43,269円ちがう",
               LONG_ANGLE)
    rows, dropped = forge.validate(_Set([ng]), _picked(), _sections(), set())
    assert rows == []
    assert "`s-` で始めること" in dropped[0]


def test_長尺は短い指示を落とす():
    """8分30秒を埋める指示が無いまま作ると、**作ってから verify に落とされます。**"""
    short_angle = "長尺。表を最後まで読み切る。主役の数字は43,269円。前提は月給300,000円。"
    assert len(short_angle) < forge.LONG_ANGLE_MIN
    item = _Item("zangyo-kyujitsu-43269", "年間休日20日で残業代が43,269円ちがう",
                 short_angle)
    rows, dropped = forge.validate(_Set([item]), _picked(), _sections(),
                                   set(), long_form=True)
    assert rows == []
    assert "angle が短すぎます" in dropped[0]
    # **同じ指示は、ショートなら通ります**（下限が違うだけ）
    ok = _Item("s-zangyo-kyujitsu-43269", "年間休日20日で残業代が43,269円ちがう",
               short_angle)
    rows, dropped = forge.validate(_Set([ok]), _picked(), _sections(), set())
    assert dropped == [] and rows
