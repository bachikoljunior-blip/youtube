"""退職金の手取りシリーズ・**年数の側**（ショート 5本）—— 退職金は 2000万円 に固定して、**勤続年数を動かす**。

**2026-09-18 21:xx JST・optimizer・1周 1体 が書いた**（JOURNAL 同刻）。

**なぜ「額」ではなく「年数」か**（`series_taishoku` の覆る条件 (2) の枝）:
額の側（1500〜3000万）は 09/19 の 4本 で出し切りました。**次に動かす軸は年数です** ——
長尺 `2026-09-17-taishokukin-2000man-tedori` の説明欄には **年数ごとの表（20/25/30/35/38年）が既に在り**、
`tests/test_series_taishoku.py` がその 9つ の数を同じ式で再現しています ＝
**この 5本 は、数を 1つ も新しく作りません**（`series_taishoku.tax` をそのまま呼ぶ）。

**なぜ別 file か**: `series_taishoku` は **30年（枠1500万円）を 5か所 に直書き**しています
（`PREM_SEG`／`RULE_SEG` の板／`FRAME_SEG`／`taxable_seg` の「枠1500万円」／`PREMISE`）。
年数を動かすには そこを全部 引数にする必要があり、**書き換えると 09/19 の 4本 の `build_sig` が動きます**
（上げ直しに 1本 1,650単位）。`series.py` の覆る条件 (2)「額→本文 の形が合わなければ別の生成器」と同じ判断です。

**コマ8（しくみ）は 5本 とも手で書いています** —— 年数ごとに**効いている線が違う**からです:
20年の壁／20年をこえた分の 70万円／端数の切り上げ／段が 5% まで下がる／枠が退職金をこえる。
**ここを共通化すると、5本 が同じことを言う本になります**（＝ 量産の印・`CLAUDE.md` の (B)）。

使い方:  python -m studio.series_taishoku_years            # 5本 全部
         python -m studio.series_taishoku_years <id> ...   # その id だけ
**書いたあとは lint → critique → build → hear → schedule --at ... --force**（METHOD §4 の順）。
**`build` は台本を最後に触ったあとに撃つこと**（先に焼くと `build_sig` が古くなり、
上げる瞬間に 92秒/本 を払います —— JOURNAL 2026-09-18 17:0x が 5本 ぶん払った）。

**覆る条件**:
 (1) **この 5本 の 24h 中央が、額の側の 4本（09/19）の中央の半分 未満**なら、動かす軸は年数ではありません
     ＝ 次は軸ではなく**題材**を変えること（`demand` の段の上から）。
 (2) **20年 の本だけが伸びたら**、効いているのは年数ではなく**「壁」そのもの**です
     ＝ 次の連作は「1年の差で変わる線」を題材ごとに集めること（年金の繰上げ・扶養の 106万／130万 など）。
 (3) 年数を足すとき（15年・40年）は `BOOKS` に足すだけでよいが、**コマ8 は足す側が手で書くこと**（上の理由）。
"""
import json
import shutil
import sys
from pathlib import Path

from .series_taishoku import (BG_SRC, BRACKETS, CTA_SEG, IMAGES, LONG_URL, LOOK_SEG, NOT_SAID, SCRIPTS,
                              SOURCES, YEARS_TABLE, YOMI, deduction, man, tax)

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-09-20"
A = 2000                      #: 退職金（万円）。**この連作では動かさない軸**
AMOUNT = A * 10_000

YOMI = dict(YOMI)
YOMI.update({"壁": "かべ", "線": "せん", "未満": "みまん", "境": "さかい", "超": "こ", "少": "すく", "差": "さ",
             "働": "はたら", "勤続": "きんぞく", "満": "み", "満額": "まんがく", "段": "だん",
             # `lint` が「読みが固定されていない」と鳴った語（20年 のコマ8・38年 のコマ5・`critique` の直しで入った語）
             "目": "め", "方": "かた", "中": "なか", "大": "おお",
             "負担": "ふたん", "軽": "かる", "復興分": "ふっこうぶん"})


def frame_text(y: int) -> tuple[str, int]:
    """その年数の枠の出し方（声で言う1文）と枠の額。"""
    d = deduction(y)
    if y <= 20:
        return f"1年40万円かける{y}年で、枠は{man(d)}です。", d
    # **文は 40字 まで**（METHOD §3 の 6・`lint` が [?] で鳴る）＝ 読点ではなく句点で切る。
    return f"20年までで800万円。こえた{y - 20}年ぶんが70万円ずつで{man(700_000 * (y - 20))}。枠は{man(d)}です。", d


def prem_seg(y: int, tail: str) -> dict:
    return dict(say=f"たとえば、{y}年はたらいて退職。退職金は{A}万円です。{tail}",
                show=f"{y}年はたらいた", sub=f"たとえば同じ会社で{y}年はたらいて退職 退職金は{A}万円（一度に受け取る）",
                tag="前提", board=["同じ会社で", f"{y}年はたらいた", f"退職金 {A}万円", "一度に受け取る"])


#: **`series_taishoku` の同名を継がずに、この連作の中で書き直したもの**（2026-09-18 21:0x）。
#: 継ぐと 09/19 に上げた 4本 の `build_sig` が動きます（上げ直し 1本 1,650単位）。
#: 直した理由は `critique` の [real]（同刻・`2026-09-20-...-20nen-short` に撃った）:
#:  (1) コマ6「税率20%の段で78万8700円」＝ **600万 × 20% は 120万 で、78万8700円 の出どころが本文に無い**
#:      → 速算表の引き算と復興分を声に入れた（「段」だけでは、聞く側は検算できません）
#:  (2) コマ5「まとめた収入なので半分にだけ税金」＝ **なぜ半分になるのかが無い** → 制度の目的を1文
#:  (3) コマ1〜3 に「何と何をくらべるか」の宣言が無く、コマ8 で突然 比べる表が出る → フックで宣言する
#: **字を足したぶんは、この 3つ を短くして返しています**（連作は 450字 まで ＝ METHOD §31）。
RULE_SEG = dict(
    say="決まりでは、退職金には税金のかからない枠があり、年数で決まります。",
    show="枠は年数で決まる", sub="退職金には税金のかからない枠があり はたらいた年数で決まる",
    tag="決まり", board=["税金のかからない枠", "年数で決まる", "20年まで 1年40万円", "こえた分 1年70万円"],
    viz={"kind": "table", "title": "枠は年数で決まる", "head": ["はたらいた年数", "1年ごとにふえる枠"],
         "rows": [["20年まで", "40万円"], ["20年をこえた分", "70万円"]], "widths": [4, 4]})


#: `series_taishoku` の CTA を短くしたもの（この連作の中だけ。継ぐと 09/19 の 4本 の `build_sig` が動く）。
CTA_SEG = dict(
    say="カワウソの年金計算室でした。自分の場合は、説明欄の無料相談から聞けます。広告のリンクです。",
    show="説明欄の\n無料相談", sub="自分の場合いくらになるかは説明欄の無料相談から聞けます 広告のリンクです",
    tag="", board=["カワウソの年金計算室", "自分の場合は？", "説明欄の無料相談", "（広告のリンク）"])


def frame_seg(y: int) -> dict:
    say, d = frame_text(y)
    items = ([{"label": "20年まで", "value": 8_000_000}, {"label": f"こえた{y - 20}年", "value": 700_000 * (y - 20)}]
             if y > 20 else [{"label": f"{y}年 × 40万円", "value": d}])
    return dict(say=say, show=f"枠は {man(d)}", sub="計算すると " + say,
                # 板の1行は 14字 まで（`lint`）。「＋ こえた15年 1050万円」は 15字 で鳴る ＝ 「ぶん」の形に畳む。
                tag="計算", board=(["20年まで 800万円", f"＋{y - 20}年ぶん {man(700_000 * (y - 20))}", f"＝ 枠 {man(d)}"]
                                 if y > 20 else [f"40万円 × {y}年", f"＝ 枠 {man(d)}"]),
                viz={"kind": "bars", "title": f"{y}年はたらいた人の枠", "items": items,
                     "total": {"label": "枠", "value": d}})


def taxable_seg(t: dict) -> dict:
    over, half, d = t["over"], t["taxable"], t["deduction"]
    if over == 0:
        return dict(say=f"{A}万円は枠{man(d)}の中におさまります。はみ出た分が0円なので、税金のかかる金額も0円です。",
                    show="税金のかかる金額 0円", sub=f"{A}万円は枠{man(d)}の中におさまる はみ出た分が0円なので税金のかかる金額も0円",
                    tag="計算", board=[f"退職金 {A}万円", f"− 枠 {man(d)}", "＝ はみ出た分 0円", "税金のかかる金額 0円"],
                    viz={"kind": "bars", "title": "枠が退職金をこえている", "items": [{"label": "退職金", "value": AMOUNT},
                                                                          {"label": "枠", "value": d}]})
    # **1文は 40字 まで**（METHOD §3 の 6）＝ 「なぜ半分か」は足すが、句点で切る。
    return dict(say=f"枠を引くと{man(over)}がはみ出ます。何年分かまとめた収入です。負担を軽くするため、半分の{man(half)}にだけ税金がかかります。",
                show=f"税金がかかるのは {man(half)}",
                sub=f"{A}万円から枠{man(d)}を引くと{man(over)}がはみ出る 何年分かまとめた収入なので負担を軽くするため半分の{man(half)}にだけ税金がかかる",
                tag="計算", board=[f"退職金 {A}万円", f"− 枠 {man(d)}", f"＝ はみ出た分 {man(over)}", "半分にだけ税金", f"＝ {man(half)}"],
                viz={"kind": "table", "title": "税金がかかる金額",
                     "rows": [["退職金", f"{A}万円"], ["− 枠", man(d)], ["＝ はみ出た分", man(over)], ["半分にだけ税金", man(half)]],
                     "widths": [4, 4]})


def tax_seg(t: dict) -> dict:
    pct = int(round(t["rate"] * 100))
    sub = next(s for hi, r, s in BRACKETS if t["taxable"] <= hi)
    # **速算表の引き算を声に入れる**（`critique` の [real] (1)）——
    # 「税率20%の段で78万8700円」だけだと、600万 × 20% ＝ 120万 との差が本文のどこにも無い。
    head = (f"所得税は{man(t['taxable'])}の{pct}%から{man(sub)}を引きます。復興分を入れて{man(t['income_tax'])}。"
            if sub else f"所得税は{man(t['taxable'])}の{pct}%に復興分を入れて{man(t['income_tax'])}。")
    return dict(
        say=head + f"住民税は10%で{man(t['resident_tax'])}です。",
        show=f"所得税 {man(t['income_tax'])}",
        sub=head + f"住民税は{man(t['taxable'])}の10%で{man(t['resident_tax'])}",
        tag="計算", board=[f"{man(t['taxable'])} の {pct}%", f"− {man(sub)}", "＋ 復興特別所得税",
                          f"所得税 {man(t['income_tax'])}", f"住民税 {man(t['resident_tax'])}"],
        viz={"kind": "bars", "title": "税金 2つ", "items": [{"label": "所得税", "value": t["income_tax"]},
                                                        {"label": "住民税", "value": t["resident_tax"]}],
             "total": {"label": "税金", "value": t["tax"]}})


def result_seg(t: dict) -> dict:
    return dict(say=f"合わせて{man(t['tax'])}。手取りは{man(t['net'])}です。",
                show=f"手取り {man(t['net'])}", sub=f"税金は合わせて{man(t['tax'])} 退職金{A}万円から引いて手取りは{man(t['net'])}",
                tag="結論", board=[f"所得税 {man(t['income_tax'])}", f"＋ 住民税 {man(t['resident_tax'])}",
                                  f"＝ 税金 {man(t['tax'])}", f"手取り {man(t['net'])}"],
                viz={"kind": "waterfall", "title": "退職金から引かれる税金", "start": {"label": "退職金", "value": AMOUNT},
                     "steps": [{"label": "税金", "value": t["tax"]}], "end": {"label": "手取り", "value": t["net"]}})


def hook_seg(y: int, t: dict, extra: str) -> dict:
    return dict(say=f"退職金{A}万円、{y}年はたらいた人の手取りは{man(t['net'])}。{extra}",
                show=f"手取り {man(t['net'])}", sub=f"退職金{A}万円 {y}年はたらいた人の手取りは{man(t['net'])} 税金は{man(t['tax'])}",
                tag="", board=[f"退職金 {A}万円", f"{y}年はたらいた", f"税金 {man(t['tax'])}", f"手取り {man(t['net'])}"],
                viz={"kind": "waterfall", "title": "退職金から引かれる税金", "start": {"label": "退職金", "value": AMOUNT},
                     "steps": [{"label": "税金", "value": t["tax"]}], "end": {"label": "手取り", "value": t["net"]}})


def premise(y: int) -> str:
    d = deduction(y)
    frame = (f"・20年まで 1年40万円 × 20年 ＝ 800万円\n・20年をこえた分 1年70万円 × {y - 20}年 ＝ {man(700_000 * (y - 20))}\n"
             f"・合計 {man(d)}（国税庁 タックスアンサー No.1420）" if y > 20 else
             f"・20年までは 1年40万円。40万円 × {y}年 ＝ {man(d)}（国税庁 タックスアンサー No.1420）")
    return (f"【前提（例の人）】\n・同じ会社で{y}年はたらいて退職。退職金は{A}万円、一時金（一度に受け取る）\n"
            "・「退職所得の受給に関する申告書」を会社に出している\n"
            "・障害が理由の退職ではない。同じ年に他の退職金はない\n\n"
            f"【退職所得控除（枠）】\n{frame}")


def calc_lines(t: dict) -> str:
    d = t["deduction"]
    if t["taxable"] == 0:
        return (f"【計算】\n・{A}万円 − 枠{man(d)} ＝ 0円以下 → 税金のかかる金額は 0円\n"
                f"・所得税 0円・住民税 0円 → 税金の合計 0円\n・手取り ＝ {A}万円")
    pct = int(round(t["rate"] * 100))
    sub = next(s for hi, r, s in BRACKETS if t["taxable"] <= hi)
    base = int(t["taxable"] * t["rate"]) - sub
    return (f"【計算】\n・{A}万円 − 枠{man(d)} ＝ {man(t['over'])}\n"
            f"・{man(t['over'])} × 2分の1 ＝ {man(t['taxable'])}（税金のかかる金額・課税退職所得）\n"
            f"・所得税 {man(t['taxable'])} × {pct}% − {man(sub)} ＝ {man(base)}（No.2260 の速算表）\n"
            f"・復興特別所得税（所得税の2.1%）を入れて {man(t['income_tax'])}（百円未満切り捨て）\n"
            f"・住民税 {man(t['taxable'])} × 10% ＝ {man(t['resident_tax'])}\n"
            f"・税金の合計 {man(t['income_tax'])} ＋ {man(t['resident_tax'])} ＝ {man(t['tax'])}\n"
            f"・手取り {A}万円 − {man(t['tax'])} ＝ {man(t['net'])}")


NOT_SAID_YEARS = NOT_SAID.replace(
    "【同じ計算の他の金額】\n・退職金1500万円・2000万円・2500万円・3000万円（どれも勤続30年）を順に出しています",
    "【同じ計算の他の年数】\n・退職金2000万円で、勤続20年・25年・31年（30年2か月）・35年・38年を順に出しています\n"
    "・金額の側（1500万円・2000万円・2500万円・3000万円／どれも勤続30年）も別に出しています")


def base_script(vid, title, takeaway, desc, segs, y):
    return {"id": vid, "date": DATE, "title": title, "takeaway": takeaway, "description": desc,
            "tags": ["退職金", "手取り", "税金", "退職所得控除", "所得税", "住民税", "2000万円", f"勤続{y}年"],
            "voice": "ja-JP-Neural2-D", "rate": 1.08,
            "yomi": {k: v for k, v in YOMI.items() if any(k in s["say"] for s in segs)},
            # 「表」は Neural2-D が「おもて」と読む（`series_taishoku.base_script` の註・2026-09-18 04:0x の hear）
            "kana_in_voice": [k for k in ("表",) if any(k in s["say"] for s in segs)],
            "image_prompt": "日本の60代前半の男性が、自宅の机で退職金の明細の書類と電卓を前にして、落ち着いた表情で座っている様子。やわらかい自然光。写実的な写真風。文字やロゴは入れない。縦長。",
            "form": "short", "thumb": [], "segments": segs,
            "notes": ("退職金の手取りシリーズ・年数の側（ショート）。2026-09-18 21:xx JST に optimizer が "
                      "`studio/series_taishoku_years.py` で書いた。退職金は 2000万円 に固定し、勤続年数だけ動かす。\n"
                      "数は長尺 `2026-09-17-taishokukin-2000man-tedori`（`ukEFxTt1PEY`）の説明欄の年数の表と同じ式"
                      "（`series_taishoku.tax`・No.1420／2260／2732）＝ 新しく作った数は 1つ もない。\n"
                      "コマ8（しくみ）は本ごとに手で書いている（年数ごとに効いている線が違う ＝ file 冒頭の理由）。\n"
                      "CTA は説明欄の成果報酬のリンクへ（`studio/asp.py`・2026-09-18 20:3x）。")}


def desc_for(y: int, t: dict, lead: str, why: str) -> str:
    return (lead + "\n\n" + premise(y) + "\n\n" + calc_lines(t) + "\n\n" + why + "\n\n"
            + YEARS_TABLE + "\n\n" + NOT_SAID_YEARS + "\n\n" + SOURCES + "\n\n"
            "【くわしい計算（長尺）】\n"
            f"・退職金2000万円・30年の計算を最初から最後まで（年数ごと・金額ごとの早見表つき） {LONG_URL}")


# ---------------------------------------------------------------- 20年（**20年の壁**）
def y20():
    y, t = 20, tax(AMOUNT, 20)
    t21 = tax(AMOUNT, 21)
    diff = t["tax"] - t21["tax"]
    segs = [
        # **フックで「何と何をくらべるか」を宣言する**（`critique` の [real] (3)）。
        hook_seg(y, t, "21年はたらいた人とくらべます。"),
        prem_seg(y, ""), RULE_SEG, frame_seg(y), taxable_seg(t), tax_seg(t), result_seg(t),
        # **途中式を声に入れる**（`critique` の [real] (4)）—— 枠 +70万 → かかる金額 −35万 → 税金 −10万6500円。
        dict(say=f"20年が線です。21年目からは枠が70万円ふえます。税金のかかる金額は35万円へり、税金は{man(diff)}へります。",
             show="20年が線", sub=f"20年が線 21年目から枠が70万円ふえて税金のかかる金額が35万円へり 税金は{man(diff)}へる",
             tag="しくみ", board=["20年までは 1年40万円", "21年目から 1年70万円", "枠 ＋70万円", f"税金 −{man(diff)}"],
             viz={"kind": "table", "title": "20年 と 21年", "head": ["", "20年", "21年"],
                  "rows": [["枠", man(t["deduction"]), man(t21["deduction"])], ["税金", man(t["tax"]), man(t21["tax"])],
                           ["手取り", man(t["net"]), man(t21["net"])]], "widths": [3, 3, 3]}),
        LOOK_SEG, CTA_SEG]
    why = (f"【なぜ 21年目で変わるのか】\n・枠は 20年までが 1年40万円、20年をこえた分が 1年70万円。"
           f"21年だと 800万円 ＋ 70万円 ＝ {man(t21['deduction'])}\n"
           f"・2000万円 − {man(t21['deduction'])} ＝ {man(t21['over'])} → 2分の1 ＝ {man(t21['taxable'])} → "
           f"税金の合計 {man(t21['tax'])}（20年より {man(diff)} 少ない）\n"
           f"・手取り {man(t21['net'])}（20年との差 {man(t21['net'] - t['net'])}）")
    desc = desc_for(y, t, f"退職金{A}万円を勤続20年で受け取ると、税金を引かれたあとにいくら残るかを計算しました。"
                          "20年と21年で税金がいくら変わるかも出しています。", why)
    return base_script(f"{DATE}-taishokukin-2000man-20nen-short",
                       f"退職金2000万円 勤続20年の手取りは{man(t['net'])} あと1年で税金が{man(diff)}へります #Shorts",
                       f"退職金の税金のかからない枠は 20年までが1年40万円・20年をこえた分が1年70万円。勤続20年なら枠は{man(t['deduction'])}で、"
                       f"2000万円から引いた{man(t['over'])}の半分{man(t['taxable'])}に税金がかかる。税金は{man(t['tax'])}、手取りは{man(t['net'])}。"
                       f"21年はたらくと枠が70万円ふえて税金は{man(t21['tax'])}になり、1年で{man(diff)}変わる。",
                       desc, segs, y)


# ---------------------------------------------------------------- 25年
def y25():
    y, t = 25, tax(AMOUNT, 25)
    t20 = tax(AMOUNT, 20)
    segs = [
        hook_seg(y, t, "20年の人とくらべます。"),
        prem_seg(y, ""), RULE_SEG, frame_seg(y), taxable_seg(t), tax_seg(t), result_seg(t),
        dict(say=f"20年をこえた5年で枠が350万円ふえ、税金のかかる金額が175万円へります。税金は{man(t20['tax'] - t['tax'])}の差です。",
             show="こえた5年で 350万円", sub=f"20年をこえた5年で枠が350万円ふえ税金のかかる金額が175万円へる 税金は{man(t20['tax'] - t['tax'])}の差",
             tag="しくみ", board=["20年をこえた5年", "70万円 × 5年", "＝ 枠 ＋350万円", f"税金 −{man(t20['tax'] - t['tax'])}"],
             viz={"kind": "table", "title": "20年 と 25年", "head": ["", "20年", "25年"],
                  "rows": [["枠", man(t20["deduction"]), man(t["deduction"])], ["税金", man(t20["tax"]), man(t["tax"])],
                           ["手取り", man(t20["net"]), man(t["net"])]], "widths": [3, 3, 3]}),
        LOOK_SEG, CTA_SEG]
    why = (f"【なぜ 20年より{man(t20['tax'] - t['tax'])}少ないのか】\n"
           f"・20年をこえた分の枠は 1年70万円。25年なら 800万円 ＋ 70万円 × 5年 ＝ {man(t['deduction'])}（20年より 350万円 多い）\n"
           f"・税金のかかる金額は はみ出た分の半分なので、枠が 350万円 ふえると 175万円 減る\n"
           f"・20年の税金 {man(t20['tax'])} → 25年 {man(t['tax'])}（差 {man(t20['tax'] - t['tax'])}）")
    desc = desc_for(y, t, f"退職金{A}万円を勤続25年で受け取ると、税金を引かれたあとにいくら残るかを計算しました。"
                          "20年の人との差も出しています。", why)
    return base_script(f"{DATE}-taishokukin-2000man-25nen-short",
                       f"退職金2000万円 勤続25年の手取りは{man(t['net'])} 税金は{man(t['tax'])} #Shorts",
                       f"勤続25年の枠は 800万円 ＋ 70万円×5年 ＝ {man(t['deduction'])}。2000万円から引いた{man(t['over'])}の半分{man(t['taxable'])}に税金がかかり、"
                       f"税金は{man(t['tax'])}、手取りは{man(t['net'])}。勤続20年の人（税金{man(t20['tax'])}）より{man(t20['tax'] - t['tax'])}少ない。",
                       desc, segs, y)


# ---------------------------------------------------------------- 31年（端数の切り上げ）
def y31():
    y, t = 31, tax(AMOUNT, 31)
    t30 = tax(AMOUNT, 30)
    segs = [
        hook_seg(y, t, "30年2か月でも、31年で計算します。"),
        prem_seg(y, ""), RULE_SEG, frame_seg(y), taxable_seg(t), tax_seg(t), result_seg(t),
        dict(say="1年未満の端数は1年に切り上げます。30年2か月なら31年で、枠が70万円ふえます。",
             show="30年2か月 → 31年", sub=f"1年に満たない端数は1年に切り上げる 30年2か月なら31年 枠が70万円ふえて手取りは{man(t['net'] - t30['net'])}ふえる",
             tag="しくみ", board=["端数は1年に切り上げ", "30年2か月 → 31年", "枠 ＋70万円", f"手取り ＋{man(t['net'] - t30['net'])}"],
             viz={"kind": "table", "title": "30年 と 30年2か月", "head": ["", "30年", "31年"],
                  "rows": [["枠", man(t30["deduction"]), man(t["deduction"])], ["税金", man(t30["tax"]), man(t["tax"])],
                           ["手取り", man(t30["net"]), man(t["net"])]], "widths": [3, 3, 3]}),
        LOOK_SEG, CTA_SEG]
    why = (f"【なぜ 2か月で手取りがふえるのか】\n・勤続年数の1年未満の端数は1年に切り上げ（No.1420）。30年2か月 → 31年\n"
           f"・枠は 800万円 ＋ 70万円 × 11年 ＝ {man(t['deduction'])}（30年より 70万円 多い）\n"
           f"・税金 {man(t30['tax'])} → {man(t['tax'])}・手取り {man(t30['net'])} → {man(t['net'])}（差 {man(t['net'] - t30['net'])}）")
    desc = desc_for(y, t, f"退職金{A}万円を勤続30年2か月（切り上げて31年）で受け取ると、税金を引かれたあとにいくら残るかを計算しました。"
                          "端数の切り上げで手取りがふえる理由も出しています。", why)
    return base_script(f"{DATE}-taishokukin-2000man-31nen-short",
                       f"退職金2000万円 30年2か月はたらくと手取りが{man(t['net'] - t30['net'])}ふえます 端数は1年に切り上げ #Shorts",
                       f"勤続年数の1年未満の端数は1年に切り上げるので、30年2か月は31年で計算する。枠は 800万円 ＋ 70万円×11年 ＝ {man(t['deduction'])}で、"
                       f"30年より70万円多い。2000万円から引いた{man(t['over'])}の半分{man(t['taxable'])}に税金がかかり、税金は{man(t['tax'])}、"
                       f"手取りは{man(t['net'])}。30年（手取り{man(t30['net'])}）との差は{man(t['net'] - t30['net'])}。",
                       desc, segs, y)


# ---------------------------------------------------------------- 35年（段が 5% まで下がる）
def y35():
    y, t = 35, tax(AMOUNT, 35)
    t30 = tax(AMOUNT, 30)
    segs = [
        hook_seg(y, t, "30年の人とくらべます。"),
        prem_seg(y, ""), RULE_SEG, frame_seg(y), taxable_seg(t), tax_seg(t), result_seg(t),
        dict(say="所得税は金額ごとに段があります。税金のかかる金額が195万円以下なら、いちばん下の5%の段です。",
             show="195万円以下は 5%", sub="所得税は金額ごとに段がある 税金のかかる金額が195万円以下ならいちばん下の5%の段",
             tag="しくみ", board=["所得税は段になっている", "195万円まで 5%", "330万円まで 10%", f"この人は {man(t['taxable'])}"],
             viz={"kind": "table", "title": "所得税の段", "head": ["税金のかかる金額", "税率"],
                  "rows": [["195万円まで", "5%"], ["330万円まで", "10%"], ["695万円まで", "20%"]], "widths": [5, 3]}),
        LOOK_SEG, CTA_SEG]
    why = (f"【なぜ 30年より税金がぐっと少ないのか】\n"
           f"・枠は 800万円 ＋ 70万円 × 15年 ＝ {man(t['deduction'])}（30年より 350万円 多い）\n"
           f"・税金のかかる金額が {man(t30['taxable'])} → {man(t['taxable'])} になり、所得税の段が 10% から 5% に下がる\n"
           f"・税金 {man(t30['tax'])} → {man(t['tax'])}・手取り {man(t30['net'])} → {man(t['net'])}")
    desc = desc_for(y, t, f"退職金{A}万円を勤続35年で受け取ると、税金を引かれたあとにいくら残るかを計算しました。"
                          "所得税の段が5%まで下がる理由も出しています。", why)
    return base_script(f"{DATE}-taishokukin-2000man-35nen-short",
                       f"退職金2000万円 勤続35年の手取りは{man(t['net'])} 税金は{man(t['tax'])}まで下がります #Shorts",
                       f"勤続35年の枠は 800万円 ＋ 70万円×15年 ＝ {man(t['deduction'])}。2000万円から引いた{man(t['over'])}の半分{man(t['taxable'])}に税金がかかる。"
                       f"税金のかかる金額が195万円以下なので所得税はいちばん下の5%の段になり、税金は{man(t['tax'])}、手取りは{man(t['net'])}。",
                       desc, segs, y)


# ---------------------------------------------------------------- 38年（枠が退職金をこえる ＝ 税金 0円）
def y38():
    y, t = 38, tax(AMOUNT, 38)
    segs = [
        hook_seg(y, t, "税金は0円。1円も引かれません。"),
        prem_seg(y, ""), RULE_SEG, frame_seg(y), taxable_seg(t),
        dict(say="はみ出た分が0円なので、所得税も住民税もかかりません。",
             show="所得税も住民税も 0円", sub="はみ出た分が0円なので所得税も住民税もかからない",
             tag="計算", board=["税金のかかる金額 0円", "所得税 0円", "住民税 0円", "税金の合計 0円"],
             viz={"kind": "bars", "title": "税金 2つ", "items": [{"label": "所得税", "value": 0},
                                                             {"label": "住民税", "value": 0}],
                  "total": {"label": "税金", "value": 0}}),
        result_seg(t),
        dict(say=f"枠が退職金をこえると、税金は0円になります。{A}万円なら、{y}年ではたらいた分の枠が追いこします。",
             show=f"{y}年で 枠が追いこす", sub=f"枠が退職金をこえると税金は0円 {A}万円なら{y}年ではたらいた分の枠が追いこす",
             tag="しくみ", board=[f"枠 {man(t['deduction'])}", f"退職金 {A}万円", "枠のほうが大きい", "税金 0円"],
             viz={"kind": "bars", "title": "枠が退職金をこえる", "items": [{"label": "退職金", "value": AMOUNT},
                                                                 {"label": f"枠（{y}年）", "value": t["deduction"]}]}),
        LOOK_SEG, CTA_SEG]
    why = (f"【なぜ 0円になるのか】\n・枠は 800万円 ＋ 70万円 × 18年 ＝ {man(t['deduction'])}\n"
           f"・退職金 2000万円 より枠のほうが大きいので、はみ出た分は 0円 → 税金のかかる金額も 0円\n"
           "・所得税・住民税とも 0円。手取りは 2000万円（1円も引かれません）\n"
           "・2000万円が枠におさまる境は 勤続37年（枠1990万円）と38年（枠2060万円）のあいだです")
    desc = desc_for(y, t, f"退職金{A}万円を勤続38年で受け取ると、税金が0円になります。枠が退職金をこえるしくみを計算で出しました。", why)
    return base_script(f"{DATE}-taishokukin-2000man-38nen-short",
                       f"退職金2000万円 勤続38年なら税金は0円 手取りは2000万円のまま #Shorts",
                       f"勤続38年の枠は 800万円 ＋ 70万円×18年 ＝ {man(t['deduction'])}で、退職金2000万円より大きい。"
                       "はみ出た分が0円なので税金のかかる金額も0円で、所得税も住民税も0円。手取りは2000万円のまま1円も引かれない。",
                       desc, segs, y)


ALL = [y20, y25, y31, y35, y38]
#: どの枠に座らせるか（09/20 の `SHORT_SLOTS`・配りの実測で 07:00 がいちばん多い ＝ JOURNAL 09/18 17:0x）。
SLOTS = ["2026-09-20 07:00", "2026-09-20 10:00", "2026-09-20 12:00", "2026-09-20 15:00", "2026-09-20 18:00"]


def write(only: list[str] | None = None) -> list[dict]:
    out = []
    for f in ALL:
        d = f()
        if only and d["id"] not in only:
            continue
        SCRIPTS.mkdir(parents=True, exist_ok=True)
        json.dump(d, open(SCRIPTS / f"{d['id']}.json", "w"), ensure_ascii=False, indent=1)
        bg = IMAGES / f"{d['id']}-bg.jpg"
        if not bg.exists():
            shutil.copy(IMAGES / BG_SRC, bg)
        n = sum(len(s["say"]) for s in d["segments"])
        print(d["id"], len(d["segments"]), "コマ", n, "字", "max say", max(len(s["say"]) for s in d["segments"]))
        out.append(d)
    return out


if __name__ == "__main__":
    write(sys.argv[1:] or None)
