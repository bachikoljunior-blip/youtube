"""**床が歯止め（`FLOOR_MIN_CLAMP`）に当たった回は、そう印字すること**
（2026-09-12 00:5x・optimizer・Opus。**API 0単位**）。

**踏んだ形**: `quota.short_verdict` の覆る条件 (1) は 2026-09-11 13:1x から
「床の側が `FLOOR_MIN_CLAMP` に当たる回が来たら、床の側も `per_lap` で動き始めるので、
この『平ら』は引かれます」と**註に**書いてありました。
ところが **`short_verdict` は `floor_clipped` を受け取る口を持っておらず**、
`short_words`（`--pace` と 親の【枠】の段が運ぶ 1〜2行）も、その条件を 1文字も印字しません。
＝ 当たった回は、読む側が「床に従えば」を**平らな数だと思ったまま**門に当てます。
§5 教訓の形 7つ目（**覆る条件を註に書いたら、その条件を読む印字も一緒に作ること**）の当のもの。

**撃った盤**（この回・`used` 92.91 / 遅れ 1.7分・`per_lap` だけを落とした。derivation は JOURNAL 00:5x）:

    per_lap   残り 6.4時間（床 29.8分・当たっていない）   残り 1.4時間（生の床 6.6分 ＝ **当たった**）
    0.900       99.21                                 **99.21**
    0.546       99.47                                 **96.74**
    0.150       97.71                                 **93.96**
                ＝ 平ら（振れ 2.2 ポイント・向き無し）   ＝ **単調 +5.25 ポイント**

**この検査が固定するのは 3つ**: (a) `floor_flat` の述語は `"min"` だけを見る（`"max"`・`"spent"` は別）・
(b) 当たった回だけ `short_words` が 3行目 を出す・(c) **盤の向き**（当たると比例して落ちる）。
**きょうの状態は当てません**（§5 教訓の形 6つ目）—— 盤はその場で作り、実物の `pace()` は見ません。

**陽性対照**（`.pyc` を消してから撃った・落ちる件数）:
    `floor_flat` を常に True にする                                  **3件**
    `short_words` の 3行目 を消す                                     **1件**
    述語を「`floor_clipped` が空でなければ平らでない」にする（`"max"`・`"spent"` も巻き込む）  **2件**
    親の段（`spawn_prompt._short_lines`）が `floor_clipped` を渡さない形に戻す        **1件**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402


# 盤を作る条件（**実物の枠を見ない** ＝ 日が経っても腐らない）。
_USED, _LAG = 92.91, 1.7
_LEFT_OPEN, _LEFT_CLIPPED = 6.43, 1.43      # 床 29.8分（歯止めの上）／生の床 6.6分（下）
_PER_LAP = 0.546


def _raw_floor(used: float, left: float, per_lap: float) -> float:
    """`pace()` と同じ式の、歯止めを掛ける前の床（分）。"""
    return per_lap / ((100.0 - used) / left) * 60.0


def test_盤の向き_歯止めに当たると床の側は比例して落ちる() -> None:
    """**(c)** —— 覆る条件 (1) が言っている「平らが引かれる」を、数で押さえる。"""
    assert _raw_floor(_USED, _LEFT_OPEN, _PER_LAP) > quota.FLOOR_MIN_CLAMP
    assert _raw_floor(_USED, _LEFT_CLIPPED, _PER_LAP) < quota.FLOOR_MIN_CLAMP

    laps = [0.150, 0.350, 0.546, 0.700, 0.900]
    open_ = [quota.reach_at_reset(_USED, _LEFT_OPEN, pl, lag_min=_LAG) for pl in laps]
    clip = [quota.reach_at_reset(_USED, _LEFT_CLIPPED, pl, lag_min=_LAG) for pl in laps]

    # 当たっていない側は「平ら」＝ 端から端まで並べても単調にならない。
    assert not all(a <= b for a, b in zip(open_, open_[1:])), open_
    # 当たった側は `per_lap` に**そのまま比例** ＝ 単調に上がり、幅も桁で違う。
    assert all(a <= b for a, b in zip(clip, clip[1:])), clip
    assert (clip[-1] - clip[0]) > (max(open_) - min(open_)), (clip, open_)


def test_floor_flat_は_min_だけを平らの破れと数える() -> None:
    """**(a)** —— 覆る条件 (1-b): `"max"` は逆側・`"spent"` は問いが立たない回。"""
    def flat(clipped):
        return quota.short_verdict(99.5, 97.7, floor_clipped=clipped)["floor_flat"]

    assert flat("min") is False
    assert flat("") is True
    assert flat("max") is True
    assert flat("spent") is True
    # 渡さない呼びは「知らない」＝ None（**False と同じに扱わないこと**）。
    assert quota.short_verdict(99.5, 97.7)["floor_flat"] is None


def test_当たった回だけ_short_words_が_側を引き直せと言う() -> None:
    """**(b)** —— 印字は 1か所（`short_words`）から出し、当たっていない回は黙ること。"""
    hit = quota.short_words(99.5, 97.7, 6.8, 6.4, "min")
    assert "床の側はもう平らではありません" in hit
    assert "13:1x の (1')" in hit
    assert f"{quota.FLOOR_MIN_CLAMP:.0f}分" in hit

    for clipped in ("", "max", "spent", None):
        quiet = quota.short_words(99.5, 97.7, 6.8, 6.4, clipped)
        assert "床の側はもう平らではありません" not in quiet, clipped

    # 判定の行そのものは、当たっても字が変わらないこと（**門は 1か所**・覆る条件 (3)）。
    assert quota.short_words(99.5, 97.7, 6.8, 6.4).splitlines()[0] == hit.splitlines()[0]


def test_着地が読めない回も_floor_flat_を返すこと() -> None:
    """空の返りに欄が無いと、呼ぶ側が `KeyError` か「知らない」を False に落とす。"""
    v = quota.short_verdict(None, None, floor_clipped="min")
    assert v["short"] is None and v["floor_flat"] is False


def test_pace_report_が_floor_clipped_を渡すこと() -> None:
    """**印字の口は 1本**（手で引き比べる行を残さない・`test_quota_short_verdict` と同じ族）。"""
    body = (ROOT / "scripts" / "quota.py").read_text(encoding="utf-8")
    i = body.index("print(short_words(")
    assert 'p.get("floor_clipped")' in body[i:i + 400], "pace_report が床の当たりを渡していません"


def test_親の段も_floor_clipped_を渡すこと() -> None:
    """段が渡さないと、**`--pace` にだけ出て、サブが読む段には出ません**（17:0x と同じ形）。"""
    body = (ROOT / "scripts" / "spawn_prompt.py").read_text(encoding="utf-8")
    i = body.index("def _short_lines(")
    j = body.index("def _quota_block(", i)
    assert 'p.get("floor_clipped")' in body[i:j], "【枠】の段が床の当たりを渡していません"
