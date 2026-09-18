"""`studio/series_taishoku.tax` が、長尺 `2026-09-17-taishokukin-2000man-tedori` の説明欄に在る数を **同じ式で再現する**こと。

長尺の説明欄（09/17 公開・`ukEFxTt1PEY`）の 9つ の数が陽性対照。**ここが割れたら、連作の数は 1つ も出さないこと**
（式は 1か所 `tax()`・国税庁 No.1420／2260／2732）。2026-09-18 03:3x・optimizer・Fable 5.1・ultracode。
"""
import json
from pathlib import Path

import pytest

from studio.series_taishoku import ALL, BRACKETS, deduction, man, tax

ROOT = Path(__file__).resolve().parents[1]

# 長尺の説明欄に書いてある数（税金の合計・手取り）。長尺の側の写しではなく、長尺の説明欄から目で写した陽性対照。
LONG_DESC = {
    (2000, 20): (1_388_700, 18_611_300),
    (2000, 25): (856_300, 19_143_700),
    (2000, 30): (405_700, 19_594_300),
    (2000, 31): (334_900, 19_665_100),      # 30年2か月 → 31年（端数の切り上げ）
    (2000, 35): (113_200, 19_886_800),
    (2000, 38): (0, 20_000_000),
    (2500, 30): (1_084_500, 23_915_500),
    (3000, 30): (1_861_800, 28_138_200),
}


@pytest.mark.parametrize("key,exp", sorted(LONG_DESC.items()))
def test_長尺の説明欄の数を同じ式で再現する(key, exp):
    a, y = key
    t = tax(a * 10_000, y)
    assert (t["tax"], t["net"]) == exp, (key, man(t["tax"]), man(t["net"]))


def test_控除の下限は80万円():
    assert deduction(1) == 800_000 and deduction(2) == 800_000 and deduction(3) == 1_200_000
    assert deduction(20) == 8_000_000 and deduction(21) == 8_700_000 and deduction(30) == 15_000_000


def test_速算表は上限が増える順():
    his = [hi for hi, _, _ in BRACKETS]
    assert his == sorted(his)


def test_man():
    assert man(19_594_300) == "1959万4300円" and man(15_000_000) == "1500万円" and man(0) == "0円" and man(97_500) == "9万7500円"


def test_連作の声の数は式の数と同じ():
    """コマ1（フック）の手取りと税金が `tax()` の数そのもの（丸めていない）。"""
    for f in ALL:
        d = f()
        a = int(d["id"].split("taishokukin-")[1].split("man")[0])
        t = tax(a * 10_000, 30)
        hook = d["segments"][0]["say"]
        assert man(t["net"]) in hook and man(t["tax"]) in hook, (d["id"], hook)
        assert sum(len(s["say"]) for s in d["segments"]) <= 450, d["id"]      # METHOD §31: 連作は 450字 まで


def test_台本が在れば生成器と同じ():
    """書いた台本を手で直したら、生成器を直すこと（次に書き直すと戻る）。

    **ただし、CTA の差し替え（2026-09-18 20:3x）より前に焼いて上げた本は外します**
    （`series_taishoku.BAKED_BEFORE_CTA_SWITCH` の註・上げ直しに 1本 1,650単位）。
    """
    from studio.series_taishoku import BAKED_BEFORE_CTA_SWITCH
    for f in ALL:
        d = f()
        if d["id"] in BAKED_BEFORE_CTA_SWITCH:
            continue
        p = ROOT / "data/studio/scripts" / f"{d['id']}.json"
        if not p.exists():
            continue
        on_disk = json.loads(p.read_text(encoding="utf-8"))
        assert [s["say"] for s in on_disk["segments"]] == [s["say"] for s in d["segments"]], d["id"]
