# -*- coding: utf-8 -*-
"""**`slot_value` の形どうしの比が、押される面の差を約分して消していないか**
（2026-09-19 23:xx・optimizer・Opus 5・ultracode・**API 0単位**）。

**なぜ在るか**: `slot_value.perf_yen` は **平均再生 × `perf_rate_band()` の中段 × 単価の中段**で、
註は「両方に同じ帯を掛けるので**約分され**、比は `mean` の比そのもの ＝ **どちらの形へ枠を配るかは読める**」
と書いていました。**約分できるのは、押される率が形で同じときだけです。**
METHOD §5【2026-09-19 08:xx】は **同じではない**と決めています ——
長尺の説明欄の URL は押せ、ショートのは押せない（ショートだけ「アイコン→チャンネル→説明欄」の 1歩 多い）。
＝ **その比は「再生の比」であって「クリックの比」ではありません。**
そして期限の中で目標に届く唯一の道（成果報酬）の通貨は、再生ではなく**クリック**です。

この検査が守るのは 3つ:
  (1) 毎周の行が、**約分は安全だ**とは言わないこと（前の字が戻ってきたら落ちる ＝ 陰性対照）
  (2) 毎周の行が、**分かれ目**（short が先でいられる、残る割合の下限 ＝ 1/倍率）を数で出すこと
  (3) 分かれ目が **式から引かれている**こと（倍率 21.4 ↔ 4.7% が動いても食い違わない）
      ＝ **2か所 に数を置かない**（`docs/METHOD.md` の作法）

**わざと守らないこと**: `perf_yen` の**式も定数も並びも**この検査は縛りません。
残る割合は**未測**で、推測の数を入れれば次の回に「測った数」として読まれます
（`PERF_CLICK_BAND` が 11件 で「実測」になった時と同じ形）。**いま置けるのは分かれ目だけです。**
"""
import re

from studio import trend
from studio.common import ledger_rows


def _line() -> str:
    return trend.slot_value_line(ledger_rows())


def test_約分は安全だと言わないこと():
    """**陰性対照**: 前の字（「比には帯が残りません ＝ どちらへ枠を配るかは読めます」）が戻ったら落ちる。"""
    s = _line()
    assert "比には帯が残りません" not in s, (
        "約分を安全だと言う字が戻っています ＝ `PERF_CLICK_BAND` の下の註（09/19 23:xx）を読むこと"
    )
    assert "絶対値は読めないが、どちらへ枠を配るかは読めます" not in s
    assert "約分は安全ではありません" in s


def test_分かれ目が数で出ること():
    s = _line()
    assert "1歩 多い" in s, "ショート側の 1歩（アイコン→チャンネル→説明欄）を名指しすること"
    assert "未測" in s, "残る割合は未測 ＝ 測った数のように読ませないこと"
    assert re.search(r"直リンクの [\d.,]+% より", s), "分かれ目（%）が行に無い"


def test_分かれ目が倍率から引かれていること():
    """(3) 倍率 N倍 と 分かれ目 100/N% が食い違わないこと（**2か所 に数を置かない**）。"""
    s = _line()
    m_ratio = re.search(r"short が \*\*([\d.,]+)倍\*\* 先", s)
    m_hop = re.search(r"直リンクの ([\d.,]+)% より", s)
    if not (m_ratio and m_hop):
        # まだ `short`／`long` の片方しか読めていない周（`enough_n` の手前）は、この行が出ません。
        assert "まだ 1本 も読めていません" in s or "門の外" in s
        return
    ratio = float(m_ratio.group(1).replace(",", ""))
    hop = float(m_hop.group(1).replace(",", ""))
    assert abs(hop - 100.0 / ratio) < 0.15, f"{ratio}倍 なら {100.0 / ratio:.1f}% のはずが {hop}%"


def test_陽性対照_帯を動かしても分かれ目は動かないこと():
    """**陽性対照**: 分かれ目は「帯が約分される所」なので、帯を変えても % は動いてはいけない。

    動いたら、分かれ目が `mean` の比ではなく帯から引かれている ＝ 註と食い違う。
    """
    s0 = _line()
    old = trend.PERF_CLICK_BAND
    try:
        trend.PERF_CLICK_BAND = tuple(b * 3.0 for b in old)
        s1 = _line()
    finally:
        trend.PERF_CLICK_BAND = old
    g = lambda s: (re.search(r"直リンクの ([\d.,]+)% より", s) or [None, None])[1]
    assert g(s0) == g(s1), "帯を 3倍 にしたら分かれ目が動いた ＝ 約分されていない所から引いている"
