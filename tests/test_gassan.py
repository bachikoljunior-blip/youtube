"""**高額介護合算療養費の表。**（2026-08-18 に新設）

`check_tables()` が守っているのは「値」で、**主張のほうは守れません。**
ここで固定するのは、docstring が言い切っている7つの主張そのものです。

**故障注入つき** —— 値を壊したときに落ちる側も見ます。片側だけでは
「この検査が効いている」とは言えません（2026-08-18 の `zeinuki_limit` と同じ形）。
"""
from __future__ import annotations

import pytest

from src.calc import _checks, gassan


def test_医療だけで9割5分が埋まる():
    """**この表の中心。**5区分すべてが 95〜97 パーセントに入る。"""
    warr = [r["埋まる割合（パーセント）"] for r in gassan.umari()]
    assert min(warr) >= 95.0, f"9割5分を割った区分がある: {warr}"
    assert max(warr) <= 97.0, f"9割7分を超えた区分がある: {warr}"
    # **段の額は6.2倍ひらくのに、埋まり方はほぼ同じ** ← 言えるのはここ
    caps = [r["年間限度額（円）"] for r in gassan.umari()]
    assert round(max(caps) / min(caps), 1) == 6.2
    assert round(max(warr) - min(warr), 1) == 1.4


def test_残る枠の実額():
    nokori = {r["区分"][0]: r["残る枠（円）"] for r in gassan.umari()}
    assert nokori["ウ"] == 30_100
    assert nokori["オ"] == 12_400
    assert nokori["ア"] == 101_300


def test_加算の無い区分は医療費がいくら高くても届かない():
    rows = {r["区分"][0]: r for r in gassan.todoku_iryohi()}
    assert rows["エ"]["届く総医療費（月・円）"] is None
    assert rows["オ"]["届く総医療費（月・円）"] is None
    assert rows["ウ"]["届く総医療費（月・円）"] == 1_270_333
    assert rows["イ"]["届く総医療費（月・円）"] == 2_918_000
    assert rows["ア"]["届く総医療費（月・円）"] == 4_218_666


def test_届く医療費は逆算と一致する():
    """**同じ数を2通りで出して突き合わせる**（1パーセント加算の逆算）。"""
    for row in gassan.todoku_iryohi():
        m = row["届く総医療費（月・円）"]
        if m is None:
            continue
        kubun = row["区分"][0]
        # 本来の上限の月が3か月、その月だけが1パーセント加算を持つ
        nen = 3 * gassan.iryo_tsuki(kubun, m) + 9 * gassan.iryo_tsuki(kubun, m, tasukai=True)
        jogen = row["残る枠（円）"] + gassan.iryo_nenkan(kubun, 0)
        assert abs(nen - jogen) <= 3, f"{kubun}: 逆算が合わない {nen} 対 {jogen}"


def test_介護だけで超えるのは低所得Iの世帯上限だけ():
    rows = gassan.kaigo_dake()
    koeru = [r for r in rows if r["埋まる割合（パーセント）"] > 100]
    assert len(koeru) == 1
    assert koeru[0]["埋まる割合（パーセント）"] == 155.4
    assert koeru[0]["介護だけの年額（円）"] == 295_200
    assert koeru[0]["年間限度額（円）"] == 190_000
    # **同じ段が、世帯か個人かで入れ替わる**（15,000円なら 94.7% で超えない）
    kojin = [r for r in rows if r["介護の月額上限（円）"] == 15_000]
    assert len(kojin) == 1
    assert kojin[0]["埋まる割合（パーセント）"] == 94.7


def test_戻るのは払った額の4割台():
    warr = [r["戻る割合（パーセント）"] for r in gassan.modoru()]
    assert min(warr) >= 42.0 and max(warr) <= 46.0, warr
    u = next(r for r in gassan.modoru() if r["区分"].startswith("ウ"))
    assert u["合計（円）"] == 1_172_700
    assert u["戻る額（円）"] == 502_700


def test_70歳を境に非課税の限度額が下がる():
    rows = {r["70歳以上の立場"]: r for r in gassan.nanajussai()}
    ni = rows["70歳以上・低所得II（住民税非課税）"]
    assert ni["70歳未満の限度額（円）"] == 340_000 and ni["下がる額（円）"] == 30_000
    ichi = rows["70歳以上・低所得I（年金収入80万円以下等）"]
    assert ichi["70歳以上の限度額（円）"] == 190_000
    assert ichi["下がる額（円）"] == 150_000 and ichi["倍率"] == 1.79
    # **同額の組もある**（下がるだけの話ではない、と言えるのはこの行があるから）
    onaji = rows["70歳以上・現役並みI"]
    assert onaji["下がる額（円）"] == 0 and onaji["倍率"] == 1.0


def test_差の額そのものが表に出ている():
    """**angle が書く数は、表が印字していなければ裏が取れません。**

    `s-gassan-70-lower-cap` の「30,000円下がる」で
    `test_doc_numbers.test_topics_yamlには掛けない` が落ちました（2026-08-18）。
    段の額を並べても、**差は別の数**です。
    """
    printed = {r["下がる額（円）"] for r in gassan.nanajussai()}
    assert {0, 30_000, 40_000, 150_000} <= printed, printed


def test_500円の死に区間():
    assert gassan.shikyu(670_500, 670_000) == 0
    assert gassan.shikyu(670_501, 670_000) == 501
    deru = [r["限度額を超えた額（円）"] for r in gassan.gake() if r["出るか"] == "出る"]
    assert min(deru) == 501


def test_多数回が無ければ5区分すべてが超える():
    rows = gassan.tasukai_nashi()
    assert all(r["なしなら超える額（円）"] > 0 for r in rows), rows
    a = next(r for r in rows if r["区分"].startswith("ア"))
    assert a["多数回が減らした額（円）"] == 1_012_500
    # **比で見ると、1パーセント加算のある3区分だけが揃う**（半分は超えません。
    # docstring に「限度額より大きい区分がある」と書いてここで落ちました）
    hi = {r["区分"][0]: round(r["多数回が減らした額（円）"] * 100
                              / r["年間限度額（円）"], 1) for r in rows}
    assert [hi["ア"], hi["イ"], hi["ウ"]] == [47.8, 47.5, 48.0]
    assert [hi["エ"], hi["オ"]] == [19.8, 28.6]
    assert max(hi.values()) < 50.0, "半分を超えた区分がある（主張のほうを直すこと）"


def test_故障注入_段を1つ壊すと落ちる(monkeypatch):
    """**当たりの側でだけ通る**形になっていないか。"""
    gassan.check_tables()                       # 壊す前は通る
    monkeypatch.setattr(gassan, "NENKAN_70MIMAN",
                        [(n, c if c != 670_000 else 60_000)
                         for n, c in gassan.NENKAN_70MIMAN])
    with pytest.raises(_checks.TableError):
        gassan.check_tables()


def test_故障注入_多数回の月数を壊すと落ちる(monkeypatch):
    monkeypatch.setattr(gassan, "TASUKAI_TSUKI", 12)
    with pytest.raises(_checks.TableError):
        gassan.check_tables()


def test_故障注入_支給の下限を消すと落ちる(monkeypatch):
    monkeypatch.setattr(gassan, "KYUFU_SHITA", 0)
    with pytest.raises(_checks.TableError):
        gassan.check_tables()


def test_月額上限は総医療費に対して単調():
    _checks.never_decreases(lambda m: gassan.iryo_tsuki("ウ", m),
                            [0, 267_000, 500_000, 1_000_000, 5_000_000],
                            "総医療費が増えたのに月額上限が下がった")
    assert gassan.iryo_tsuki("ウ", 1_000_000) == 87_430
    assert gassan.iryo_tsuki("エ", 5_000_000) == 57_600, "加算の無い区分が動いている"
