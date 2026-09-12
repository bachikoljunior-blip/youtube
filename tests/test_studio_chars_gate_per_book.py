"""字数の門は、**焼いたことが在る本ではその本の実測 字/秒 から引く**
（2026-09-12 13:4x・hourly・Opus）。

**なぜ**: 480字 の1つの門は、台帳 `built` 105件・8本 に当てると**両側に外れます**。

    遅い本  09/07 `2026-09-07-kurisage-81sai-11kagetsu` は **480字 で 96.9秒** を焼いた
            ＝ 門は 95秒 の代理のはずなのに、**越える本を通していました**
    速い本  09/11 は 503字ぶん・09/13 は 500字ぶん の余りが在り、
            ＝ 門が **20〜23字 ぶん、分かる説明を削らせていました**

本ごとの最小 字/秒 は **4.823〜5.552（15%）**開き、同じ本の中は 0.9〜2.3% に収まります
（`docs/JOURNAL.md` 2026-09-12 13:4x に 8本 の表）。だから**本ごとに引く**のが正しい。

**この検査は実物の台帳を読みません**（§5 の教訓 6つ目「きょうの状態を不変条件に書かない」）——
台帳は毎周 伸びるので、行はここで作ります。
"""
import pytest

from studio import cli, script


def _rows(vid: str, pairs: list[tuple[int, float]]) -> list[dict]:
    return [{"event": "built", "id": vid, "chars": c, "seconds": s} for c, s in pairs]


def test_焼いていない本は代理の480():
    gate, why = script.chars_gate("まだ焼いていない", rows=[])
    assert gate == script.MAX_TOTAL_CHARS
    assert "代理" in why


def test_遅い本は門が下がる():
    """09/07 の実物の形（480字 が 96.9秒 になった本）。門は 480 より**下**でなければならない。"""
    rows = _rows("slow", [(480, 96.9), (466, 94.5)])
    gate, _ = script.chars_gate("slow", rows=rows)
    assert gate < script.MAX_TOTAL_CHARS
    assert gate / min(c / s for c, s in [(480, 96.9), (466, 94.5)]) <= script.MAX_SECONDS


def test_速い本は門が上がる():
    """09/13 の実物の形（479字 が 87.2秒）。門は 480 より**上**（余りを削らせない）。"""
    rows = _rows("fast", [(479, 87.2), (477, 87.9), (467, 85.2)])
    gate, why = script.chars_gate("fast", rows=rows)
    assert gate > script.MAX_TOTAL_CHARS
    assert "字/秒" in why


def test_門はいちばん遅い焼きから引く():
    """越える側に外れないため（速いほうを採ると、次の焼きで `MAX_SECONDS` を越え得る）。"""
    rows = _rows("mix", [(480, 87.0), (480, 94.0)])      # 5.517 と 5.106
    gate, _ = script.chars_gate("mix", rows=rows)
    assert gate == int(480 / 94.0 * script.MAX_SECONDS * (1 - script.BUILD_JITTER))


def test_門を通った字数は秒数の上限を越えない():
    """門の定義そのもの（**どの本でも**）。`BUILD_JITTER` のぶん手前に居ること。"""
    for pairs in ([(480, 96.9)], [(479, 87.2)], [(461, 94.5)], [(450, 91.7)]):
        rows = _rows("v", pairs)
        gate, _ = script.chars_gate("v", rows=rows)
        rate = min(c / s for c, s in pairs)
        assert gate / rate <= script.MAX_SECONDS * (1 - script.BUILD_JITTER) + 1e-9


def test_秒数の上限の出どころは1か所():
    """写しを持つと 2か所 がずれます（§5 の教訓 7つ目）。"""
    assert cli.MAX_SECONDS == script.MAX_SECONDS


def test_陽性対照_本ごとをやめると遅い本を通す(monkeypatch):
    """**壊したら落ちる**ことを撃つ（§5 の教訓の形 3つ目）。

    `chars_gate` が台帳を見ずに 480 を返す形（＝ 直す前）に戻すと、
    **96.9秒 を焼いた本が 480字 で通ります**。
    """
    rows = _rows("slow", [(480, 96.9)])
    assert script.chars_gate("slow", rows=rows)[0] < 480      # いまは止まる

    monkeypatch.setattr(script, "built_rate", lambda vid, rows=None: None)
    assert script.chars_gate("slow", rows=rows)[0] == 480     # 戻すと通る


def test_problems_は本ごとの門で鳴る(monkeypatch):
    """`problems()` が `chars_gate` を通っていること（定数を直に読んでいない）。"""
    segs, left = [], 470
    while left > 0:
        n = min(script.MAX_SAY, left)
        segs.append(script.Segment(say="あ" * n, show="x", sub=""))
        left -= n
    s = script.Script(id="t-gate", date="2026-09-12", title="t #Shorts",
                      takeaway="t", segments=segs)
    assert not [p for p in s.problems() if "合計" in p]        # 470 < 480（代理）

    monkeypatch.setattr(script, "chars_gate", lambda vid, rows=None: (460, "検査の門"))
    got = [p for p in s.problems() if "合計" in p]
    assert len(got) == 1 and "検査の門" in got[0]
