"""**腕を選ぶ表の天井が、規則を見ていること**（2026-08-31・最適化の回）。

## この検査が持っている主題

前の回からの申し送りは、この1行でした ——

    grep -n "house_rule" scripts/eta.py   ← ここに出てこない天井が、次の候補

**`_levers()` は、その grep に出てきませんでした。** 中身はこうです::

    per_day_cap = a["per_video_now"] * UPLOAD_CAP_PER_DAY      # **92本/日**
    rows.append(("本数だけで届く上限", ..., f"...（92本の上限。**×31.8 まで**）"))

**規則は 1本/日 です**（`src/house_rule.PUBLISH_PER_DAY`・オーナーが固定・覆る条件なし）。

## なぜ、ここが特に高くつくか

この行が乗っている表の見出しは、こうです ——

    --- 早めるには、どれを何倍にするか（**倍率が小さいものから手を付ける**）---

**その回にどの腕を引くかを、読む側はこの表から選びます。**
92本 の天井は「本数を増やせば再生は ×31.8 まで伸ばせる」と読めますが、
**規則の下では 1本も増やせません。** 腕 `density` の天井は `×1.00`（引き代なし）だと
`eta.py` は別の場所で自分で印字しており、**同じ画面の2か所が食い違っていました。**

## 実測（2026-08-31・`analyse()` の返りに当てた・API 0単位）

    本数だけで届く上限   86,676回／日（92本の上限・**×31.8 まで**）
                      → **942回／日**（規則 1本/日）  **92分の1**

そして規則を入れると、この行は**向きが変わります**（そこがこの直しの本体です）——
いまの再生／日 **2,724回** は、規則 1本/日 の定常 **942回** より**上**です。
差は**予約の在庫を消化しているぶん**で、**在庫が尽きれば下がります。**

## この検査が見ている3点

1. **天井の出どころが `_ceiling_per_day()` の1か所であること**（規則・観測・口 の最小）
2. **規則が縛っているあいだ、`UPLOAD_CAP_PER_DAY` の 92 が答えに出ないこと**
3. **上限がいまの再生／日 を下回るとき、「まだ伸ばせる」と読める字を出さないこと**

**緩めないこと。** 緩めた瞬間、腕を選ぶ表がもう一度 92倍 楽観に戻ります。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _eta():
    spec = importlib.util.spec_from_file_location("etamod_levers", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(eta, a: dict) -> str:
    for label, _now, need in eta._levers({}, a):
        if label.startswith("本数だけで届く上限"):
            return need
    pytest.fail("`_levers()` に「本数だけで届く上限」の行がありません")
    return ""


def _fake(eta, *, per_video: float, views_per_day: float) -> dict:
    """`_levers()` が読む欄だけを持つ、最小の `analyse()` の返り。"""
    return {
        "subs_remaining": 977.0,
        "subs_per_day": 0.86,
        "sub_rate": 0.000315,
        "views_per_day": views_per_day,
        "per_video_now": per_video,
        "ceiling_per_day": eta._ceiling_per_day(),
        "ceiling_caps": {"規則": float(eta.house_rule.PUBLISH_PER_DAY),
                         "観測": 10.0, "口": float(eta.UPLOAD_CAP_PER_DAY)},
    }


def test_本数の天井は規則を見ている():
    """**1・2 の検査。** 92本 の日枠ではなく、規則 1本/日 で掛けること。"""
    eta = _eta()
    rule = float(eta.house_rule.PUBLISH_PER_DAY)
    a = _fake(eta, per_video=942.125, views_per_day=2724.1)

    need = _row(eta, a)
    wrong = f"{942.125 * eta.UPLOAD_CAP_PER_DAY:,.0f}回"
    right = f"{942.125 * rule:,.0f}回"

    assert right in need, (
        f"「本数だけで届く上限」が {right} を出していません: {need!r}\n"
        f"  規則は {rule:,.0f}本/日（`src/house_rule.py`）。"
        f" `UPLOAD_CAP_PER_DAY`（{eta.UPLOAD_CAP_PER_DAY}本）を掛けていないか、"
        f" 出どころが `_ceiling_per_day()` から外れています"
    )
    assert wrong not in need, (
        f"日枠 {eta.UPLOAD_CAP_PER_DAY}本/日 で掛けた数 {wrong} が残っています: {need!r}\n"
        "  **この表から、その回に引く腕を選びます。**"
        f" 92本 の天井は「本数で ×{eta.UPLOAD_CAP_PER_DAY / max(rule, 1):,.0f} 伸ばせる」と"
        "読めますが、規則の下では1本も増やせません"
    )


def test_上限がいまを下回る回は_伸ばせると読める字を出さない():
    """**3 の検査。** 向きが変わる回に、向きの変わった字が出ること。

    規則 1本/日 では、上限（942回／日）がいまの再生／日（2,724回）を**下回ります**。
    差は予約の在庫を消化しているぶんで、**在庫が尽きれば下がります。**
    ここで「**×0.35倍まで**」とだけ出すと、読む側は「まだ伸ばせる」と読みます。
    """
    eta = _eta()
    if float(eta.house_rule.PUBLISH_PER_DAY) * 942.125 >= 2724.1:
        pytest.skip("規則の上限がいまの再生／日 を上回っています（この場では向きが変わりません）")

    need = _row(eta, _fake(eta, per_video=942.125, views_per_day=2724.1))
    assert "持続しません" in need or "1本も増やせません" in need, (
        f"上限がいまの再生／日 を下回る回なのに、その断りがありません: {need!r}\n"
        "  **『まだ ×N倍 伸ばせる』と読める行を残さないこと。**"
        " 差は予約の在庫を消化しているぶんで、在庫が尽きれば下がります"
    )


def test_上限がいまを上回る回は_倍率のまま出す():
    """**逆側**。規則が緩ければ（あるいは再生が薄ければ）、素直に倍率を出すこと。

    **片側だけを見る検査は、片側だけの証拠**です。
    ここを置かないと、上の検査は「いつでも警告を出す」実装でも緑になります。
    """
    eta = _eta()
    # いまの再生／日 を 1回 に置けば、上限は必ず上回る
    need = _row(eta, _fake(eta, per_video=942.125, views_per_day=1.0))
    assert "倍まで" in need, (
        f"上限がいまの再生／日 を上回る回に、倍率の行が出ていません: {need!r}"
    )
    assert "持続しません" not in need, (
        f"上回っているのに「持続しません」を出しています: {need!r}"
    )


def test_天井の出どころは_ceiling_per_day_の1か所():
    """**1 の検査の、別の当て方。** 規則を動かしたら、答えも動くこと。

    定数を書いた実装は、ここで落ちます（`house_rule` を差し替えても答えが動かない）。
    """
    eta = _eta()
    keep = eta.house_rule.PUBLISH_PER_DAY
    try:
        eta.house_rule.PUBLISH_PER_DAY = 5
        a = _fake(eta, per_video=100.0, views_per_day=1.0)
        need = _row(eta, a)
        assert "500回" in need, (
            f"規則を 5本/日 にしたのに、上限が 500回／日 になりません: {need!r}\n"
            "  **天井に定数を書いています。** 出どころは `_ceiling_per_day()` の1か所"
        )
    finally:
        eta.house_rule.PUBLISH_PER_DAY = keep
