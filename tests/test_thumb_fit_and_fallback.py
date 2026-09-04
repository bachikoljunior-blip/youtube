"""サムネの**幅**と、絵の字の**出どころ**の検査。**外へは1回も出ません。**

## なぜ在るか（2026-09-05 07:xx・きょうの枠の本 `qyVdpAoT_40` で踏んだ）

**1. `--rebuild` は、控えの 98% に対して何もしませんでした。**
`scripts/refresh_thumbnail.rebuild_stash()` は `<ID>.script.json` **だけ**を読み、
その控えを残すようになったのは 2026-09-02（`critique_queue.stash()` の註）。
この回に数えた実物: 控え **712本** ／ `<ID>.script.json` **14本（2.0%）** ／
`<ID>.plan.json` **672本** ／ 絵は在るのに焼き直せない本 **566本**。
`run_marker.py --write` が毎周 印字している
「サムネは `refresh_thumbnail.py --rebuild <ID>`」は、**ほとんどの本で1手目から落ちます。**

実際の形: 05:58 にきょうだいの回が `qyVdpAoT_40` の題を
「【小規模企業共済】240か月と241か月で税額はいくら違う？」へ入れ替え、
**絵は 2026-08-19 の控えのまま**。`--rebuild` は「控えが足りません」で止まりました。

**2. `thumbnail.create()` は、字の幅を1度も測っていませんでした。**
大きさは文字数の2段（`150 if len(x) <= 7 else 120`）だけ。120px の全角は約 120px 幅で、
左端 72px から書くと入るのは **10文字**。**11文字目から先は画面の外へ出て消えます。**
実物（この回に焼いて目で見た）: `小規模企業共済 241か月目`（13文字）→ **`小規模企業共済 241か`**。
**切れていることは、例外も警告も出ません。**

いまの控えの台本 16本 は 0本 が該当（生成側の2行はもともと短い）ですが、
**plan から組み立てると 672本 中 529本 の line2 がはみ出します** ——
＝ 上の 1 を直した瞬間に、2 が表に出る形でした。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_thumbnail as rt  # noqa: E402
from src import thumbnail as th  # noqa: E402


def _draw():
    return ImageDraw.Draw(Image.new("RGB", (th.W, th.H)))


def _limit() -> float:
    return th.text_box()


# ------------------------------------------------------------------ 幅

def test_short_text_keeps_its_size():
    """**入る字は1ピクセルも変わらない**こと（控えの 16本 が該当）。"""
    d = _draw()
    assert th._fit_font(d, "9万4500円", 150, th.text_box(), floor=th.TEXT_FLOOR).size == 150


def test_long_text_is_shrunk_until_it_fits():
    """**はみ出す字は、枠に入るまで小さくする**こと。"""
    d = _draw()
    long = "小規模企業共済 241か月目"
    assert d.textlength(long, font=th._font(120)) > _limit(), "前提が崩れています"
    f = th._fit_font(d, long, 120, th.text_box(), floor=th.TEXT_FLOOR)
    assert f.size < 120, "小さくしていません"
    assert d.textlength(long, font=f) <= _limit(), "小さくしても、まだはみ出しています"


def test_it_never_goes_below_the_floor():
    """**床より小さくしない**こと —— 切れていないだけの、読めない字を作らない。"""
    d = _draw()
    f = th._fit_font(d, "あ" * 200, 150, th.text_box(), floor=th.TEXT_FLOOR)
    assert f.size == th.TEXT_FLOOR


def test_empty_text_is_safe():
    d = _draw()
    assert th._fit_font(d, "", 150, th.text_box(), floor=th.TEXT_FLOOR).size == 150


def test_create_draws_the_whole_line(tmp_path):
    """`create()` を通しても、長い2行目が枠に収まること（**焼いて測る**）。"""
    src = tmp_path / "src.jpg"
    Image.new("RGB", (th.W, th.H), (20, 24, 30)).save(src, "JPEG")
    out = th.create(src, "9万4500円", "小規模企業共済 241か月目",
                    tmp_path / "out.jpg", tmp_path, kicker="掛金累計1680万円の場合")
    assert out.exists() and out.stat().st_size > 0
    d = _draw()
    f2 = th._fit_font(d, "小規模企業共済 241か月目", 120, th.text_box(), floor=th.TEXT_FLOOR)
    assert d.textlength("小規模企業共済 241か月目", font=f2) <= _limit()


# ------------------------------------------------------- 絵の字の出どころ

def _stash(tmp_path: Path, vid: str, plan) -> Path:
    s = tmp_path / "critique_queue"
    s.mkdir(parents=True, exist_ok=True)
    (s / f"{vid}.plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return s


def test_it_falls_back_to_the_plan(tmp_path):
    """`<ID>.script.json` が無い本は、**コマの実物**から組み立てること。"""
    plan = [
        {"kind": "stat", "headline": "見出し1", "stat": "", "note": ""},
        {"kind": "stat", "headline": "小規模企業共済 241か月目　2/2",
         "stat": "9万4500円", "note": "掛金累計1680万円の場合"},
    ]
    got, where = rt._thumb_text("VID", "", _stash(tmp_path, "VID", plan))
    assert got is not None, where
    assert got["thumbnail_line1"] == "9万4500円"
    assert got["thumbnail_line2"] == "小規模企業共済 241か月目", "枝番（2/2）を落としていません"
    assert got["thumbnail_kicker"] == "掛金累計1680万円の場合"
    assert "plan.json" in where and "元の字とは違います" in where, (
        "組み立てた字だと言っていません —— 載せる前に目で見る根拠が消えます"
    )


def test_a_plan_without_a_number_returns_nothing(tmp_path):
    """**数の出ないコマしか無い本は、焼かない**こと（空の絵を作らない）。"""
    plan = [{"kind": "table", "headline": "見出し", "stat": "", "note": ""}]
    got, why = rt._thumb_text("VID", "", _stash(tmp_path, "VID", plan))
    assert got is None and "数の入ったコマ" in why


def test_the_stashed_script_still_wins(tmp_path):
    """`<ID>.script.json` が在る本は、今までどおりそちらを読むこと。"""
    s = _stash(tmp_path, "VID", [{"kind": "stat", "headline": "H", "stat": "S", "note": "N"}])
    (s / "VID.script.json").write_text(json.dumps(
        {"thumbnail_line1": "本物1", "thumbnail_line2": "本物2",
         "thumbnail_kicker": "本物k"}, ensure_ascii=False), encoding="utf-8")
    got, where = rt._thumb_text("VID", "", s)
    assert got["thumbnail_line1"] == "本物1" and "台本の控え" in where


def test_the_slot_book_is_rebuildable_now():
    """**きょうの枠の本が、実際に焼き直せる**こと（この検査を足した理由の本）。

    `qyVdpAoT_40` は 2026-08-19 の控えなので `<ID>.script.json` を持ちません。
    **控えが repo から消えたら、この検査は黙ります**（無い物を落とさない）。
    """
    stash = ROOT / "data" / "critique_queue"
    if not (stash / "qyVdpAoT_40.plan.json").exists():
        return
    got, where = rt._thumb_text("qyVdpAoT_40", "s-shokibo-241kagetsu-9man4500", stash)
    assert got is not None, f"きょうの枠の本の絵が、まだ焼き直せません: {where}"
    assert got["thumbnail_line1"], where
