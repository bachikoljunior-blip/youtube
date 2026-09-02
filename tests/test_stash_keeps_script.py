"""**「この本のここだけ直す」という手が、この repo に1つも無かった。**

## 実物（2026-09-02）

09/03 に出す本（`MqQKSnbM0OI`）の読みを2件 直しました
（段のローマ数字 アイアイアイ → さん／表の行 クダリ → ぎょう）。
**その直しを本へ入れようとしたら、入れる道がありません。**

控えに在ったのは:

    <ID>.jpg         contact sheet（焼き上がった絵）
    <ID>.thumb.jpg   サムネイル（焼き上がった絵）
    <ID>.plan.json   `slides_plan`（**絵**を焼き直す入力）
    <ID>.json        読み上げ文 ＋ 向き ＋ 変化率

**`script.json` だけがありません。** `title` / `description_body` / `tags` /
`first_comment` / `chapters` / `title_alternatives` は、どこにも残っていません。

`python -m src.pipeline --script <台本> --topic <ID>` が
「同じ本を1か所だけ変えて焼き直す」唯一の道で、台本が無ければ
`--topic` だけの生成 ＝ `claude -p` が**別の本を書き下ろします**
（題も説明も一次コメントも入れ替わる。6〜11分）。

**画面が「焼直可」と言っていたのは絵のことで、本のことではありませんでした。**

## なぜこれが `improve` の値段そのものか

実測（`data/runs.jsonl` の ship 305件）: `improve` は **9件（3%）**。
当てどころが見つかっても、**当てる道の値段が「本を1冊 書き直す」**でした。

## ここで固定するもの

1. `stash()` が `script.json` を `<ID>.script.json` として残す
2. **`.script.json` を待ち行列の glob が拾わない**（`.plan.json` と同じ穴の2つ目 ——
   あちらは配列なので `isinstance` で落ちましたが、**台本は dict** なので
   名前で外さないと `"<ID>.script"` という架空の待ちが生えます）
3. 残せなかった回は**黙らない**

## 覆る条件

`--script` が欠けた欄を自分で埋めるようになったら、`narration` だけで足ります。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "critique_queue_script_mod", ROOT / "scripts" / "critique_queue.py")
cq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cq)


def _script() -> dict:
    return {
        "title": "題", "title_alternatives": ["あ", "い"],
        "description_body": "説明", "tags": ["a"],
        "thumbnail_line1": "1", "thumbnail_line2": "2",
        "first_comment": "こめんと",
        "segments": [{"narration": "一行目です。", "visual": {}},
                     {"narration": "二行目です。", "visual": {}}],
        "chapters": [{"segment_index": 0, "label": "はじめ"}],
    }


def _work(tmp_path: Path, with_script: bool = True) -> Path:
    w = tmp_path / "build" / "t-1"
    w.mkdir(parents=True)
    (w / "inspect.jpg").write_bytes(b"jpg")
    (w / "slides_plan.json").write_text("[]", encoding="utf-8")
    if with_script:
        (w / "script.json").write_text(json.dumps(_script(), ensure_ascii=False),
                                       encoding="utf-8")
    return w


def _stash_into(tmp_path, monkeypatch, with_script=True):
    stash = tmp_path / "stash"
    monkeypatch.setattr(cq, "STASH", stash)
    monkeypatch.setenv("YT_NO_STASH_PUSH", "1")
    w = _work(tmp_path, with_script)
    cq.stash(video_id="vid1", topic="t-1", work=w, script=_script(),
             thumbnail_set=False)
    return stash


def test_台本を残す(tmp_path, monkeypatch):
    stash = _stash_into(tmp_path, monkeypatch)
    kept = stash / "vid1.script.json"
    assert kept.exists(), "**`script.json` を残していません**（焼き直す道が閉じます）"
    got = json.loads(kept.read_text(encoding="utf-8"))
    for k in ("title", "description_body", "tags", "first_comment", "chapters"):
        assert k in got, f"{k} が落ちています —— これが無いと同じ本になりません"
    meta = json.loads((stash / "vid1.json").read_text(encoding="utf-8"))
    assert meta.get("script") is True


def test_台本が無ければ黙らない(tmp_path, monkeypatch, capsys):
    _stash_into(tmp_path, monkeypatch, with_script=False)
    out = capsys.readouterr().out
    assert "がありません" in out and "焼き直す" in out, out


def test_script_json_は待ち行列に架空の待ちを生やさない(tmp_path, monkeypatch):
    """**`.plan.json` と同じ穴の2つ目。** 台本は dict なので型では落ちません。"""
    stash = _stash_into(tmp_path, monkeypatch)
    (stash / "vid1.jpg").write_bytes(b"jpg")
    got = [d.get("video_id") for d in cq.pending(include_stranded=True, order=False)]
    assert got == ["vid1"], got
    assert "vid1.script" not in got


def test_サムネの押し直しも架空の待ちを見ない(tmp_path, monkeypatch):
    """**`*.json` を舐めるもう1つの輪**（`thumbnail_set is False` を集める側）。"""
    stash = _stash_into(tmp_path, monkeypatch)
    fn = next((getattr(cq, n) for n in dir(cq)
               if n.startswith("missing_thumb") or n == "needs_thumbnail_push"), None)
    if fn is None:
        import re
        src = (ROOT / "scripts" / "critique_queue.py").read_text(encoding="utf-8")
        assert src.count('.endswith((".plan.json", ".script.json"))') == 2, (
            "**`*.json` を舐める輪は2つあります。** 両方から外すこと")
        return
    ids = [r.get("video_id") for r in fn()]
    assert "vid1.script" not in ids
    assert stash.exists()
