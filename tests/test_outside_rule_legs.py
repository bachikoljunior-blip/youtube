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


# ---------------------------------------------------------------------------
# **数える口が「これから焼く台本」だけを見て、控えを見ていないか**
# （2026-09-05 04:4x に足した。**上の2件が緑のまま、実物が素通りした**）
#
# 上の2件は「規則の本文 ↔ 数える口」の対応しか見ません。ところが口には**行き先が2つ**あります:
#
#     `script_writer.long_script_problems()`   ← **これから焼く台本**（`generate()` が3回まで書き直す）
#     `daily_pick.OUTSIDE_LEGS`（`pick_legs`） ← **もう実物に入っている台本の控え**
#                                                （＝ その本が「処置」かを決める側）
#
# `outside_length_problems` は 2026-09-05 03:5x に**前者にだけ**繋がりました。
# 上の2件は両方 緑のままで、実物はこうなっていました（04:1x に撃った・API 0単位）::
#
#     pick_legs('GFvAcxvDmYM') → ([], None)      ← 4脚 全通と返る
#     台本 7,699字 ＝ 22.8分・切れ目 25分 を **731字 割っている**
#
# その本は 09/05 09:00 に出て、前提「外の作り方を写した長尺」を 09/07 09:00 の齢48h で
# 閉じる本です。**帯でいちばん大きく効いている軸（尺・×2.6）だけを外した本で閉じると、
# 「外の作りを写しても効かない」という判定が、写していない軸のせいで出ます。**
#
# **赤になったときの直し方は2つだけ**（上と同じ形）:
#   1. `daily_pick.OUTSIDE_LEGS` にその口を足す
#   2. 控えでは数えられないと決めて、下の `KEIGAI_NOT_ON_QUEUE` に**理由つきで**書く

#: **控え（`data/critique_queue/<ID>.script.json`）だけでは数えられない口。理由は必須。**
KEIGAI_NOT_ON_QUEUE: dict[str, str] = {
    "_check_not_repeat": (
        "`verify._check_not_repeat(work, script)` は**焼いた作業ディレクトリ**（`work`）を要る。"
        "控えは script.json 1枚なので、この口は控えに当てられない。"
        "＝ 焼く側（`pipeline`）でだけ数える。**`script_writer` にも存在しない**ので、"
        "`OUTSIDE_LEGS` に書くと `legs_of_path` が「口が在りません」を返し続ける"),
}


def test_数える口は控えの側にも繋がっている():
    from src import daily_pick as dp

    counted = {fn.split(" ")[0] for _, fn in sw.OUTSIDE_RULE_LEGS
               if not fn.startswith(sw.OUTSIDE_LEG_NOT_COUNTED)}
    on_queue = {fn for _, fn in dp.OUTSIDE_LEGS}
    missing = sorted(counted - on_queue - set(KEIGAI_NOT_ON_QUEUE))
    assert not missing, (
        "規則を数える口が `daily_pick.OUTSIDE_LEGS` に繋がっていません: "
        + "・".join(missing)
        + "\n＝ **これから焼く台本は落ちるのに、もう実物に入っている台本は素通りします**"
          "（`pick_legs` が 全通 を返し、その本が「処置」を名乗れてしまう）。\n"
          "`OUTSIDE_LEGS` に足すか、`KEIGAI_NOT_ON_QUEUE` に**理由つきで**書くこと。")


def test_控えで数えない口の言い訳は理由を持っている():
    empty = [k for k, v in KEIGAI_NOT_ON_QUEUE.items() if not str(v).strip()]
    assert not empty, f"理由の無い言い訳が在ります: {empty}"


def test_控えの口はすべて控えの形_dict_を受ける():
    """**口が転んでも「通った」になっていた穴**（2026-09-05 04:2x に踏んだ）。

    `daily_pick.legs_of_path()` は控えを `json.loads` した **`dict`** を口に渡します。
    ところが `outside_length_problems` は `script.model_dump()` だけで読む
    **pydantic 専用**で、`dict` を渡すと毎回 `AttributeError`。
    当時の `legs_of_path` は `except Exception: continue` でそれを飲んでいたので、
    **この脚は静かに合格**になっていました。

    ここは「転ばないこと」だけを見ます（**合否は見ません** —— 中身の判定は別の検査）。
    """
    from src import daily_pick as dp
    from src import script_writer as _sw

    mihon = {"title": "【60歳以上の方へ】仮の題",
             "thumbnail_kicker": "仮", "thumbnail_line1": "仮", "thumbnail_line2": "仮",
             "segments": [{"narration": "これは見本の一文です。",
                           "visual": {"kind": "text", "headline": "見本"}}]}
    koronda: list[str] = []
    for label, fn in dp.OUTSIDE_LEGS:
        f = getattr(_sw, fn, None)
        if f is None:
            koronda.append(f"{label}: 口 `{fn}` が `src.script_writer` に在りません")
            continue
        try:
            f(mihon)
        except Exception as exc:                                   # noqa: BLE001
            koronda.append(f"{label}: `{fn}` が dict で転びました（{type(exc).__name__}: {exc}）")
    assert not koronda, (
        "控えの形（`dict`）で転ぶ口が在ります:\n" + "\n".join(f"  ・{t}" for t in koronda)
        + "\nほかの口と同じ両対応で書くこと")


def test_転んだ脚は通ったことにしない():
    """`legs_of_path` は、口が転んだら **`why` を返す**（`bad` を空で返して合格にしない）。

    前の版は `except Exception: continue` で、**転んだ脚は静かに合格**でした。
    `pick_legs` の docstring は「**読めないものを『通った』に数えません**」と書いてあり、
    書いてあってしていなかった所です。
    """
    import json
    import tempfile
    from pathlib import Path

    from src import daily_pick as dp
    from src import script_writer as _sw

    def korobu(script):
        raise RuntimeError("わざと転ぶ")

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.script.json"
        p.write_text(json.dumps({"segments": []}), encoding="utf-8")
        na = "_wazato_korobu_kuchi"
        setattr(_sw, na, korobu)
        moto = dp.OUTSIDE_LEGS
        try:
            dp.OUTSIDE_LEGS = (("試し", na),)
            bad, why = dp.legs_of_path(p, what="試しの台本")
            assert why, "口が転んだのに `why` が空です（＝「通った」になっています）"
            assert "試し" in why, why
        finally:
            dp.OUTSIDE_LEGS = moto
            delattr(_sw, na)
