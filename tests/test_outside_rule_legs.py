"""`OUTSIDE_LONG_RULE` の本文と、それを数える口の対応が抜けていないかを見る。

## なぜ要るか（2026-09-04 16:3x に足した）

この規則の脚を数える口は、**5回に分けて**入りました（`src/script_writer.OUTSIDE_RULE_LEGS`
の註に日付つきの一覧）。毎回、本文を読み直した回が**数え落とされた節を1つ**見つけています。
5回目は (2)「章ごとに判断を1つ置く」——「章を5〜7つ。」と**同じ行**に在ったので、
行を眺めるやり方では見つかりませんでした。

しかも4回目の回は「**規則の脚は、これで全部 数えた側に入りました**」とコードに書き残し、
その文のせいで次の回は本文を読み直しません。**穴ではなく、穴を作っている側を塞ぐ**ための検査です。

**この検査が赤になったときの直し方は2つだけ**:

  1. その節を数える口を足して、`OUTSIDE_RULE_LEGS` にその関数名を書く
  2. 数えないと決めて、`OUTSIDE_LEG_NOT_COUNTED + "<なぜ>"` を書く（**理由は必須**）

**表から見出しを消して赤を消さないこと。** そのときは 2. を使うこと。

**覆る条件**: 前提「外の作り方を写した長尺」が外れたら（48h で 100回 未満）、
`OUTSIDE_LONG_RULE` ごと使わないので、この検査も一緒に落とすこと
（`config/hypotheses.yaml` の `next_if_false`）。
"""
from src import script_writer as sw


def test_規則の節はすべて数える口か理由に結び付いている():
    missing = sw.outside_rule_uncounted()
    assert not missing, (
        "`OUTSIDE_LONG_RULE` に、どの口にも結び付いていない節があります。\n"
        + "\n".join(f"  ・{u}" for u, _ in missing)
        + "\n数える口を足して `OUTSIDE_RULE_LEGS` に書くか、"
          f"`{sw.OUTSIDE_LEG_NOT_COUNTED}<なぜ>` を書くこと。")


def test_表の見出しはすべて規則の本文に在る():
    """本文から消えた節の見出しが表に残っていると、**当たらない見出し**が
    「結び付いている」の数を水増しします（本文を書き換えた回が踏む形）。"""
    stale = [k for k, _ in sw.OUTSIDE_RULE_LEGS if k not in sw.OUTSIDE_LONG_RULE]
    assert not stale, f"`OUTSIDE_RULE_LEGS` の見出しが本文に在りません: {stale}"


def test_数えないと決めた節には理由が書いてある():
    bare = [k for k, v in sw.OUTSIDE_RULE_LEGS
            if v.startswith(sw.OUTSIDE_LEG_NOT_COUNTED)
            and len(v) <= len(sw.OUTSIDE_LEG_NOT_COUNTED) + 4]
    assert not bare, f"数えないと決めた節に理由がありません: {bare}"


def test_章ごとの判断を数える口が在る():
    """5回目の数え落とし (2d) そのもの。**判断の無い章は落ちる。**

    見るのは**章の見出し＋その章の narration** です（実物 `nenkin-…` の章
    「額面か手取りか」は、見出しの `か` ではなく本文の「どちらで見るか」で通ります ——
    `か` 1文字を判断の語にすると、ほとんどの文が当たります）。
    """
    #: 章ごとの narration。**「線の動き方の説明だけ」の章が1つ**（実物 `zaishoku` と同じ形）。
    text = {
        "冒頭": "きょうの結論です。",
        "線の位置": "年金が多い人ほど、線は左にあります。帯の広さは変わりません。",
        "額面か手取りか": "額面で見るか手取りで見るかを、ここで決めます。",
        "何歳までと置くか": "何歳まで生きると置くかで、答えは変わります。",
        "一か月待つ値段": "あと一か月 待つべきかどうかを、ここで決めます。",
        "締め": "自分の場合の数字を出す手順は三つです。順に見ます。",
    }
    labels = list(text)
    segs = []
    for lab in labels:
        for i in range(5):
            segs.append({"narration": text[lab] if i == 0 else "です。",
                         "visual": {"kind": "chart", "headline": f"{lab}表{i}"}})
    script = {"segments": segs,
              "chapters": [{"segment_index": i * 5, "label": lab} for i, lab in enumerate(labels)]}
    problems = sw.outside_body_problems(script)
    assert any("章「線の位置」に判断が1つも無い" in p for p in problems), problems
    # 判断の語が在る章は鳴らない（`べきか` / `かどうか` / `決めます` も判断の語）。
    for lab in ("額面か手取りか", "何歳までと置くか", "一か月待つ値段"):
        assert not any(f"章「{lab}」に判断" in p for p in problems), (lab, problems)
    # 冒頭の章と締めの章は、この脚の持ち場ではありません。
    for lab in ("冒頭", "締め"):
        assert not any(f"章「{lab}」に判断" in p for p in problems), (lab, problems)


def test_べきか_も判断の語として数える():
    """実測 2026-09-04: `zaishoku-2026-62man` の章「月給を抑えるか・4人の例」は
    「次の判断は、月給を抑えるべきかです」と言っており、**サムネむけの
    `_OUTSIDE_DECIDE_RE`（どれ／どちら／選ぶ…）では落ちます。**"""
    assert sw._OUTSIDE_CHAPTER_DECIDE_RE.search("次の判断は、月給を抑えるべきかです")
    assert sw._OUTSIDE_CHAPTER_DECIDE_RE.search("抑える意味があるかどうかは、その範囲のどこにいるかで決まります")
    assert not sw._OUTSIDE_CHAPTER_DECIDE_RE.search("年金が多い人ほど、線は左にあります")


def test_表が書いた脚の番号は_その口が本当に数えている番号か():
    """**番号のずれを見る。** 2026-09-04 20:4x に実物で踏んで足しました。

    それまで表はこう書いていました::

        ("最後に判断の語", "outside_title_problems (4b)")
        ("全角45文字以内", "outside_title_problems (4c)")

    ところが `outside_title_problems` が数えている番号は
    **(4b) 題の長さ ／ (4c) サムネの金額** です ——
    **表の2行は、別の物を数える口を指していました。**

    上の `test_規則の節はすべて数える口か理由に結び付いている` は
    「**どこかの口**に結び付いているか」しか見ないので、**番号が違っても緑**でした。
    実際、題の金額も題の末尾の判断の語も、**どちらも門になっていません**でした
    （`outside_title_problems({'title': '【緊急解説】まったく数字のない題です'}) == []`）。

    ＝ この検査は「数え落とし」ではなく「**数えていると名乗る所**」を見ます。
    上の module docstring の「穴ではなく、穴を作っている側を塞ぐ」の、番号の側です。

    **赤になったときの直し方**（表から番号を消して緑にしないこと）:

      1. その番号を、その口の docstring の「何を数えるか」に足す（＝ 実際に数える）
      2. 表の番号を、その口が本当に数えている番号へ直す
      3. 数えないと決めたなら `OUTSIDE_LEG_NOT_COUNTED + "<なぜ>"` へ（**理由は必須**）
    """
    import inspect
    import re
    ずれ = []
    for 節, 値 in sw.OUTSIDE_RULE_LEGS:
        if 値.startswith(sw.OUTSIDE_LEG_NOT_COUNTED):
            continue
        口 = re.findall(r"(outside_\w+_problems)", 値)
        番号 = re.findall(r"\((\d[a-z0-9]*)\)", 値)
        if not 口 or not 番号:
            continue                      # 番号を持たない脚（冒頭の a〜e）はここでは見ない
        fn = getattr(sw, 口[0], None)
        doc = inspect.getdoc(fn) or ""
        for n in 番号:
            if f"({n})" not in doc:
                ずれ.append((節, 口[0], n))
    assert not ずれ, (
        "`OUTSIDE_RULE_LEGS` の番号が、その口が数えている番号に在りません:\n"
        + "\n".join(f"  ・「{k}」→ {f} の ({n})" for k, f, n in ずれ)
        + "\n表の番号を直すか、その番号を実際に数えて docstring に足すこと。"
          "**表から番号を消して緑にしないこと。**")
