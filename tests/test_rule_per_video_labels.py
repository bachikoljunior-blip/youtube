"""**形の札が付かない本を、黙って落とさないこと。**（2026-09-01・最適化の回）

## 何を踏んだか（実測 2026-09-01）

`src/rule_per_video.py`（08/31 作）は `data/video_forms.json` を**生で**読み、
札の無い本を `fm.get(vid) != form` で**黙って捨てて**いました。

`data/video_forms.json` は Analytics の `creatorContentType` で、
**公開して数日たった本しか載りません**。実測:

    08/31 に公開した 10本 → Analytics の札 **0本** ／ 控えの秒数 **8本**
    views.jsonl の 248本 のうち 札の無い本 **53本**（新しい日ほど多い）

つまり**この標本は、いちばん新しい日を丸ごと落としていました。**
`eta.py` の唯一 生きている腕（`per_video`）の分子と天井が、
そこから出ています —— **いま改善した1本は、この標本に入れません。**

`src/forms.py` は、まさにこのために「実測 → 控えの秒数 → 題名の札」の3段で
決める1か所として 2026-08-25 に作られています。**そこを通していませんでした。**

## この検査が守る3つ

1. **札の無い本は、台帳の秒数で拾うこと**（`duration` の段が効いている）
2. **題名の札（`tag`）は既定で採らないこと** —— 推測なので、天井を動かさせない
3. **落ちた本数を印字すること**（`labels["unlabelled"]`）——
   見えていない縁の大きさが出ていないと、次の回がまた「全部入っている」と読む

## 覆る条件

`data/video_forms.json` が公開直後の本も載せるようになったら（Analytics の遅れが
消えたら）、`duration` の段は要らなくなります。そのとき `unlabelled` が 0 を
返し続けるので、**この検査は自然に無害になります**（消してよい合図）。
"""
from __future__ import annotations

import json

from src import rule_per_video


def _views(rows):
    return "\n".join(json.dumps({"id": i, "hours": h, "views": v, "at": a})
                     for i, h, v, a in rows)


def _setup(tmp_path, monkeypatch, labelled_ids, ledger):
    """`views.jsonl` に 3本。`video_forms.json` は `labelled_ids` だけを持つ。"""
    rows = []
    for k, vid in enumerate(("a", "b", "c")):
        rows.append((vid, 0.0, 0, f"2026-08-0{k + 1}T00:00:00Z"))
        rows.append((vid, 96.0, 100 * (k + 1), f"2026-08-0{k + 5}T00:00:00Z"))
    vp = tmp_path / "views.jsonl"
    vp.write_text(_views(rows), encoding="utf-8")

    fp = tmp_path / "video_forms.json"
    fp.write_text(json.dumps({"forms": {i: "ショート" for i in labelled_ids}}),
                  encoding="utf-8")
    monkeypatch.setattr(rule_per_video, "FORMS", fp)
    monkeypatch.setattr(rule_per_video, "_LEDGER_CACHE", ledger)
    return vp


def test_duration_picks_up_what_analytics_has_not_labelled_yet(tmp_path, monkeypatch):
    """**Analytics の札が無くても、控えの秒数が在れば標本に入ること。**"""
    ledger = {"b": {"id": "b", "duration_s": 40.0, "title": "no tag"},
              "c": {"id": "c", "duration_s": 40.0, "title": "no tag"}}
    vp = _setup(tmp_path, monkeypatch, ["a"], ledger)

    only_measured = rule_per_video._settled(vp, trust=("measured",))
    assert [v for _, v, _ in only_measured] == ["a"], "生の読みは1本しか見ていない"

    tiers: dict[str, int] = {}
    both = rule_per_video._settled(vp, tiers=tiers)
    assert sorted(v for _, v, _ in both) == ["a", "b", "c"], (
        "控えの秒数で拾えるはずの本が落ちている")
    assert tiers.get("duration") == 2
    assert tiers.get("unlabelled") == 0


def test_title_tag_is_not_trusted_by_default(tmp_path, monkeypatch):
    """**題名の `#Shorts` だけの本は、既定では採らないこと**（推測なので）。

    採らないだけでなく、**落ちた本数が `unlabelled` に出ること**まで見ます。
    """
    ledger = {"b": {"id": "b", "title": "なにか #Shorts"}}   # 秒数が無い
    vp = _setup(tmp_path, monkeypatch, ["a"], ledger)

    tiers: dict[str, int] = {}
    default = rule_per_video._settled(vp, tiers=tiers)
    assert [v for _, v, _ in default] == ["a"], "題名の札で標本に入ってしまっている"
    assert tiers.get("unlabelled") == 2, "落ちた本数が印字に出ない"

    named = rule_per_video._settled(vp, trust=("measured", "duration", "tag"))
    assert sorted(v for _, v, _ in named) == ["a", "b"], (
        "名指しで tag を許しても拾えていない")


def test_estimate_reports_the_blind_edge(tmp_path, monkeypatch):
    """**`estimate()` は、落ちた本数と採った段を返すこと。**"""
    ledger = {"b": {"id": "b", "duration_s": 40.0, "title": "x"}}
    vp = _setup(tmp_path, monkeypatch, ["a"], ledger)
    e = rule_per_video.estimate(views_path=vp)
    assert "labels" in e and "trust" in e
    assert e["trust"] == list(rule_per_video.LABEL_TIERS)
    assert e["labels"].get("unlabelled") == 1     # "c" は台帳にも無い


def test_tag_is_outside_the_default_tiers():
    """**既定の段に `tag` を入れないこと**（この行が戻ると、天井が推測で動きます）。"""
    assert "tag" not in rule_per_video.LABEL_TIERS
    assert "duration" in rule_per_video.LABEL_TIERS
