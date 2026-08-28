"""**隣り合う表が「枠も行数も同じで、本文まで似ている」ものを、台本の時点で捕まえる。**

（2026-08-29 に足した）

## なぜ要るか（実測）

同じ日に `config/hypotheses.yaml` の前提を1件 判定しました ——
「長尺の生成が落ちる主因は『過去の図と重なっています』の門」は **外れ**（3/6 ＝ 50%）。
その3件は**全部 08-24 の同じ回**で、そこで止まっています。
**08-25 以降の主因は入れ替わっており**、3件中2件（67%）が

    VerificationError: 隣り合う図解が**見た目には変わっていない**箇所が 1件
    （21枚中。いちばん小さい差は画面の 0.6%）

でした。落ちた組を開くと、**どちらも表**です:

    6枚目  亡くなった日 / 未支給の月数 / 未支給年金の額
           1日 3か月 450000円 ／ 10日 3か月 450000円 ／ 13日… ／ 14日…
    7枚目  亡くなった日 / 未支給の月数 / 未支給年金の額
           15日 1か月 150000円 ／ 16日… ／ 20日… ／ 28日…

**見出しは違い、数字も違いますが、絵はほぼ同じです**（128px の灰色で 0.60%）。
`_check_adjacent_repeat` は**見出しの一致**と**chart の棒の包含**しか見ておらず、
**表は素通り**でした。

**そして、この指摘は書き直しで直ります。**（列を変える／2枚を1枚にまとめる）
`_check_slides` で落ちると `claude -p`・音声合成・全コマのレンダリングを
まるごと捨てます（実測 200〜590秒）。`script_writer.long_script_problems` が
`_check_adjacent_repeat` を呼んでいるので、**ここへ足せば同じセッションが
3回まで直せます** —— `_check_not_repeat` を 2026-08-24 にそこへ移したのと同じ形です。

## しきい値をどう置いたか（**当たりは n=1 です。隠しません**）

`data/critique_queue/*.plan.json`（公開ずみ 540本）に当てた実測:

    隣り合う table で見出し行が同一          924組  ← 段階表示。**当てない**
      そのうち行数も同じ                      18組
        本文の一致率が 70% 以上                0組   ← **誤報 0/540**
    この回に落ちた1組                                **73.8%**

公開ずみ側の最大は 60.8%。あいだは 13ポイント 空いています。

**覆る条件はしきい値の註（`src/verify.SAME_TABLE_TEXT_RATIO`）に書いてあります。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import verify  # noqa: E402

HEADERS = ["亡くなった日", "未支給の月数", "未支給年金の額"]


def _script(*visuals: dict) -> dict:
    return {"segments": [{"narration": "…", "visual": v} for v in visuals]}


def _table(headline: str, rows: list[list[str]]) -> dict:
    return {"kind": "table", "headline": headline, "headers": HEADERS, "rows": rows}


UPPER = [["1日", "3か月", "450000円"], ["10日", "3か月", "450000円"],
         ["13日", "3か月", "450000円"], ["14日", "3か月", "450000円"]]
LOWER = [["15日", "1か月", "150000円"], ["16日", "1か月", "150000円"],
         ["20日", "1か月", "150000円"], ["28日", "1か月", "150000円"]]


def test_実物で落ちた組が台本の時点で捕まる():
    """**この2枚が、レンダリング後まで生き延びていました。**（`mishikyu-hi-betsu-sanbai`）"""
    out = verify._check_adjacent_repeat(
        _script(_table("上の段はすべて450000円", UPPER),
                _table("下の段はすべて150000円", LOWER)))
    assert len(out) == 1, out
    assert "見出し行" in out[0] and "行数" in out[0]
    assert "4行" in out[0]
    # **直し方を1行で言うこと**（書き直しの輪へそのまま渡ります）
    assert "列そのもの" in out[0] or "1枚の表にまとめて" in out[0]


def test_段階表示は捕まえない():
    """**行が1つずつ増える組は、実測 924組 中 906組。**ここを当てると全部 落ちます。"""
    out = verify._check_adjacent_repeat(
        _script(_table("まず2行", UPPER[:2]), _table("3行目を足す", UPPER[:3])))
    assert out == [], out


def test_見出し行が違えば捕まえない():
    a = _table("A", UPPER)
    b = {"kind": "table", "headline": "B",
         "headers": ["月", "額"], "rows": [["1月", "1円"], ["2月", "2円"],
                                          ["3月", "3円"], ["4月", "4円"]]}
    assert verify._check_adjacent_repeat(_script(a, b)) == []


def test_中身が十分ちがえば捕まえない():
    """**枠が同じでも、本文が入れ替わっていれば別の絵です。**

    公開ずみ 540本 の 18組（枠も行数も同じ）は、全部この側で通っています
    （本文の一致率の最大 60.8%）。
    """
    other = [["東京都", "13.9%", "2,300円"], ["大阪府", "8.8%", "1,200円"],
             ["北海道", "0.4%", "980円"], ["沖縄県", "0.1%", "310円"]]
    out = verify._check_adjacent_repeat(_script(_table("A", UPPER), _table("B", other)))
    assert out == [], out


def test_表が空なら捕まえない():
    """行の無い表で `ratio` を測らないこと（`difflib` に空を渡すと 0 か 1 に化けます）。"""
    empty = {"kind": "table", "headline": "A", "headers": HEADERS, "rows": []}
    assert verify._check_adjacent_repeat(_script(empty, dict(empty, headline="B"))) == []


def test_chartとtableが隣り合っても捕まえない():
    chart = {"kind": "chart", "headline": "A", "bars": [{"display": "1円"}]}
    assert verify._check_adjacent_repeat(_script(chart, _table("B", UPPER))) == []


def test_公開ずみの控えで誤報が出ない():
    """**この検査そのものが効くことの検査**（`docs/trigger_main.md` §4）。

    足した門は、当たりを1件も含まないまま緑で通ります。
    **実物 540本に当てて 0件**であることを、ここで固定します。
    数が動いても落ちない形にしてあります（見るのは件数ではなく **0 かどうか**）。
    """
    import json

    hits = []
    for p in sorted((ROOT / "data" / "critique_queue").glob("*.plan.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        frames = doc if isinstance(doc, list) else (doc.get("slides") or [])
        if not isinstance(frames, list):
            continue
        script = {"segments": [{"visual": f} for f in frames if isinstance(f, dict)]}
        for problem in verify._check_adjacent_repeat(script):
            if "見出し行" in problem:
                hits.append((p.stem, problem))
    assert not hits, (
        f"公開ずみの控えに誤報が {len(hits)}件 出ました。**しきい値を上げるのではなく、"
        f"当たりの側をもう一度 測ること**（`src/verify.SAME_TABLE_TEXT_RATIO` の覆る条件）:"
        f"\n  " + "\n  ".join(f"{n}: {p[:120]}" for n, p in hits[:5]))
