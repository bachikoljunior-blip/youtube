"""繰上げの連作 5本 の数を、**生成器と違う道で**数え直す（2026-09-19 06:xx・optimizer・Opus 5・1周 1体）。

**なぜ足したか**: `series_kuriage.figures()` は「250 − 早めた月数」の 1本 の式で全部を出しています。
式が 1本 だと、**式そのものが間違っていても 5本 とも仲よく間違います**（この repo でいちばん多い壊れ方の、数の側）。
ここでは**累積を月ごとに積んで**、先に受け取った分が 65歳組に追いこされる月を**数え上げで**出し、
生成器の答えと突き合わせます。**同じ式を 2度 書かないこと**（それは検査ではなく写しです）。

出どころ: 減額率 1か月 0.4%（昭和37年4月2日以後生まれ）・日本年金機構「年金の繰上げ受給」。
`2026-09-16-kuriage-ushinau-3tsu`（長尺）と公開ずみ `lQHX9LJ80Sg` が「60歳 → 80歳10か月」を持っています。

**覆る条件**: (1) `RATE_PERMIL` を替える本を書いたら（0.5%/月 ＝ 昭和37年4月1日以前生まれ）、
この検査の期待値も一緒に替えること（答えは「200 − 早めた月数」）。
(2) 例の年金額（`P`）を替えたら、**追いこされる月は動きません**（それがこの連作の背骨）——
動いたら、動いたほうが誤りです。
"""
import pytest

from studio import series_kuriage as sk


def _catch_up_months(age: int) -> int:
    """**数え上げ**で、65歳組の累計が早くもらった側に追いつく月を出す（式を使わない）。"""
    m = (65 - age) * 12
    early = sk.P - sk.P * sk.RATE_PERMIL * m // 1000
    got_early = early * m          # 65歳の時点で、早くもらった側が受け取ずみの額
    got_late = 0
    months = 0
    while got_late < got_early:    # 65歳 から 1か月ずつ積む
        got_early += early
        got_late += sk.P
        months += 1
    return months


@pytest.mark.parametrize("age,amount,catch_up,age_at", [
    (60, 114_000, 190, "80歳10か月"),
    (61, 121_200, 202, "81歳10か月"),
    (62, 128_400, 214, "82歳10か月"),
    (63, 135_600, 226, "83歳10か月"),
    (64, 142_800, 238, "84歳10か月"),
])
def test_5本の数が数え上げと合う(age, amount, catch_up, age_at):
    f = sk.figures(age)
    assert f["amt"] == amount
    assert f["even"] == catch_up
    assert f["even"] == _catch_up_months(age), "式と数え上げが割れています"
    assert f"{f['even_age']}歳{f['even_mo']}か月" == age_at


def test_1年おそくすると1年うしろへ動く():
    """この連作の背骨（**1年の差で変わる線**）そのもの。"""
    got = [sk.figures(a)["even"] for a in (60, 61, 62, 63, 64)]
    assert [b - a for a, b in zip(got, got[1:])] == [12, 12, 12, 12]


def test_追いこされる月は年金額によらない():
    """毎月いくらの人でも同じ（コマ8 が声で言っている当のこと）。"""
    base = sk.P
    try:
        for p in (80_000, 150_000, 300_000):
            sk.P = p
            assert [sk.figures(a)["even"] for a in (60, 62, 64)] == [190, 214, 238]
    finally:
        sk.P = base


def test_5本が書き出せる形になっている():
    books = [fn() for fn in sk.ALL]
    assert len(books) == 5
    for d in books:
        assert d["form"] == "short" and d["date"] == "2026-09-21"
        assert len(d["segments"]) == 10
        assert "#Shorts" in d["title"]
        # **「歳に」＋ 数 を声に入れないこと**（`hear` が +10年 を拾った形・METHOD §37 の 決め 3）
        for s in d["segments"]:
            assert "歳に1" not in s["say"] and "歳に2" not in s["say"], (
                "「65歳に15年」は「65歳 25年」と聞こえます（`hear` 2026-09-19 06:xx）")
