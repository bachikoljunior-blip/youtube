"""**「表が出た」を「貯まった」と読ませないこと**（`scripts/retention.py`・2026-09-02）。

実測（2026-09-02 11:4x）—— `python scripts/retention.py` はこう振る舞いました:

    [analytics] 維持率を取得できませんでした: 500     ← 1行だけ、130行の表の**上**
    （…維持率カーブ 130行…）                          ← **前の回と1桁も違わない**
    exit 0                                            ← **正常終了**

貯めは **132本 のまま**、`python -m src.clarity` の n も **113本 のまま**でした。
それでも呼んだ側からは「撃った → 表が出た」としか見えません。
この repo は同じ形を一度 踏んでいます（`length_of` ——
**見出しだけ出して1本も描かずに正常終了し、7日 気づかれなかった**）。

**そして「落ちた」には2種類あります。**

    エラー（HttpError）  上流の一時失敗 → **撃ち直せば通ることがある**
    空（`rows` が 0行）  その本のカーブがまだ無い → **撃ち直しても増えない**

`fetch_retention` は**どちらも `[]`** で返します。混ぜて「撃ち直せば通る」と
書くと、次の回が毎周 空の本を引き直します（実測 61本／周）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("_ret", ROOT / "scripts" / "retention.py")
ret = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ret)


def _set(試した=0, 足した=0, 空=0, エラー=0):
    ret.LAST_FETCH.update({"試した": 試した, "足した": 足した, "空": 空, "エラー": エラー})


def test_0本_足せなかった回はそう言う():
    _set(試した=63, 足した=0, 空=61, エラー=2)
    text = "\n".join(ret.fetch_lines(132, 132))
    assert "1本も貯まりませんでした" in text
    assert "新しい観測ではありません" in text, \
        "n が動かなかったことを言っていません（clarity の連が空回りします）"


def test_空とエラーを分けて言う():
    _set(試した=63, 足した=0, 空=61, エラー=2)
    text = "\n".join(ret.fetch_lines(132, 132))
    assert "空 61本" in text and "エラー 2本" in text
    assert "撃ち直しても増えません" in text, \
        "空の本を「撃ち直せば通る」と言うと、次の回が毎周 引き直します"

    _set(試した=5, 足した=0, 空=0, エラー=5)
    text = "\n".join(ret.fetch_lines(132, 132))
    assert "撃ち直せば通ることがあります" in text
    assert "撃ち直しても増えません" not in text


def test_足せた回は_clarity_を撃ち直せと言う():
    _set(試した=10, 足した=7, 空=3, エラー=0)
    text = "\n".join(ret.fetch_lines(132, 139))
    assert "132本 → **139本**" in text
    assert "src.clarity" in text


def test_引きに行かなかった回を_失敗と言わない():
    _set(試した=0)
    text = "\n".join(ret.fetch_lines(132, 132))
    assert "1本も貯まりませんでした" not in text


def test_main_が必ず印字する():
    """**表のあとに置くこと** —— 前だと 130行 の上へ流れて読まれません。"""
    src = (ROOT / "scripts" / "retention.py").read_text(encoding="utf-8")
    body = src.split("def main(")[1]
    assert "fetch_lines(" in body, "main が貯めの動きを印字していません"
    assert body.index("report(") < body.index("fetch_lines("), \
        "fetch_lines は report のあとに置くこと（前だと表に埋もれます）"
