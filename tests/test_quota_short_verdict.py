"""**「短く終わってよいか」の門は、着地の 2つ のうち「床に従えば」の側で読む。**

2026-09-11 13:1x・optimizer・Opus。`sweep_verdict`（11:2x）と**同じ型**の穴を閉じた。

**踏んだ形**: METHOD §5 の 2026-09-10 15:1x の決めの覆る条件 (1) は
「『すべて』の着地が **98%** を越えたら optimizer も短くてよい」ですが、
**この 98 は METHOD の字の中にしか無く**、`--pace` は着地を **2つ** 印字しながら
「で、短く終わってよいのか」を1度も言いませんでした（40周 のあいだ、毎回 人が手で
「97.6% ＝ 98% の下」と引き比べている）。METHOD §5「教訓の形（7つ目）」＝
**覆る条件を註に書いたら、その条件を読む印字も一緒に作ること**。

**そして、どちらの側に当てるかで答えが変わります**（`short_verdict` の盤・この回に撃った）:
`per_lap` を落とすと「床に従えば」は **0.20 まで 99.4〜99.8% で平ら**、
「いまの間隔のまま」は **99.4 → 93.4（0.35）→ 89.2（0.20）** と比例して落ちる。
「短く終わる」は `per_lap` を軽くする手そのものなので、
**間隔の側で読むと、門は自分が許した手で下がる数を読む**ことになります。

**この回は 2つ が重なっている点**（99.44 / 99.41）なので、側を決めた効きはまだ出ていません
——だから検査は**重なっていない組**でも当てます（`agree` False の側）。

**きょうの状態を不変条件として書かないこと**（METHOD §5 教訓の形 6つ目）＝
この検査は `pace()` を1度も呼ばず、数はその場で渡します。

**陽性対照**（壊したら落ちるまで撃つ・教訓の形 3つ目。`.pyc` を消してから撃った）:
`short_verdict` の読む側を `reach_carry` へ倒すと **2件**／
門の数を関数の中へ焼き込む（`SHORT_LANDING_GATE` を読まない）と **1件**／
`blind` の向き（窓 ＞ 残り）を逆にすると **1件**／
`pace_report` が `short_words` を通らない形に戻すと **1件**。

**そのうち門の1つは、1度目 落ちませんでした**（この回に踏んだ・教訓の形 3つ目の当のもの）:
検査が `gate = quota.SHORT_LANDING_GATE` から当てていたので、
**関数の中へ 98 を焼き込んだ版と 1件も見分けが付かなかった**。
＝ **定数から引いているかを当てるなら、門そのものを動かして当てること**（`monkeypatch`）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402


def test_この回に実際に踏んだ組_2つが重なる点():
    """`used` 83.57 / 残り 17.92時間 / 遅れ 1.75分 で撃った数。"""
    v = quota.short_verdict(99.44, 99.41, seg_hours=19.23, left_hours=17.92)
    assert v["short"] is True
    assert v["side"] == "floor" and v["agree"] is True
    w = quota.short_words(99.44, 99.41, 19.23, 17.92)
    assert "引かれました" in w and "床に従えば" in w


def test_読む側は床_間隔の側が門の下でも引く():
    """`per_lap` が落ちた後の形（床 99.7 / 間隔 93.4）。**側を決めた効きはここに出る。**"""
    v = quota.short_verdict(99.67, 93.35, seg_hours=19.23, left_hours=17.92)
    assert v["short"] is True and v["side"] == "floor"
    assert v["agree"] is False
    assert "もう一方の側は逆の答え" in quota.short_words(99.67, 93.35, 19.23, 17.92)


def test_床の側が門の下なら引かない():
    v = quota.short_verdict(97.22, 87.76, seg_hours=19.23, left_hours=17.92)
    assert v["short"] is False
    assert "短く終わらないこと" in quota.short_words(97.22, 87.76, 19.23, 17.92)


def test_門の数は定数から引く(monkeypatch):
    """**門を関数の中へ焼き込まないこと**（2か所に持たない・`SHORT_LANDING_GATE` の註）。

    **門を動かして当てます** —— いまの数（98）でだけ当てると、
    関数の中へ 98 を焼き込んだ版と見分けが付きません（この回に 1度 踏んだ陽性対照）。
    """
    gate = quota.SHORT_LANDING_GATE
    assert quota.short_verdict(gate + 0.01, None)["short"] is True
    assert quota.short_verdict(gate, None)["short"] is False
    monkeypatch.setattr(quota, "SHORT_LANDING_GATE", 95.0)
    assert quota.short_verdict(96.0, None)["short"] is True
    assert quota.short_verdict(94.0, None)["short"] is False
    assert "門 95%" in quota.short_words(96.0, None)


def test_窓が残りより長い回だけ_間隔の側で読むなと言う():
    """**この枠のうちに効きを映せない**ことの印（`blind`）。"""
    blind = quota.short_verdict(99.44, 99.41, seg_hours=19.23, left_hours=17.92)
    assert blind["blind"] is True
    assert "「いまの間隔のまま」では読まないこと" in quota.short_words(99.44, 99.41, 19.23, 17.92)

    seen = quota.short_verdict(99.44, 99.41, seg_hours=6.0, left_hours=17.92)
    assert seen["blind"] is False
    assert "「いまの間隔のまま」では読まないこと" not in quota.short_words(99.44, 99.41, 6.0, 17.92)

    unknown = quota.short_verdict(99.44, 99.41)
    assert unknown["blind"] is None


def test_着地が読めない回は当てない():
    v = quota.short_verdict(None, None)
    assert v["short"] is None and v["side"] is None
    assert "着地が読めません" in quota.short_words(None, None)


def test_pace_report_が_short_words_を通る():
    """**印字は `short_words` の 1か所から出すこと**（手で引き比べる行を残さない）。"""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "quota.py").read_text(encoding="utf-8")
    body = src.split("def pace_report", 1)[1]
    assert "short_words(" in body
