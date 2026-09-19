"""`studio/series_sousaihi.py` の検査（2026-09-20 03:xx・optimizer・Opus 5・ultracode）。

**なぜ足したか**: この連作の数は **全部 外の一次資料の写し**で、`figures()` のような
計算がありません（`series_kakyu` は 423,700 × 年数 を assert で照らせる）。
**計算が無い連作は、数がずれても道具の側からは静かです** —— だから
**「どの数が、どの出どころの、どの字から来たか」をここで押さえます。**

**この検査が守っているのは 3つ**:
 (1) 額の定数（5万円・7万円）が、`docs` と 説明欄 と 表 で同じであること
 (2) **声に「額」と「行」が 1字 も無いこと**（`lint` の門と同じ ——
     「額」は TTS が「ひたい」と読み、「行」は「い／おこな」で割れる。
     **門は `lint` に在りますが、`lint` は本ごとに撃つ手**で、
     連作を書き足した回が撃ち忘れると静かに通ります）
 (3) **6本 が 6通り を過不足なく覆い、表の光る行が その本の行であること**
"""
from __future__ import annotations

import re

import pytest

from studio import series_sousaihi as ss

ALL = [fn() for fn in ss.ALL]


def test_六本ある():
    assert len(ALL) == 6
    assert len({d["id"] for d in ALL}) == 6
    assert len(ss.SLOTS) == 6


def test_額は一次資料の数のまま():
    # 協会けんぽ「埋葬料・埋葬費」＝ 埋葬料・家族埋葬料 5万円／埋葬費は5万円の範囲内の実費
    assert ss.MAISOU == 50_000
    # 港区「国民健康保険に加入していた人の葬祭費の手続き」＝ 7万円
    assert ss.MINATO == 70_000
    # 横浜市「葬祭費の支給」＝ 5万円
    assert ss.YOKOHAMA == 50_000
    # 東京都後期高齢者医療広域連合「葬祭費」＝ 7万円（広域連合5万円＋区市町村2万円）
    assert ss.TOKYO_KOUKI == 70_000
    assert ss.TOKYO_KOUKI - 20_000 == 50_000, "広域連合ぶんは 5万円（区市町村の2万円を引いた残り）"
    # 時効は 6本 で同じ（起算日だけが違う）
    assert ss.NENGEN == 2


def test_man_の字():
    assert ss.man(50_000) == "5万円"
    assert ss.man(70_000) == "7万円"
    assert ss.man(423_700) == "42万3700円"


def test_連作の表は六行で表の額は定数から出ている():
    assert len(ss.TABLE_ROWS) == 6
    assert [r[1] for r in ss.TABLE_ROWS][2:5] == [ss.man(ss.MAISOU)] * 3
    for row in ss.TABLE_ROWS:
        assert len(row) == 2
        for cell in row:
            assert len(cell) <= 12, f"表のマスは 12字 まで（`viz.MAX_CELL`）: {cell}"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_光る行はその本の行(d):
    """**6本 で同じ 6行**なので、既定（最後の行）だと
    見ている人が自分の行を目で探すことになります。"""
    seg = d["segments"][4]                       # コマ5 ＝ 連作の表
    assert seg["viz"]["rows"] == ss.TABLE_ROWS
    assert 0 <= seg["viz"]["hi"] < 6


def test_六本が六通りを過不足なく覆う():
    his = sorted(d["segments"][4]["viz"]["hi"] for d in ALL)
    assert his == [0, 1, 2, 3, 4, 5], "1本 1行。だぶりも抜けも無いこと"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_声に額と行が無い(d):
    """`lint` の門と同じもの。**連作を書き足した回が `lint` を撃ち忘れても、ここで止まります。**

    「額」＝ TTS が「ひたい」と読む（実測 09/06・09/15）→ 声では「金額」か「いくら出るか」。
    **止めるのは裸の「額」だけです** ——「金額」は `lint` 自身が挙げている逃げ道で、
    「きんがく」としか読めません（**ここを裸の `"額" not in` で書くと、
    正しい逃げ道まで落ちます。2026-09-20 03:xx に 1度 そう書いて 6本 とも落ちた**）。
    「行」＝ 「行きます」（い）と「行った」（おこな）が同じ本に出る → 声では「した」。
    画面（`show`/`board`/`viz`）と説明欄は、法令どおりの字のままでよい。
    """
    for i, s in enumerate(d["segments"]):
        assert not re.search(r"(?<!金)額", s["say"]), f"コマ{i + 1} の声に裸の「額」: {s['say']}"
        assert "行" not in s["say"], f"コマ{i + 1} の声に「行」: {s['say']}"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_声に小数と点が無い(d):
    for s in d["segments"]:
        assert "点" not in s["say"]
        assert not re.search(r"[0-9０-９]\.[0-9０-９]", s["say"])


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_札は決められた六つのどれか(d):
    ok = {"", "前提", "しくみ", "決まり", "計算", "結論", "見る所"}
    for i, s in enumerate(d["segments"]):
        assert s.get("tag", "") in ok, f"コマ{i + 1} の札「{s.get('tag')}」"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_字だけのコマが無い(d):
    """オーナー `9155fe09`「画面がある意味が文字だけになってんのどうにかしろよ」。
    CTA（最後の 1コマ）は `asp.CTA_SEG` が持つので、この検査の外。"""
    for i, s in enumerate(d["segments"][:-1]):
        assert s.get("viz"), f"コマ{i + 1} に viz が無い"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_時効は声でお金を名指しする(d):
    """`crosscheck` [missing_cond]（2026-09-20 03:xx）——
    コマ7 が「葬祭費も埋葬料も」と 2つ を並べるので、コマ8 が
    お金を名指ししないと、起算日が両方に掛かって聞こえます
    （葬祭費は「葬祭をした日の翌日」・埋葬料は「亡くなった日の翌日」）。"""
    say = d["segments"][7]["say"]
    assert f"{ss.NENGEN}年" in say
    monies = {"葬祭費", "家族埋葬料", "埋葬料", "埋葬費"}
    assert any(m in say for m in monies), say


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_申請できる人を家族に狭めていない(d):
    """`crosscheck` [sharper]（2026-09-20 03:xx）——
    健康保険法100条の要件は「**生計を維持されていた者**で埋葬を行う人」で、
    親族であることは要りません。**声が「家族」と言うと、当たる人が自分を外します。**
    `maisouryou-kazoku`（家族埋葬料）だけは、制度の名前そのものに「家族」が入ります。
    """
    if "kazoku" in d["id"]:
        return
    assert "家族" not in d["segments"][2]["say"], d["segments"][2]["say"]


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_説明欄に出どころが六件そろっている(d):
    for url in ("kyoukaikenpo.or.jp/benefit/burial_charges",
                "kyoukaikenpo.or.jp/faq/benefit/008",
                "tokyo-ikiiki.net",
                "city.minato.tokyo.jp",
                "city.yokohama.lg.jp",
                "nenkin.go.jp"):
        assert url in d["description"], f"{d['id']} の説明欄に {url} が無い"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_説明欄の額は定数から出ている(d):
    assert f"{ss.MAISOU:,}円" in d["description"]
    assert f"{ss.MINATO:,}円" in d["description"]
    assert f"{ss.YOKOHAMA:,}円" in d["description"]
    assert f"{ss.TOKYO_KOUKI:,}円" in d["description"]


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_死亡一時金は説明欄にだけ在る(d):
    """軸にしなかった理由（老齢基礎年金を受けた人の遺族には出ない）は冒頭の註。
    **出どころは持っているので、説明欄には置きます。**"""
    assert "死亡一時金" in d["description"]
    assert "120,000円" in d["description"] and "320,000円" in d["description"]
    assert "8,500円" in d["description"]
    for s in d["segments"]:
        assert "死亡一時金" not in s["say"], "声には入れない（当たる人がいない）"


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_CTAは門を通っている(d):
    """**門は 1か所**（`studio/asp.py` の `CTA_SEG`）。写しを持たないこと。"""
    from studio import asp
    assert d["segments"][-1]["say"] == asp.CTA_SEG["say"]


@pytest.mark.parametrize("d", ALL, ids=[d["id"] for d in ALL])
def test_形と日付(d):
    assert d["form"] == "short"
    assert d["date"] == ss.DATE == "2026-09-24"
    assert d["id"].startswith(ss.DATE)
    assert d["title"].endswith("#Shorts")
    assert len(d["segments"]) == 10
