"""**画面に置いた登録の依頼が、本文に1pxも掛かっていないこと。**

## なぜ要るか（2026-09-03・最適化の回）

`scripts/eta.py` は毎周こう印字します ——「最初に落ちる門は 門1'（登録者500人）で
**532日後**。その門を動かす腕は `views/day × sub_rate` の2本」「`sub_rate` を天井まで
引くと **81日**（`per_video` の 119日 より大きい）」、そして
「直近7日の ship: `per_video` **115件** ／ `sub_rate` **7件**」。

依頼はいままで **`src/script_writer.py` の最後のセグメントの音声1文だけ**でした
＝ **最後まで見た人にしか届きません**（実測の維持率 12〜53%）。
画面（`src/visuals.py` の `.subs-badge`）は全時間 出るので、届く先が増えます。

**この検査が見ているのは「効くか」ではなく「壊していないか」です。**
札は `body` の `padding-top` の中に置いてあり、そこは構造上どのコマも空です。
**その約束が崩れたら（padding-top を縮めた・札を大きくした）、ここが落ちます。**

**覆る条件**: 置き場所を padding の外へ動かすなら、この検査ごと書き直すこと
（そのときは「重ならない」ではなく「何を押しのけたか」を測る検査になります）。
"""
from __future__ import annotations

import pytest

from src import ab_split, visuals

VISUAL = {
    "kind": "stat",
    "headline": "年金の受け取り方を65歳と70歳と75歳で比べて損益分岐を出す",
    "stat": "月12万4500円",
    "note": "2026年4月改正の条件で計算した結果です",
}

#: 札と、本文の各要素の**矩形**を返す。重なりは矩形どうしで見る
#: （「たぶん空いている」ではなく、**ブラウザに数えさせる**）。
PROBE = """() => {
  const b = document.querySelector('.subs-badge');
  if (!b) return {badge: null};
  const r = b.getBoundingClientRect();
  const hits = [];
  for (const sel of ['.headline', '.body', '.formula']) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const q = el.getBoundingClientRect();
    const over = !(r.right <= q.left || r.left >= q.right
                   || r.bottom <= q.top || r.top >= q.bottom);
    if (over) hits.push(sel);
  }
  return {top: r.top, bottom: r.bottom, left: r.left, right: r.right,
          hits: hits, text: b.textContent,
          inView: r.top >= 0 && r.left >= 0
                  && r.right <= innerWidth && r.bottom <= innerHeight};
}"""


def test_振り分けは同じIDなら何度でも同じ側():
    """焼き直しで群が移ると比較が壊れます（`slot_half` と同じ約束）。"""
    for tid in ("a", "zaishoku-2026-62man", "s-shokibo-11-12kagetsu-59man"):
        assert ab_split.subs_badge(tid) == ab_split.subs_badge(tid)
        assert ab_split.subs_badge(tid) in ("画面あり", "画面なし")


def test_割合を0や1にすると振り分けが止まる():
    assert ab_split.subs_badge("a", share=0) == "画面なし"
    assert ab_split.subs_badge("a", share=1) == "画面あり"


def test_両群に本が入る():
    """**塩が効いていること。** 片側に全部 落ちたら A/B になりません。"""
    labels = [ab_split.subs_badge(f"topic-{i}") for i in range(200)]
    assert 60 <= labels.count("画面あり") <= 140, labels.count("画面あり")


def test_EXPERIMENTS_に登録されている():
    """足し忘れると `status.py` が群を突き合わせないまま外れを出します。"""
    exp = ab_split.EXPERIMENTS["subs_badge"]
    assert exp.side == "dist"
    assert exp.metric == "登録"
    assert {exp.treated, exp.control} == {"画面あり", "画面なし"}


def test_台帳にこの実験を名指しした前提が開いている():
    """**前提の無い A/B は、判定されずに走り続けます。**"""
    import yaml

    doc = yaml.safe_load(
        (ab_split.ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    hit = [h for h in doc["hypotheses"]
           if "ab_split.subs_badge" in str(h.get("falsified_if", ""))
           and not any(k in h for k in ("verdict", "closed_on", "outcome"))]
    assert len(hit) == 1, [h.get("claim") for h in hit]
    assert hit[0]["lever"] == "sub_rate"
    assert hit[0]["side"] == "dist"


def test_札の文言に登録の語が入っている():
    """`endcard_verdict.is_request()` と同じ語で処置群を作ります。"""
    assert "登録" in visuals.SUBS_BADGE_TEXT


def test_札を出さないときは画面が1文字も変わらない():
    off = visuals.build_html(VISUAL, None, False, 0, 1.0, False)
    # CSS の規則は常に在る（配色は差し込みで作る）。**要素のほうを見ること。**
    assert '<div class="subs-badge">' not in off
    # 既定（引数なし）も「出さない」側であること。
    assert visuals.build_html(VISUAL, None, False, 0, 1.0) == off


@pytest.mark.parametrize("portrait", [False, True])
def test_札は本文に1pxも重ならない(portrait):
    """**ブラウザに矩形を数えさせる**（目視は取りこぼすし、無いものを作る）。"""
    pw = pytest.importorskip("playwright.sync_api")

    size = visuals.VIEWPORT_PORTRAIT if portrait else visuals.VIEWPORT
    with pw.sync_playwright() as p:
        br = p.chromium.launch(executable_path=visuals._chromium_path(),
                               args=["--font-render-hinting=none"])
        pg = br.new_page(viewport={"width": size[0], "height": size[1]},
                         device_scale_factor=visuals.SCALE)
        pg.set_content(visuals.build_html(VISUAL, None, portrait, 0, 1.0, True),
                       wait_until="load")
        got = pg.evaluate(PROBE)
        bad_on = pg.evaluate(visuals._LINE_PROBE_JS)
        pg.set_content(visuals.build_html(VISUAL, None, portrait, 0, 1.0, False),
                       wait_until="load")
        bad_off = pg.evaluate(visuals._LINE_PROBE_JS)
        br.close()

    assert got.get("badge", "present") is not None, "札そのものが焼かれていません"
    assert got.get("hits") == [], got
    assert got["inView"], got
    assert visuals.SUBS_BADGE_TEXT in got["text"]
    # **折り返しの検査が、札の有無で変わらないこと。**
    # 変わったら、札が版面を押している（＝ padding の外へ出ている）。
    assert bad_on == bad_off, (bad_on, bad_off)
