"""繰下げの連作 5本 の数を、**生成器と違う道で**数え直す（2026-09-19 19:xx・optimizer・Opus 5・1周 1体）。

**なぜ足したか**: `series_kurisage.figures()` は `EVEN = 143` を**定数で持っています**。
繰上げ側（`series_kuriage`）は「250 − 早めた月数」の式でしたが、こちらは **1000 ÷ 7 が割り切れない**ので
「142か月 では足りず、143か月目 でこえる」という**不等式**が本当の背骨です。
**定数は写しなので、写しが正しいことを別の道（月ごとの数え上げ）で照らします。**
`figures()` の中の assert と**同じ式を 2度 書かないこと** —— ここは 1か月ずつ積む側です。

出どころ: 増額率 1か月 0.7%（昭和16年4月2日以後生まれ）・日本年金機構「年金の繰下げ受給」。
70歳まで待つと 60か月 × 0.7% ＝ **42%増**（世間で言う数と一致・15万円 → 21万3000円）。

**覆る条件**:
 (1) `RATE_PERMIL` を替えたら（71〜75歳 の本は率は同じ・75歳 は 120か月 で 84%増）、
     **`EVEN` は動きません**（1000 ÷ 7 は率だけで決まる）。動いたら、動いたほうが誤りです。
 (2) 例の年金額（`P`）を替えても **追いこす月は動きません**（それがこの連作の背骨）。
 (3) `viz` の `lines` が出す交点（`viz._cross_x` → `_age_text`）と、台本の `cross.at` は
     **`viz.check` が `build` で照らします** ＝ ここでは重ねて照らしません（**門は 1か所**）。
"""
import pytest

from studio import series_kurisage as sk


def _catch_up_months(age: int) -> int:
    """**数え上げ**で、繰下げた側の累計が 65歳組を追いこす月を出す（式も定数も使わない）。"""
    m = (age - 65) * 12
    late = sk.P + sk.P * sk.RATE_PERMIL * m // 1000   # 待った側の毎月
    got_late = 0
    got_early = sk.P * m          # 受け取り開始の時点で、65歳組が受け取ずみの額
    months = 0
    while got_late <= got_early:  # 受け取り開始 から 1か月ずつ積む
        got_late += late
        got_early += sk.P
        months += 1
    return months


@pytest.mark.parametrize("age,amount,lost,age_at", [
    (66, 162_600, 1_800_000, "77歳11か月"),
    (67, 175_200, 3_600_000, "78歳11か月"),
    (68, 187_800, 5_400_000, "79歳11か月"),
    (69, 200_400, 7_200_000, "80歳11か月"),
    (70, 213_000, 9_000_000, "81歳11か月"),
])
def test_5本の数が数え上げと合う(age, amount, lost, age_at):
    f = sk.figures(age)
    assert f["amt"] == amount
    assert f["lost"] == lost
    assert f["even"] == sk.EVEN == 143
    assert f["even"] == _catch_up_months(age), "定数 143 と数え上げが割れています"
    assert f"{f['even_age']}歳{f['even_mo']}か月" == age_at


def test_142か月では足りず143か月目でこえる():
    """**声が「割ると」と言わない理由**そのもの（1000 ÷ 7 ＝ 142.857… は割り切れない）。"""
    for age in sk.AGES:
        f = sk.figures(age)
        assert f["add"] * 142 < f["lost"], (age, "142か月 で足りてしまう ＝ 143 は写し違い")
        assert f["add"] * 143 > f["lost"], (age, "143か月 でもこえない ＝ 143 は写し違い")


def test_70歳は42パーセント増():
    """世間の数（「70歳まで待つと42%増」）と一致すること。"""
    f = sk.figures(70)
    assert f["amt"] == sk.P * 142 // 100 == 213_000
    assert f["pct"] == "42"


def test_1年おそくすると追いこす歳も1年うしろへ動く():
    """この連作の背骨（**1年の差で変わる線**）そのもの。"""
    got = [sk.figures(a)["even_age"] for a in sk.AGES]
    assert [b - a for a, b in zip(got, got[1:])] == [1, 1, 1, 1]


def test_追いこす月数は年金額によらない():
    """毎月いくらの人でも同じ（file 冒頭の証明・コマ8 が表で言っている当のこと）。"""
    base = sk.P
    try:
        for p in (70_000, 150_000, 300_000):
            sk.P = p
            assert [_catch_up_months(a) for a in (66, 68, 70)] == [143, 143, 143]
    finally:
        sk.P = base


def test_5本が書き出せる形になっている():
    books = [fn() for fn in sk.ALL]
    assert len(books) == 5
    ids = [d["id"] for d in books]
    assert len(set(ids)) == 5
    for d in books:
        assert d["form"] == "short"
        assert len(d["segments"]) == 10
        # **画面が字だけのコマ を 0 に**（オーナー `9155fe09`）——
        # CTA と「見る所」は板のままでよい（数のコマではない）ので、8コマ を見ます。
        assert all(s.get("viz") for s in d["segments"][:8]), d["id"]
        # 声の門（`script.MAX_SAY` 70字）
        assert max(len(s["say"]) for s in d["segments"]) <= 70, d["id"]


def test_コマ8の表は5本で同じで光る行だけが動く():
    rows = sk.TABLE_ROWS
    assert len(rows) == 5
    for k, age in enumerate(sk.AGES):
        seg = sk.rule_seg(sk.figures(age))
        assert seg["viz"]["rows"] is rows, "表の写しを作らないこと（門は 1か所）"
        assert seg["viz"]["hi"] == k, (age, "光る行がその本の歳の行になっていません")
