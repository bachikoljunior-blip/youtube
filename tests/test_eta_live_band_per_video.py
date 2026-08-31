"""**天井の分母から、上限を超えて死んだ本を外す**（2026-08-29 に足した）。

天井は `1本あたり再生 × 再生が付く上限（day_cap・10本/日） × 30日` です。
**右の「上限」が「超えて出したぶんは 0再生」を既に言っている**のに、
左の「1本あたり再生」は**その死んだ本を分母に入れたままの平均**でした。
**同じ死を、式の左と右で2回 引きます。**

実測（`data/views.jsonl`・齢48時間 以上の 168本。2026-08-29）:

    1〜9再生 の 42本 が、分母の **29%** を占めて、再生の **0.18%** しか持っていない
    帯の中 n=84 平均 **678回** ／ 帯の外 n=84 平均 168回（**4.0倍**）
    帯の予測と実測の生死は **150/168 ＝ 89%** で一致

**この形に戻ったら、ここが赤くなります。**
"""
import datetime as dt
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
sys.modules["eta_mod"] = eta
_spec.loader.exec_module(eta)


def _rows(pairs):
    """`dimensions=video` の行の形。3・4列目はショート扱いになる値。"""
    return [[vid, views, 30.0, 100.0] for vid, views in pairs]


def _published(ids, day="2026-08-21"):
    """`ab_split.published()` の行の形（`at` は JST の datetime）。"""
    base = dt.datetime.fromisoformat(day + "T09:00:00")
    return [{"video_id": v, "at": base + dt.timedelta(minutes=30 * i)}
            for i, v in enumerate(ids)]


def test_帯の外に落ちた本は分母から外れる():
    """上限を超えて出した本（0〜数回）を、平均の分母に入れないこと。"""
    live = [f"L{i}" for i in range(10)]      # 30分きざみ・先頭10本 ＝ 帯の中
    dead = [f"D{i}" for i in range(20)]      # そのあとに詰めた本 ＝ 帯の外
    pub = _published(live)
    # 帯の外は、生きた本の直後に1分きざみで置く（間隔でも本数でも落ちる）
    last = pub[-1]["at"]
    pub += [{"video_id": v, "at": last + dt.timedelta(minutes=i + 1)}
            for i, v in enumerate(dead)]

    rows = _rows([(v, 1000) for v in live] + [(v, 2) for v in dead])
    vals = eta.live_band_views(rows, published=pub, forms=ROOT / "tests" / "no_such_forms.json")

    assert len(vals) == 10, f"帯の中は10本のはず: {len(vals)}"
    assert sum(vals) / len(vals) == 1000, "帯の中だけの平均になっていない"

    everything, _ = eta.split_per_video(rows)
    diluted = sum(everything) / len(everything)
    assert diluted < 400, "この標本は薄まっているはず（前提の確認）"


def test_帯が引けない回は前の式に落ちる():
    """`data/uploaded.jsonl` が読めない回でも、黙って 0 にしないこと。"""
    assert eta.live_band_views(_rows([("A", 100)]), published=[]) == []


def test__per_video_は帯の中の平均を優先する():
    m = {"views_per_video_live": 678, "views_per_video": 423,
         "median_views_per_video": 300}
    assert eta._per_video(m) == 678
    del m["views_per_video_live"]
    assert eta._per_video(m) == 423
    del m["views_per_video"]
    assert eta._per_video(m) == 300


def test_物差しを取り替えた点は実績として読ませない():
    """`_scale_note` が断らないと、次の回が +60% を『作業が効いた』と読みます。"""
    note = eta._scale_note({"views_per_video": 423},
                           {"views_per_video": 423, "views_per_video_live": 678})
    assert any("分母" in line for line in note), note
    assert any("実績ではありません" in line for line in note), note
    # 既に取り替わった後の点どうしでは、断らないこと（毎回 出ると読み飛ばされる）
    assert eta._scale_note({"views_per_video_live": 678},
                           {"views_per_video_live": 700}) == []
