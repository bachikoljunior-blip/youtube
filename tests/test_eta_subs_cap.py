"""`sub_rate` の天井 —— **定義上の 100% ではなく、1本あたり登録率の実測の最大。**

## なぜ要るか（2026-08-28 の実測。`scripts/eta.py` の印字がそのまま根拠）

    天井 `sub_rate` ×3,153.91 …… 登録率 100%（定義上の上限）  ← **実測の天井ではありません**
    軌跡（2027-01-07）の 56日目の内訳 …… `sub_rate` ×10.36
    この腕を凍らせると軌跡は **+114日** → **必要な腕です**

到達日は「登録率が ×10.36 になる」前提の上に乗っていました。ところが
**その倍率が実在の幅の中かは、構造上 確かめられません** —— 天井が 100% だと、
どんな倍率でも下に入ります。`per_video` の天井は**実測の最大**（1本あたり再生
1,891回・ショート39本の最大）なので、**同じ物差しを登録率にも当てます。**

実測: 最大 0.2066%（`CdX2oIb7BG8` 1,452再生 3人）÷ いま 0.0317% ＝ **×6.5**。
門（登録者1,000人）に要るのは ×2.08 なので、**この直しは「届かない」と
言っていません** —— 要る倍率と実在の幅を、同じ物差しで並べただけです。

## ここで固定するもの

1. **1本が丸ごと天井にならない**（`min_views` より下の本は数えない）
2. **測れた回は実測を採る**（`measured=True`・`why` に出どころ）
3. **測れない回は元の 100% に落ちる**（消したのではない）
4. **いまの登録率が実測の最大を超えていたら ×1.0**（引き代なしであって、負ではない）
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_subs_cap_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import subs_cap  # noqa: E402

import _eta_pin  # noqa: E402


def _doc(videos: list[dict], at: str = "2026-08-28T00:00:00+09:00") -> dict:
    return {"at": at, "videos": videos}


def _write(tmp_path: Path, videos: list[dict]) -> Path:
    p = tmp_path / "shorts_subs.json"
    p.write_text(json.dumps(_doc(videos), ensure_ascii=False), encoding="utf-8")
    return p


def test_下限より少ない再生の本は天井にしない(tmp_path):
    """**200再生で1人 ＝ 0.5%** は、たまたま1人が付いただけで天井になります。

    `min_views` を置くのはそのためです（既定 1,000再生 ＝ 1人でも 0.1%）。
    """
    p = _write(tmp_path, [
        {"id": "tiny", "views": 200.0, "subs_gained": 1},      # 0.5%（下限より下）
        {"id": "big", "views": 2000.0, "subs_gained": 2},      # 0.1%
    ])
    best = subs_cap.best_per_video(p)
    assert best["video"] == "big"
    assert best["rate"] == pytest.approx(0.001)
    assert best["n"] == 1, "下限より下の本は、数にも入れないこと"


def test_実測が取れた回は天井が実測になる(monkeypatch, tmp_path):
    """いま 0.05% ／ 実測の最大 0.20% → 天井は **×4**（×2,000 ではない）。"""
    _eta_pin.pin_day_cap(monkeypatch, 25.0)
    p = _write(tmp_path, [{"id": "best", "views": 1000.0, "subs_gained": 2}])   # 0.2%
    monkeypatch.setattr(subs_cap, "SRC", p)

    caps = eta.physical_caps({"sub_rate": 0.0005}, density=10.0)
    assert caps["sub_rate"]["measured"] is True
    assert caps["sub_rate"]["factor"] == pytest.approx(4.0)
    assert "実測の最大" in caps["sub_rate"]["why"]
    assert "best" in caps["sub_rate"]["why"], "出どころ（どの本か）を必ず併記すること"


def test_測れない回は定義上の100パーセントに落ちる(monkeypatch):
    """**消したのではありません。** 測れた回だけ実測を使う形です。

    `data/shorts_subs.json` が無い／`videos` が空／Analytics が動画べつの
    登録者を返さなかった回は、ここに落ちます。
    """
    _eta_pin.pin_day_cap(monkeypatch, 25.0)
    monkeypatch.setattr(subs_cap, "best_per_video", lambda *a, **k: None)

    caps = eta.physical_caps({"sub_rate": 0.0005}, density=10.0)
    assert caps["sub_rate"]["measured"] is False
    assert caps["sub_rate"]["factor"] == pytest.approx(2000.0)
    assert "100%" in caps["sub_rate"]["why"]


def test_実測より上に居るときは引き代なし(monkeypatch, tmp_path):
    """**×0.5 を返さないこと。** 密度の天井と同じ扱い（`max(1.0, …)`）。

    倍率が 1 を下回るのは「引き代がマイナス」ではなく、
    **いまの登録率が、実測の最大より上にある**という意味です。
    そのまま返すと、軌跡が**登録率を下げる向きに歩きます。**
    """
    _eta_pin.pin_day_cap(monkeypatch, 25.0)
    p = _write(tmp_path, [{"id": "best", "views": 1000.0, "subs_gained": 1}])   # 0.1%
    monkeypatch.setattr(subs_cap, "SRC", p)

    caps = eta.physical_caps({"sub_rate": 0.002}, density=10.0)     # いま 0.2%
    assert caps["sub_rate"]["factor"] == pytest.approx(1.0)
    assert "引き代なし" in caps["sub_rate"]["why"]


def test_100パーセントより高い実測は採らない(monkeypatch, tmp_path):
    """**低いほうを採る**、という向きを固定する（`min` の向き）。

    実測が定義上の上限より高く出ることは普通ありませんが、
    ここが `max` に化けると、天井が実測より緩む側へ倒れます。
    """
    _eta_pin.pin_day_cap(monkeypatch, 25.0)
    p = _write(tmp_path, [{"id": "best", "views": 1000.0, "subs_gained": 900}])  # 90%
    monkeypatch.setattr(subs_cap, "SRC", p)

    caps = eta.physical_caps({"sub_rate": 0.5}, density=10.0)        # いま 50% → 100% は ×2
    assert caps["sub_rate"]["factor"] == pytest.approx(1.8)
    assert caps["sub_rate"]["factor"] < 2.0, "定義上の 100%（×2）より低いほうを採ること"


def test_実物の帳面から天井が出る():
    """**合成ではなく、この機械が実際に持っている数で1回 通すこと。**

    `data/shorts_subs.json` は API で取り直すので値は動きます。
    ここで見るのは**値ではなく、出るかどうかと桁**です ——
    「登録率 100%」（＝ ×3,000 前後）に落ちていないこと。
    """
    best = subs_cap.best_per_video()
    if best is None:
        pytest.skip("data/shorts_subs.json がまだありません（口が 403 の回）")
    assert 0 < best["rate"] < 0.05, "1本あたり登録率が 5% を超えるなら、下限の置き方を疑うこと"
    assert best["views"] >= subs_cap.MIN_VIEWS


def test_天井の行に分子の人数と1人ぶんの揺れが出る(monkeypatch, tmp_path):
    """**判断する側が読む行に、分子の桁を出すこと**（2026-08-29 に足した）。

    このモジュールの docstring は最初からこう断っていました ——
    「1本の登録者数は小さい整数です。3人／1,452再生なので、±1人で ±0.07% 動きます」。
    **断りは docstring にしか無く、判断する側が読む行には出ていませんでした。**

    その行（`scripts/eta.py --alloc`）は
    「**`per_video` と同じ物差し**」だけを強調します。物差し（実測の最大）は
    同じですが、**分子の桁が違います** —— 向こうは再生 1,891回、こちらは 3人。

    実測: `--alloc` の名指し（`sub_rate` がいちばん早い）は
    **4回 続けて見送られています**（08-28 19:5x / 21:3x / 08-29 00:5x / 04:0x）。
    4回とも理由は別々でしたが、**見送る側が毎回この揺れを手で確かめ直していました。**
    **手で確かめ直すものは、印字する側に置くこと。**
    """
    p = _write(tmp_path, [{"id": "best", "views": 1000.0, "subs_gained": 3}])
    monkeypatch.setattr(subs_cap, "SRC", p)

    best = subs_cap.best_per_video()
    assert best is not None
    low, high = subs_cap.swing(best)
    assert low == pytest.approx(0.002), "3人 → 2人 で 0.2%"
    assert high == pytest.approx(0.004), "3人 → 4人 で 0.4%"

    line = subs_cap.why(best)
    assert "分子は 3人 の整数です" in line, "分子の人数そのものを出すこと"
    assert "0.2000%〜0.4000%" in line, "±1人 ぶんの幅を出すこと"


def test_分子が1人でも揺れの下は0で止まる(monkeypatch, tmp_path):
    """**下側は負にならないこと。** 率が負の天井は意味を持ちません。"""
    p = _write(tmp_path, [{"id": "best", "views": 1000.0, "subs_gained": 1}])
    monkeypatch.setattr(subs_cap, "SRC", p)
    best = subs_cap.best_per_video()
    assert best is not None
    low, _ = subs_cap.swing(best)
    assert low == 0.0
