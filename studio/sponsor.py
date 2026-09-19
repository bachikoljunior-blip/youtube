"""**門の外の分子 その1（企業案件）を歩く手**（**API 0単位**・台帳だけ）。

**2026-09-20 04:xx・optimizer・Opus 5・ultracode・1周 1体 が書いた**（JOURNAL 同刻）。

---

## なぜ在るか —— **この repo が 2日 にわたって「腕が無い」と書き続けた所**

`studio/cli.py`（`cmd_status` の中・2026-09-18 15:4x）:

> すぐ上の行は門の外を **企業案件 1つ** と数え、**その道を歩く手を 1つ も置けませんでした**
> （相手の yes が要るので、うちの側に腕がありません）。

`studio/asp.py` 冒頭も、`docs/METHOD.md` §5 も、`trend.perf_need_rate` の註も、同じ字で
**「企業案件は相手の yes ＝ こちらに腕が無い」**と書き、そこで止まっています。
**止まった先に在るのが、いま測れている中でいちばん近い道です**（下の数）。

    門の内 広告        `trend.rev_deadline`  登録 43人 → 1,000人 ＝ **期限の 485日 後**
    門の外 成果報酬     `trend.perf_need_rate` 6本/日 で **0.3倍**・ただし扉と **クリック 105倍** が要る
    門の外 **企業案件**  `trend.ungated_yen`    6本/日 で **0.89倍** ＝ **相場の中段の内側**

**＝ 3つ のうち、相場の中で届くと読めるのは 企業案件 だけです。**
それが「腕が無い」の一言で、**一度も手を置かれないまま 2日 立っていました。**

**「相手の yes が要る」は本当です。「だからこちらに腕が無い」は本当ではありません。**
yes を貰う前にこちらが作る物が 3つ あり、**3つとも 台帳だけで作れます（API 0単位）**:

    (1) **媒体資料**   再生/月・相手の齢・本数・実績を、こちらの数で 1枚 にする（`sheet`）
    (2) **相手の一覧** 誰に声を掛けるか（`TARGETS`・扉が開いている順）
    (3) **文面**       オーナーが貼るだけの字（`letter`）

**オーナーの手は「送る」だけ**になります（窓 1つ・数分）。
これは `docs/FOR_OWNER.md` の「最小手順」と同じ形で、**成果報酬の窓（提携申請）と同じ重さ**です。

---

## 値段の出どころ（**写しを持たない**）

**単価の帯は `trend.SPONSOR_YEN_PER_VIEW_BAND` の 1か所にしかありません**（¥0.5／**¥1.5**／¥3.0・**未測**）。
再生/月 も 天井の本/日 も `trend.ungated_yen` から引きます。
**この file は定数を 1つ も持ちません** —— 持った日が、帯が動いても追わなくなる日です
（`trend.sponsor_daily_cap_videos` が 2026-09-18 に踏んだのと同じ穴・検査 `tests/test_studio_sponsor.py`）。

**提示できる額** ＝ 再生/月 × 帯。6本/日 の天井（再生/月 **149,380回**）× 中段 ¥1.5 ＝ **¥224,070/月**
＝ **1社 の yes で目標の 1.12倍**。いま（1,600回/日）でも 中段で ¥71,980/月 ＝ **0.36本ぶん**。

---

## 相手の選び方（`TARGETS` の並び）

**成果報酬の「扉」とは別の問い**です（`studio/asp.py`「案件の扉」）。あちらは
**否認条件が視聴者を落とすか**でした。企業案件は成果ではなく**枠**を買うので、
否認条件は掛かりません。**掛かるのは 3つ**:

    (a) **相手の客が、この画面の向こうに居るか**   相手は **65歳以上 62.5%**（`trend.audience_split`）
    (b) **相手が 外部の媒体に金を払う習慣が在るか**  上場・広報窓口・法人提携の口が在るか
    (c) **相手の 1件 が大きいか**                  葬儀・墓・介護は 1件 数十万〜数百万

**(a)(b)(c) が 3つ とも立つのは 供養・終活・介護** です（`asp.py` の棚と同じ相手で、
**そちらは 1件 ¥1,000〜5,000 の成果報酬、こちらは 枠の買い切り** ＝ 同じ相手に 2つ の売り方）。

**電話番号・URL は「読んだ日」と一緒に持ちます**（`src` の欄）。**読んでいない口は載せません** ——
載せた瞬間、次の回がそれを「確かめた口」として読みます（`PERF_CLICK_BAND` が 11件 で
「実測」になった時と同じ形）。**`checked` が False の行は、オーナーに出す前に 1度 開くこと。**

---

## 覆る条件

 (1) **返事が「登録者数で決めています」で返ったら**、この道は登録 1,000人 の門の内側へ移ります
     ＝ そのとき 企業案件 は `rev_deadline` の側（期限の外）になり、**この file は畳むこと**。
     **まだ 1度 も訊いていません** —— それが (1) を引く唯一の手です。
 (2) **`trend.SPONSOR_YEN_PER_VIEW_BAND` は未測です**（うちは 1件 も受けていない）。
     1社 でも見積りが返ったら、**その数が帯の正本**になります ＝ 帯を直す所は `trend` の 1か所。
 (3) **相手の齢（`p65`）が読めなくなったら**（`audience_split` が `measured: False`）、
     媒体資料の 1枚目 の売りが消えます ＝ そのときは再生/月 だけで出すこと（`sheet` は自動で落とします）。
 (4) **3社 に送って 3社 とも無返事なら**、次は「送る相手」ではなく**媒体資料の中身**を疑うこと
     （再生/月 が 5万 では枠として小さい ＝ 6本/日 を先に戻す）。
 (5) 広告であることの表示（景表法・ステマ規制）は `studio/asp.py` と同じ門を通すこと ——
     **企業案件でも `【PR】` は要ります**。yes が返った回が `asp.compose` の側へ足すこと。
"""
from __future__ import annotations

from .common import BRAND_NAME


def _t(name: str, cat: str, why: str, route: str, src: str, checked: bool) -> dict:
    return {"name": name, "cat": cat, "why": why, "route": route, "src": src, "checked": checked}


#: 声を掛ける相手（**扉が開いている順**＝ 上の註 (a)(b)(c) が 3つ とも立つ順）。
#: **`checked` が True の行だけ、そのまま出してよい**（上の註）。
TARGETS = [
    _t("株式会社鎌倉新書（いいお墓・いい葬儀・いい相続）",
       "供養・終活のポータル（上場）",
       "相手の客が 65歳以上 に寄っていて、外部の媒体に払う習慣が在る（13サービス・広報窓口が在る）",
       "「いいお墓」掲載・提携のお問い合わせ https://www.e-ohaka.com/contact_partner/"
       "（お墓事業 法人窓口 03-6262-3522）",
       "e-ohaka.com/contact_partner・kamakura-net.co.jp（2026-09-20 に読んだ）", True),
    _t("株式会社ユニクエスト（小さなお葬式）",
       "葬儀（累計 66万件）",
       "法人向けの提携の口が公開で在る（導入費・運用費 0円 と書いている ＝ 外部と組む前提の窓口）",
       "法人様向けサービス https://www.osohshiki.jp/alliance/",
       "osohshiki.jp/alliance（2026-09-20 に読んだ）", True),
    _t("株式会社よりそう（よりそうお葬式）",
       "葬儀",
       "同じ棚の 2番手。相手も出し先も 小さなお葬式 と同じ",
       "公式サイトの「お問い合わせ」から（**URL 未確認 ＝ 出す前に 1度 開くこと**）",
       "未読", False),
    _t("株式会社クーリエ（みんなの介護）",
       "老人ホーム・介護施設の紹介",
       "1件 が大きく（入居）、決めるのは本人か子。うちの相手は 65歳以上 62.5%",
       "株式会社クーリエ お問い合わせ https://www.courier.jpn.com/contact/"
       "（`minnanokaigo.com/ad-form/` は**施設の掲載**の口 ＝ 媒体の話はこちらではありません）",
       "courier.jpn.com/contact（2026-09-20 に読んだ）", True),
    _t("株式会社エイチームライフデザイン（ライフドット）",
       "お墓・葬儀のポータル",
       "同じ棚。上場子会社 ＝ 媒体費の決裁の形が在る",
       "公式サイトの「お問い合わせ」から（**URL 未確認 ＝ 出す前に 1度 開くこと**）",
       "未読", False),
]


def checked_targets() -> list[dict]:
    """**口を実際に読んだ相手だけ。** オーナーに出せるのはこちらです（上の註）。"""
    return [t for t in TARGETS if t["checked"]]


def kit(rows: list[dict], scripts_dir=None) -> dict:
    """媒体資料の数（**API 0単位**・台帳だけ）。**定数は 1つ も持ちません**（上の註）。

    返り: `{"views_month","views_month_cap","per_day_cap","band","goal",
             "price": {level: {"now","cap"}}, "times_cap", "p65","p55","top",
             "audience_measured","audience_window","subs","views_total","n"}`
    """
    from . import trend as _trend

    d = _trend.ungated_yen(rows, scripts_dir)
    g = _trend.channel_growth(rows)
    a = _trend.audience_split(rows) or {}

    vm = float(d["views_month"] or 0.0)
    vc = float((d["cap"] or {}).get("views_month") or vm)
    band = tuple(d["band"])

    price = {}
    for lv, b in zip(_trend.YEN_LEVELS, band):
        price[lv] = {"now": vm * b, "cap": vc * b}

    return {
        "views_month": vm,
        "views_month_cap": vc,
        "per_day_cap": _trend.sponsor_daily_cap_videos(),
        "band": band,
        "goal": float(d["goal"]),
        "need_per_view": d["need_per_view"],
        "times_cap": ((d["cap"] or {}).get("times") or {}).get("中"),
        "price": price,
        "audience_measured": bool(a.get("measured")),
        "p65": a.get("p65"),
        "p55": a.get("p55"),
        "top": a.get("top"),
        "audience_window": (a.get("start"), a.get("day")),
        "subs": g.get("subs"),
        "views_total": g.get("views"),
        "n": g.get("n"),
    }


def sheet(rows: list[dict], scripts_dir=None) -> str:
    """**媒体資料 1枚**（そのまま貼れる字・**API 0単位**）。

    **相手の齢が測れていない周は、その行を落とします**（覆る条件 (3)）——
    測っていない数を売りにすると、返事の 1通目 で崩れます。
    """
    k = kit(rows, scripts_dir)
    lo, mid, hi = k["band"]
    L = [f"# 媒体資料 —— YouTube「{BRAND_NAME}」",
         "",
         "## どんな画面か",
         "",
         "年金・退職金の「手取りが実際にいくらか」を、1本 1分ほどで数字だけ見せるショート動画です。",
         f"本数 {k['n']:,}本・総再生 {k['views_total']:,}回・チャンネル登録 {k['subs']:,}人。",
         ""]
    if k["audience_measured"] and k["p65"] is not None:
        s, e = k["audience_window"]
        top = k.get("top") or {}
        tl = ""
        if top:
            tl = f"（いちばん多い層は {top.get('age')}・{top.get('gender')} で {top.get('pct')}%）"
        L += ["## 見ている人",
              "",
              f"**55歳以上 {k['p55']:.1f}%・65歳以上 {k['p65']:.1f}%**{tl}。"
              f"（YouTube アナリティクスの実測・{s}〜{e}）",
              "",
              "＝ 登録者数ではなく**年齢の寄り**が、この画面の値打ちです。"
              "供養・終活・介護のように「客が 65歳以上 に寄っている」商材ほど、無駄打ちが減ります。",
              ""]
    else:
        L += ["## 見ている人",
              "",
              "（この期間は年齢の実測が取れていないため、載せていません）",
              ""]
    L += ["## 配る量",
         "",
         f"いま 再生/月 **{k['views_month']:,.0f}回**。"
         f"投稿を 1日 {k['per_day_cap']:.0f}本 に戻すと 再生/月 **{k['views_month_cap']:,.0f}回** です"
         "（1本あたりの再生は動かさずに数えた見込み）。",
         "",
         "## ご提案できる形",
         "",
         "・本編の中で商品・サービスを紹介（タイアップ）",
         "・概要欄・固定コメント・チャンネルのリンク欄への掲載",
         "・上の組み合わせを、月単位の掲載として",
         "",
         "## 費用の目安",
         "",
         "| 単価（円/再生） | いまの月額 | 1日 "
         f"{k['per_day_cap']:.0f}本 に戻した月額 |",
         "|---|---|---|"]
    for lv, b in zip(("低", "中", "高"), (lo, mid, hi)):
        p = k["price"][lv]
        L.append(f"| ¥{b} | ¥{p['now']:,.0f} | ¥{p['cap']:,.0f} |")
    L += ["",
          "※ 相場の一般的な幅で置いた目安です。ご予算に合わせて形をお作りします。",
          "",
          "## 表示について",
          "",
          "広告であることは、景品表示法・ステルスマーケティング規制に沿って"
          "動画内と概要欄に【PR】と明記します。",
          ""]
    return "\n".join(L)


def letter(rows: list[dict], target: "dict | None" = None, scripts_dir=None) -> str:
    """**オーナーが貼るだけの文面**（**API 0単位**）。

    **1通目に値段を書きません** —— 先に数だけ出して、相手の枠に合わせてもらうほうが返事が来ます。
    値段は `sheet` の側に在り、2通目（返事が来た回）で出します。
    """
    k = kit(rows, scripts_dir)
    who = (target or {}).get("name", "ご担当者")
    age = ""
    if k["audience_measured"] and k["p65"] is not None:
        # **`**` を入れないこと** —— これはメールの本文で、md として読まれません。
        age = f"視聴者は65歳以上が{k['p65']:.0f}%（55歳以上は{k['p55']:.0f}%）で、"
    return (
        f"件名: YouTubeでのタイアップ・広告掲載のご相談（{BRAND_NAME}）\n"
        "\n"
        f"{who} 様\n"
        "\n"
        "突然のご連絡を失礼いたします。\n"
        f"YouTubeで「{BRAND_NAME}」というチャンネルを運営しております。\n"
        "年金・退職金の手取り額を1本1分ほどの動画で解説しており、\n"
        f"これまでに{k['n']:,}本・総再生{k['views_total']:,}回です。\n"
        "\n"
        f"{age}現在の再生数は月あたり約{k['views_month']:,.0f}回、\n"
        f"投稿本数を1日{k['per_day_cap']:.0f}本に戻した場合は月あたり約{k['views_month_cap']:,.0f}回を見込んでおります。\n"
        "\n"
        "御社のサービスは、この視聴者層と重なる部分が大きいと考えております。\n"
        "動画内でのご紹介や概要欄への掲載など、タイアップのご相談をさせていただけないでしょうか。\n"
        "媒体資料をお送りいたしますので、ご興味があればご返信いただけますと幸いです。\n"
        "\n"
        "なお、広告であることは景品表示法・ステルスマーケティング規制に沿って\n"
        "動画内と概要欄に【PR】と明記いたします。\n"
        "\n"
        "ご検討のほど、よろしくお願いいたします。\n"
    )


def short(rows: list[dict], scripts_dir=None) -> str:
    """`status`／`trend` に足す 1行。**空になる周はありません**（数は台帳から出ます）。

    **決めと覆る条件は上の註 ＝ ここへ決めを書かないこと。**
    """
    k = kit(rows, scripts_dir)
    if not k["views_month_cap"]:
        return ""
    ct = len(checked_targets())
    return ("**企業案件を歩く手**（`studio/sponsor.py`・**API 0単位**）: "
            f"提示できる額 **¥{k['price']['中']['cap']:,.0f}/月**"
            f"（1日 {k['per_day_cap']:.0f}本 の再生/月 {k['views_month_cap']:,.0f}回 × 相場の中段 ¥{k['band'][1]}）"
            f" ＝ **1社 の yes で目標の {k['price']['中']['cap']/k['goal']:.2f}倍**。"
            f"相手の一覧 **{len(TARGETS)}社**（口を読んだのは **{ct}社**）・"
            "媒体資料と文面は `python -m studio.cli sponsor`。"
            "**まだ 1社 も送っていません** ＝ この行が『0社』のあいだ、"
            "**門の外でいちばん近い道（6本/日 で 0.89倍）は 1度 も試されていません**"
            "（`trend.ungated_yen`・覆る条件は `studio/sponsor.py` の註）")
