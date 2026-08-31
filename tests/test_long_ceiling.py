"""**長尺の天井の判定**（`src/long_ceiling.py`）が、仮説と同じ数を見ていること。

## なぜ要るか（2026-08-31 に作り、2026-09-01 に判定の形ごと直した）

`config/hypotheses.yaml` の `長尺1本あたり-13本` は **門 80回** で判定します。
この前提が `scripts/eta.py` の言う「**未測定の1つ**」——
月20万に届く帯は「長尺がショート並みに伸びた側」だけなので、
**この1件が、目標に届く道が在るかどうかを決めています。**

## **2026-09-01 に直したこと**（前の版は永久に閉じませんでした）

    前: 齢 24〜72時間 の読みが 30本以上 そろったうえで、中央値が 80回 に届かないなら外れ
    後: 齢 96時間 以上 の読みが 13本以上 そろったうえで、80回超が 3本以下 なら外れ

**(1) 30本 は窓に入りません** —— 判定は直近28日、規則は1日1本、窓の上限は **28本**。
**30 > 28** なので待っても入れ替わっても満ちない。しかも `falsified_if` が
「満たなければ**期限だけ延ばすこと**」と書いており、`house_rule.needs_beyond_rule()`
は**期日で解く**ので延ばすと黙る —— **指示と検査が同じ向きに壊れていました。**

**(2) 齢 24〜72時間 は熟れる前です** —— `settle.mature_hours('長尺')` は **96時間**。
実測 2026-09-01: 24〜72時間 で中央値 **1回**、96時間 以上で **4回**（**×4**）。

**(3) 13本 で足ります** —— 符号検定。「中央値が 80回」が真なら門超えは p=0.5 なので、
n=13 で 3本以下 なら p=0.046 で棄却。**門（80回）は1文字も緩めていません。**

## ここで固定するもの

1. **符号検定が正しいこと**（`ABOVE_MAX` が `sign_reject_at(N_TARGET)` と一致）
2. **`N_TARGET` が窓に入ること**（`N_TARGET` ≤ 28日 × `PUBLISH_PER_DAY`）
   —— **ここが前の版で壊れていました。この検査が再発を止めます**
3. 標本が足りなければ **判定しない**こと
4. 熟れの齢を `src/settle.py` から引くこと（**写さない**）
5. **門（80）と本数（13）が仮説の本文と同じ**であること（2か所にあるので）

## 覆る条件

- `falsified_if` の門が 80回 から動いたら `MEDIAN_GATE` を合わせること
- オーナーが規則を外したら（`PUBLISH_PER_DAY` が上がる）、2番の上限が上がるので
  `N_TARGET` を上げ直してよい
"""
from __future__ import annotations

from pathlib import Path

from src import house_rule
from src import long_ceiling as lc

ROOT = Path(__file__).resolve().parent.parent

#: 実測 2026-09-01（齢 96時間 以上・`reach_split.long_ids()`・昇順）。
MATURE = [1, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 4, 7, 8, 8, 16, 54, 121, 156]


# --- 符号検定 ---------------------------------------------------------------

def test_符号検定の確率():
    """全部が門の下なら (1/2)^n。**手で確かめられる所を1つ置く。**"""
    assert lc.sign_p(13, 13) == 1.0
    assert abs(lc.sign_p(13, 0) - 1 / 8192) < 1e-12
    assert abs(lc.sign_p(13, 3) - 378 / 8192) < 1e-12


def test_棄却域は事前に決まる():
    """n=13 なら 3本以下（p=0.046）。**標本を見てから選ぶものではありません。**"""
    assert lc.sign_reject_at(13) == 3
    assert lc.sign_p(13, 3) < 0.05
    assert lc.sign_p(13, 4) >= 0.05


def test_小さすぎる標本では棄却できない():
    """n=4 では、全部が門の下でも p=1/16 で 0.05 を切りません。"""
    assert lc.sign_reject_at(4) is None


def test_ABOVE_MAX_は検定から出た数と一致する():
    """**写した数が、計算した数とずれていないこと。**"""
    assert lc.ABOVE_MAX == lc.sign_reject_at(lc.N_TARGET)


# --- **2番。前の版が壊れていた所** ------------------------------------------

def test_必要な本数は窓に入る():
    """**`N_TARGET` は、規則の下で窓に入る本数を超えてはいけません。**

    前の版は 30本 で、窓（28日 × 1本/日 ＝ 28本）に入りませんでした。
    **満たせない条件を反証条件にしてはいけない** —— この検査が再発を止めます。
    """
    cap = lc.WINDOW_DAYS * house_rule.PUBLISH_PER_DAY
    assert lc.N_TARGET <= cap, (
        f"`N_TARGET`={lc.N_TARGET} は窓（{lc.WINDOW_DAYS}日 × "
        f"{house_rule.PUBLISH_PER_DAY}本/日 ＝ {cap}本）に入りません。**永久に閉じません。**")


def test_仮説の側も窓に入る():
    """同じことを、**仮説の本文の側**でも見ます（`house_rule` の門を通して）。"""
    import yaml
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    hits = [h for h in house_rule.window_unreachable(doc.get("hypotheses") or [])
            if "長尺の1本あたり再生" in h["claim"]]
    assert hits == [], f"また窓に入らなくなっています: {hits}"


# --- 判定 -------------------------------------------------------------------

def test_足りない標本では判定しない():
    d = lc.verdict([1, 2, 3])
    assert d["decidable"] is False
    assert d["n"] == 3


def test_実測は外れと出る():
    """22本中 門超え 2本 → 棄却域に入るので `falsified`。"""
    d = lc.verdict(MATURE)
    assert d["decidable"] is True
    assert d["above"] == 2
    assert d["falsified"] is True
    assert d["p"] < 0.001


def test_門を超える本が半分なら外れない():
    """**逆向きも効くこと** —— 効き目があれば `survived` に出ること。"""
    v = [1, 2, 3, 4, 5, 6] + [200] * 7
    d = lc.verdict(v)
    assert d["decidable"] is True
    assert d["falsified"] is False


def test_中央値():
    assert lc.median([]) == 0.0
    assert lc.median([1, 2, 3]) == 2.0
    assert lc.median([1, 2, 3, 4]) == 2.5


# --- 熟れの齢 ---------------------------------------------------------------

def test_熟れの齢はsettleから引く():
    """**写さないこと。** `src/settle.py` が動いたら、ここも動くべきです。"""
    from src import settle
    assert lc.mature_hours() == int(settle.mature_hours("長尺"))


def test_熟れの齢の控えはショートより長い():
    """長尺はショート（48時間）より遅く熟れます。**控えがそれを下回らないこと。**"""
    from src import settle
    assert lc.MATURE_HOURS_FALLBACK > settle.mature_hours("ショート")


# --- 標本の読み方 -----------------------------------------------------------

def test_帯で切る(tmp_path):
    """**「以上」ではなく帯**。熟れる前の読みが混ざると ×4 ずれます。"""
    p = tmp_path / "views.jsonl"
    p.write_text(
        '{"id": "a", "hours": 30, "views": 1}\n'
        '{"id": "a", "hours": 120, "views": 50}\n'
        '{"id": "b", "hours": 40, "views": 2}\n', encoding="utf-8")
    assert lc.band_by_id(96, float("inf"), p) == {"a": 50.0}
    assert lc.band_by_id(24, 72, p) == {"a": 1.0, "b": 2.0}


def test_壊れた行は飛ばす(tmp_path):
    p = tmp_path / "views.jsonl"
    p.write_text('{"id": "a", "hours": 120, "views": 5}\nこわれた\n', encoding="utf-8")
    assert lc.band_by_id(96, float("inf"), p) == {"a": 5.0}


def test_ファイルが無くても止まらない(tmp_path):
    assert lc.band_by_id(96, float("inf"), tmp_path / "no.jsonl") == {}


# --- 2か所に書いてある数 ----------------------------------------------------

def test_門の数は仮説と同じ():
    """**2か所に書いてある数**。片方だけ動いたら、ここで落とします。"""
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert "長尺1本あたり-13本" in text
    i = text.index("長尺1本あたり-13本")
    section = text[i:i + 4000]
    assert f"{lc.MEDIAN_GATE}回 を超える本が {lc.ABOVE_MAX}本以下" in section, \
        "`falsified_if` の判定の形が動いています。`MEDIAN_GATE`/`ABOVE_MAX` を合わせること"
    assert f"need: {lc.N_TARGET}" in section, \
        "`needs` の本数が動いています。`N_TARGET` を合わせること"


def test_齢も仮説と同じ():
    """**熟れの齢も2か所にあります。**"""
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    i = text.index("長尺1本あたり-13本")
    section = text[i:i + 4000]
    assert f"齢 {lc.mature_hours()}時間 以上" in section


def test_印字に判定の数が出る():
    out = lc.report()
    assert str(lc.MEDIAN_GATE) in out
    assert "長尺1本あたり-13本" in out
