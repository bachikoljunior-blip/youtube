"""**ショートか長尺かを、題名の札だけで決めさせない**（2026-08-25）。

この検査が守っているのは1点です —— **測った形が、書いてある札に勝つ**こと。
戻すと、`scripts/reschedule.py --spread` が長尺をショートと数えて
その日の枠を食いつぶし、本物のショートを後ろの日へ押し出します。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import forms  # noqa: E402


def test_measured_beats_tag_long():
    """**Analytics が「長尺」と言えば、`#Shorts` が付いていても長尺。**

    実物: `WuTf0Z-tRJc`（5分51秒・公開済み・1再生）。
    """
    short, how = forms.classify(
        {"id": "V1", "title": "傷病手当金 … #Shorts"}, forms={"V1": "長尺"})
    assert short is False
    assert how == "measured"


def test_measured_beats_missing_tag():
    """**逆向きも同じ。** 札が無くても、実測がショートならショート。

    実物: `pMHDwK5tB2E` / `YmJ7psxW3co` / `FSAN9tjIX10`。
    札で数えると**1日の上限から漏れます**。
    """
    short, how = forms.classify(
        {"id": "V2", "title": "ふるさと納税 扶養1人で上限は約1万6544円下がる"},
        forms={"V2": "ショート"})
    assert short is True
    assert how == "measured"


def test_duration_beats_tag_when_unmeasured():
    """実測が無ければ、**控えの秒数**が札に勝つ（予約中の本はここに落ちます）。"""
    assert forms.classify({"id": "V3", "title": "長い話 #Shorts",
                           "duration_s": 309.0}, forms={})[0] is False
    assert forms.classify({"id": "V4", "title": "短い話",
                           "duration_s": 30.0}, forms={})[0] is True


def test_tag_is_last_resort_and_is_countable():
    """**何も測っていない本だけ札に落ち、そのことが数えられる。**"""
    rows = [{"id": "V5", "title": "むかしの本 #Shorts"},
            {"id": "V6", "title": "測った本", "duration_s": 12.0}]
    assert forms.classify(rows[0], forms={}) == (True, "tag")
    assert [r["id"] for r in forms.inferred(rows)] == ["V5"]


def test_mislabelled_names_the_rows():
    """食い違う本を名指しできること（**空でない限り、札の読み手は間違えます**）。"""
    bad = forms.mislabelled([
        {"id": "V7", "title": "長尺なのに #Shorts", "duration_s": 351.0},
        {"id": "V8", "title": "ショートなのに札なし", "duration_s": 29.0},
        {"id": "V9", "title": "正しい #Shorts", "duration_s": 30.0},
    ])
    assert sorted(b["id"] for b in bad) == ["V7", "V8"]


def test_strip_tag():
    assert forms.strip_tag("金利1%と3%で住宅ローン控除はいくら増えるか #Shorts") == \
        "金利1%と3%で住宅ローン控除はいくら増えるか"
    assert forms.strip_tag("札のない題") == "札のない題"


def test_reschedule_uses_forms(monkeypatch):
    """**`reschedule._is_short` が `src.forms` を通ること。**

    ここが `"#Shorts" in title` に戻ったら落ちます。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_resched", Path(__file__).resolve().parent.parent / "scripts" / "reschedule.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(forms, "measured_forms", lambda: {"V1": "長尺"})
    assert mod._is_short({"id": "V1", "title": "長尺なのに #Shorts"}) is False


def test_verify_blocks_long_with_shorts_tag():
    """**3分を超える本に `#Shorts` が付いていたら、投稿前に止める。**"""
    from src import verify
    assert verify._check_form_tag({"title": "長い話 #Shorts"}, 309.0)
    assert verify._check_form_tag({"title": "長い話"}, 309.0) == []
    # 逆向きは**止めません**（動画そのものは正しい。途切れるほうが高い）
    assert verify._check_form_tag({"title": "短い話"}, 30.0) == []


def test_ledger_keeps_duration_across_retime(tmp_path, monkeypatch):
    """**`retime()` が足した行に秒数が無くても、失わないこと。**"""
    from src import config, dupes
    led = tmp_path / "data" / "uploaded.jsonl"
    led.parent.mkdir(parents=True)
    led.write_text(
        json.dumps({"video_id": "V", "topic": "t", "title": "題",
                    "at": "2026-09-01T00:00:00Z", "duration_s": 312.0},
                   ensure_ascii=False) + "\n"
        + json.dumps({"video_id": "V", "topic": "t", "title": "題",
                      "at": "2026-09-02T00:00:00Z",
                      "retimed_at": "2026-08-25T00:00:00Z"},
                     ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    rows = dupes.ledger_rows()
    assert len(rows) == 1
    assert rows[0]["duration_s"] == 312.0
