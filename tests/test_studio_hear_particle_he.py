"""助詞の「へ」だけ、予定の側が音（え）を出す —— 片側の問い（`studio/hear.py` の `_particle_he` の註）。

2026-09-11 21:2x（optimizer・Opus）。`hourly` の 16:4x の申し送り「助詞だけを別の問いで撃つ」の答え。
**「は」は入れない**（実測: whisper は助詞の「は」を 16/17 で字のまま書く ＝ 音がどちらでも同じ字）。
"""
import json
from pathlib import Path

from studio import hear

ROOT = Path(__file__).resolve().parents[1]


def test_助詞のへは予定の側が音で出る():
    assert hear.expected_kana("年金をもらう人へ", {}).endswith("ひとえ")


def test_助詞のはは予定の側が字のまま():
    # 実測で whisper が字のまま書くので、ここを「わ」にすると 1本 16件 の偽の差が出る
    assert "は" in hear.expected_kana("退職金は1500万円です", {})
    assert "わ" not in hear.expected_kana("退職金は1500万円です", {})


def test_語中のへは両側とも字のまま():
    assert hear.expected_kana("部屋に入る", {}).startswith("へや")
    assert hear.expected_kana("年金が減ります", {}).endswith("へります")


def test_聞いた側は助詞のへを直さない():
    """聞いた側まで直すと、片側の問いが閉じる（`to_kana` の註）。"""
    assert hear.heard_kana("もらうひとへ", {}).endswith("ひとへ")
    assert hear.heard_kana("もらうひとえ", {}).endswith("ひとえ")


def test_陽性対照_字のまま読んだ形で差が出る():
    """TTS が助詞の「へ」を「ヘ」と読んだ形は、いま 1字差で鳴る（前は `_LOOSE` が畳んで見えなかった）。"""
    exp = hear.loose(hear.expected_kana("年金をもらう人へ", {}))
    assert exp == hear.loose(hear.heard_kana("ねんきんをもらうひとえ", {}))   # 正しい読みは通る
    assert exp != hear.loose(hear.heard_kana("ねんきんをもらうひとへ", {}))   # 字のまま読んだら鳴る


def test_LOOSE_にへえの畳みが残っていないこと():
    assert ("へ", "え") not in hear._LOOSE


def test_実物の本の照合は1コマも変わらない():
    """77コマ（7本）の「予定 対 音どおりの聞いた側」が、全部 一致のまま（この直しは中立）。"""
    n = 0
    for p in sorted((ROOT / "data" / "studio" / "scripts").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        yomi = d.get("yomi") or {}
        for seg in d["segments"]:
            say = seg.get("say") or ""
            heard_ok = hear.expected_kana(say, yomi)   # 音どおりに書かれた聞いた側
            assert hear.loose(hear.expected_kana(say, yomi)) == hear.loose(hear.heard_kana(heard_ok, yomi)), (p.name, say)
            n += 1
    assert n >= 70
