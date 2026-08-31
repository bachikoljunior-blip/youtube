"""**ファン課金の門（expanded YPP）が、広告の門より手前にあることを固定する。**

## なぜ要るか（2026-08-30・最適化の回）

`docs/MEANS.md` の M23 は 2026-08-29 から 2026-08-30 まで、こう判定していました:

    **メンバーシップと Super Thanks は、AdSense と同じ門の後ろにあります**（要確認）。
    門を早める効果は 0 で、門の後の分子を 数% 増やすだけ。

**外れです。** 公表値は2段あります
（`support.google.com/youtube/answer/13429240` を 2026-08-30 に直接 読んだ）:

    expanded YPP  登録者 500人 ＋ 90日に公開3本
                  ＋（12か月 3,000時間 ／ 90日 ショート 300万回）
                  → メンバーシップ・Super Thanks・Super Chat・Jewels・Shopping
    YPP           登録者 1,000人
                  ＋（12か月 4,000時間 ／ 90日 ショート 1,000万回）
                  → **上に加えて** 広告と Premium

**この取り違えは1年 生き延びました**（`eta.py` の門は初回から1段だけ）。
外れた理由は「要確認」と書いたまま**誰も確認しなかった**ことなので、
**確認した結果のほうを、落ちるテストとして置きます。**
註だけだと、次に定数をいじる側は註を読まずに通せます。

## このテストが守っているのは「2段あること」であって、数字の暗記ではありません

だから**上の段と下の段の関係**を見ます（下 < 上）。
公表値そのものが変わったら、下の `test_published_values` が落ちて気づけます。

## 覆る条件

- **YouTube が公表値を変えたら**、`test_published_values` を取り直すこと。
  出どころは上の1枚だけ。**記憶で直さないこと**
- **下の段が日本で使えないと分かったら**（国べつの可用性は**未確認**）、
  `eta.py` の下の段ごと消すこと。このテストもそのとき消す
- **ファン課金の分子（加入率・単価）が実測で入ったら**、このテストは
  「門が手前」までしか見ていないので、**分子の側は別に固定すること**
"""

import scripts.eta as eta


def test_published_values():
    """**公表値そのもの。** 記憶ではなく、読んだ数字を置いてある。"""
    assert eta.FAN_SUBS_GATE == 500
    assert eta.FAN_HOURS_GATE == 3_000
    assert eta.FAN_SHORTS_VIEWS_GATE == 3_000_000
    assert eta.SUBS_GATE == 1_000
    assert eta.LONG_HOURS_GATE == 4_000
    assert eta.SHORTS_VIEWS_GATE == 10_000_000


def test_fan_gate_is_strictly_earlier_on_every_leg():
    """**全部の脚で手前**。1つでも逆転したら、M23 の判定を組み直すこと。"""
    assert eta.FAN_SUBS_GATE < eta.SUBS_GATE, "登録者の脚"
    assert eta.FAN_HOURS_GATE < eta.LONG_HOURS_GATE, "視聴時間の脚"
    assert eta.FAN_SHORTS_VIEWS_GATE < eta.SHORTS_VIEWS_GATE, "ショートの脚"


def test_fan_gate_does_not_unlock_ads():
    """**下の段で広告は開きません。**

    ここを取り違えると「門が手前 ＝ 早く広告収入が入る」と読めてしまい、
    到達日が根拠なく前に出ます。**開くのはファン課金だけ**です。
    """
    unlocks = eta.FAN_GATE_UNLOCKS
    assert "メンバーシップ" in unlocks
    assert "Super Thanks" in unlocks
    assert "広告" not in unlocks, "下の段に広告を書かないこと"
    assert "Premium" not in unlocks, "下の段に Premium を書かないこと"


def test_no_revenue_number_was_smuggled_in():
    """**分子を足していないこと。**

    M23 の縛りは「**帯を増やさない**」——未測定の単価や加入率を入れると、
    到達日がその推測で動きます。下の段の定数は**門の3つと文言だけ**で、
    `RPM_SCENARIOS` は6帯のまま。**増えていたら、日付が推測で動いています。**
    """
    assert len(eta.RPM_SCENARIOS) == 6, "帯が増えている ＝ 未測定の分子が入った"
    fan_names = [n for n in dir(eta) if n.startswith("FAN_")]
    assert sorted(fan_names) == [
        "FAN_GATE_UNLOCKS",
        "FAN_HOURS_GATE",
        "FAN_SHORTS_VIEWS_GATE",
        "FAN_SUBS_GATE",
    ], f"下の段に定数が増えています: {fan_names}"
