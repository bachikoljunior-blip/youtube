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

from . import asp

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
             "目": "め", "方": "かた", "中": "なか", "大": "おお", "境目": "さかいめ",
             "負担": "ふたん", "軽": "かる", "復興分": "ふっこうぶん",
             # 15年 のコマ8（2026-09-19 15:5x）。`lint` が「読みが固定されていない」と鳴った語。
             "手前": "てまえ"})


def frame_text(y: int) -> tuple[str, int]:
    """その年数の枠の出し方（声で言う1文）と枠の額。"""
    d = deduction(y)
    if y <= 20:
        return f"1年40万円かける{y}年で、枠は{man(d)}です。", d
    # **文は 40字 まで**（METHOD §3 の 6・`lint` が [?] で鳴る）＝ 読点ではなく句点で切る。
    return f"20年までで800万円。こえた{y - 20}年ぶんが{man(700_000 * (y - 20))}。枠は{man(d)}です。", d


def prem_seg(y: int, tail: str) -> dict:
    return dict(say=f"たとえば、{y}年はたらいて退職。退職金は{A}万円。{tail}",
                show=f"{y}年はたらいた", sub=f"たとえば同じ会社で{y}年はたらいて退職 退職金は{A}万円（一度に受け取る）",
                tag="前提", board=["同じ会社で", f"{y}年はたらいた", f"退職金 {A}万円", "一度に受け取る"])


#: **`series_taishoku` の同名を継がずに、この連作の中で書き直したもの**（2026-09-18 21:0x）。
#: 継ぐと 09/19 に上げた 4本 の `build_sig` が動きます（上げ直し 1本 1,650単位）。
#: 直した理由は `critique` の [real]（同刻・`2026-09-20-...-20nen-short` に撃った）:
#:  (1) コマ6「税率20%の段で78万8700円」＝ **600万 × 20% は 120万 で、78万8700円 の出どころが本文に無い**
#:      → **声（掛け算と引き算）と 画面の表（3段の率と引く額）の両方**。
#:        この 1件 は 4周 とも立ち、**置き場所を 2度 入れ替えて数えました** ——
#:        決めと数は `tax_seg` の註（1か所）。ここでは繰り返しません
#:  (2) コマ5「まとめた収入なので半分にだけ税金」＝ **なぜ半分になるのかが無い** → 制度の目的を1文
#:  (3) コマ1〜3 に「何と何をくらべるか」の宣言が無く、コマ8 で突然 比べる表が出る → フックで宣言する
#: **字を足したぶんは、この 3つ を短くして返しています**（連作は 450字 まで ＝ METHOD §31）。
#: **「なぜ半分か」は、数が出るより前に言うこと**（`critique` の 2周目 [real]・2026-09-18 21:1x）。
#: 1周目の直しは コマ5 に「負担を軽くするため」と足しましたが、**それは目的で、しくみではない**と返ってきました。
#: しくみは「何年分もためたお金を 1年の収入として計算すると率が上がるので、半分にして均す」——
#: **その一言を コマ3（決まり）へ移すと、コマ5 は数だけになり、字も 23字 返ってきます。**
RULE_SEG = dict(
    say="決まりでは、退職金には税金のかからない枠があり、年数で決まります。何年分もためたものなので、はみ出た分の半分だけに税金がかかります。",
    show="枠は年数で決まる", sub="退職金には税金のかからない枠があり年数で決まる 何年分もためたものなのではみ出た分は半分にして計算する",
    tag="決まり", board=["税金のかからない枠", "年数で決まる", "20年まで 1年40万円", "こえた分 1年70万円", "はみ出た分は半分"],
    viz={"kind": "table", "title": "枠は年数で決まる", "head": ["はたらいた年数", "1年ごとにふえる枠"],
         "rows": [["20年まで", "40万円"], ["20年をこえた分", "70万円"]], "widths": [4, 4]})


#: `series_taishoku` の CTA を短くしたもの（この連作の中だけ。継ぐと 09/19 の 4本 の `build_sig` が動く）。
# **2026-09-19 08:xx: 指す先を「説明欄」から「プロフィールのリンク」へ**（Shorts では説明欄・コメント欄の URL が
# 押せない ＝ YouTube 2023-08-31。理由・覆る条件は `studio/asp.py` の `PROFILE_NOTE` の註 ＝ **門は 1か所**）。
CTA_SEG = dict(asp.CTA_SEG)

#: `series_taishoku.LOOK_SEG` を短くしたもの（同じ理由 ＝ 継ぐと 09/19 の 4本 が動く）。
LOOK_SEG = dict(
    say="自分の枠は年数で決まります。税金は退職所得の源泉徴収票にあります。",
    show="退職所得の源泉徴収票", sub="自分の枠ははたらいた年数で決まる 引かれた税金は会社からもらう退職所得の源泉徴収票に書いてある",
    tag="見る所", board=["自分の枠は", "はたらいた年数で決まる", "退職所得の源泉徴収票", "引かれた税金が書いてある"])


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
    # **「なぜ半分か」は コマ3 で言いました**（上の RULE_SEG の註）＝ ここは数だけ。
    return dict(say=f"枠を引くと{man(over)}がはみ出ます。半分の{man(half)}に税金がかかります。",
                show=f"税金がかかるのは {man(half)}",
                sub=f"{A}万円から枠{man(d)}を引くと{man(over)}がはみ出る 半分の{man(half)}にだけ税金がかかる",
                tag="計算", board=[f"退職金 {A}万円", f"− 枠 {man(d)}", f"＝ はみ出た分 {man(over)}", "半分にだけ税金", f"＝ {man(half)}"],
                viz={"kind": "table", "title": "税金がかかる金額",
                     "rows": [["退職金", f"{A}万円"], ["− 枠", man(d)], ["＝ はみ出た分", man(over)], ["半分にだけ税金", man(half)]],
                     "widths": [4, 4]})


def _bracket_rows(taxable: int) -> list[list[str]]:
    """速算表の段（`[税金のかかる金額, 率, 引く額]`）—— **はじめの3段 ＋ この人の段**。

    この人の段が はじめの3段 の中なら 3行 のまま（＝ 既に焼いた本の `build_sig` は動かない）。
    """
    rows = [[f"{man(hi)}まで", f"{int(round(r * 100))}%", man(s) if s else "0円"]
            for hi, r, s in BRACKETS[:3]]
    for i, (hi, r, s) in enumerate(BRACKETS):
        if taxable <= hi:
            if i >= 3:
                rows.append([f"{man(hi)}まで", f"{int(round(r * 100))}%", man(s) if s else "0円"])
            break
    return rows


def tax_seg(t: dict) -> dict:
    pct = int(round(t["rate"] * 100))
    sub = next(s for hi, r, s in BRACKETS if t["taxable"] <= hi)
    # **掛け算と引き算を声に入れます**（`critique` を 4周 回して数えた・2026-09-18 21:2x）。
    # **METHOD §34 は「声から外す」と決めていました**が、それは**額の側の連作で 3周 回した数**です。
    # この連作で 4周 数え直したら、**向きが逆に出ました**:
    #     声に無い（1周目・4周目）  → **[real] 2回**（「600万 × 20% は 120万 のはずで、計算が合わないように見える」）
    #     声に在る（2周目・3周目）  → **[real] 1回**（「なぜこの率とこの引く額なのか」＝ 累進そのもの）＋ **[nitpick] 1回**
    # ＝ **在るほうが弱い傷で済みます。** 無いほうの傷は「数が合っていない」に見える側で、
    # **このチャンネルの売り物（数が合っていること）に直に当たります。**
    # 残る [real]（なぜこの引く額か）は 450字 では答えられない側 ＝ 長尺の仕事（§34 と同じ結論）。
    # **覆る条件**: 5周目 が「声に在る」形で **[real] を 2件 以上** 立てたら、この行を §34 へ戻すこと。
    head = (f"{man(t['taxable'])}の{pct}%は{man(int(t['taxable'] * t['rate']))}。表の{man(sub)}を引いて、所得税は{man(t['income_tax'])}。"
            if sub else f"所得税は{man(t['taxable'])}の{pct}%に復興特別所得税を入れて{man(t['income_tax'])}。")
    return dict(
        say=head + f"住民税は10%で{man(t['resident_tax'])}です。",
        show=f"所得税 {man(t['income_tax'])}",
        sub=head + f"住民税は{man(t['taxable'])}の10%で{man(t['resident_tax'])}",
        tag="計算", board=[f"{man(t['taxable'])} の {pct}%", f"− {man(sub)}", "＋ 復興特別所得税",
                          f"所得税 {man(t['income_tax'])}", f"住民税 {man(t['resident_tax'])}"],
        # **率と引く額の出どころは、声ではなく画面で渡す**（`critique` の 2周目 [real]
        # 「なぜこの税率でこの控除額なのか説明がない」・オーナー 09/10 12:4x「画面を有効活用できてない」）。
        # 450字 の連作では、速算表のしくみを声で足すと 他のコマを削ることになります ——
        # **表なら 0字 で渡せます**（段ごとの率と引く額を並べ、この人の段が分かる形）。
        # **段は「はじめの3段 ＋ この人の段」**（2026-09-19 15:5x に字を式へ替えた）。
        # もとは 3段 を字で持っており、**この人の段が表に無い本を作れました** ——
        # 勤続15年（税金のかかる金額 700万円 ＝ 23%の段）は 695万円 を越えるので、
        # 表の3段 のどれにも当たらず、**声が言う「63万6000円を引いて」の出どころが画面から消えます**。
        # 既に焼いた 5本（20/25/31/35年・どれも 695万円 以下）は **3段 のまま** ＝ `build_sig` は動きません。
        # **覆る条件**: 税金のかかる金額が 900万円 を越える本を書いたら段が 5行 になる ——
        # `lint` の行数の門に当たったら、そこで「この人の段の前後 1段 ずつ」へ畳むこと。
        viz={"kind": "table", "title": "所得税の速算表（この人の段）",
             "head": ["税金のかかる金額", "率", "引く額"],
             "rows": _bracket_rows(t["taxable"]), "widths": [5, 2, 4]})


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
        # **フックは「結論」、コマ2 は「何とくらべるか」**（`critique` 3周目 の [real] (1)）——
        # 1周目 は結論だけ・2周目 は宣言だけにしたら、**どちらの周も同じ所に [real] が立ちました**
        # ＝ 要るのは片方ではなく **2つ を別のコマに置くこと**。フックに両方 入れると 70字 を越えます。
        hook_seg(y, t, f"21年なら税金が{man(diff)}へります。"),
        prem_seg(y, "同じ金額で年数だけ変えます。"), RULE_SEG, frame_seg(y), taxable_seg(t), tax_seg(t), result_seg(t),
        # **途中式を声に入れる**（`critique` 1周目 の [real] (4)）—— 枠 +70万 → かかる金額 −35万 → 税金 −10万6500円。
        # **「線」は 3周目 に [real]**（「初めて聞く人には抽象的」）＝ 「境目」へ。
        dict(say=f"20年が境目です。21年目は枠が70万円ふえます。半分にすると税金のかかる金額は35万円へり、税金は{man(diff)}へります。",
             show="20年が境目", sub=f"20年が境目 21年目から枠が70万円ふえて税金のかかる金額が35万円へり 税金は{man(diff)}へる",
             tag="しくみ", board=["20年が境目", "20年までは 1年40万円", "21年目から 1年70万円", f"税金 −{man(diff)}"],
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


# ---------------------------------------------------------------- 15年（**壁の手前 ＝ 枠の伸びが 40万円**）
#
# **【2026-09-19 15:5x・optimizer・Opus 5・1周 1体】6本目 として足しました。**
# **なぜ**: `SHORT_SLOTS` は 09/19 12:xx に **6枠** になったのに、連作の生成器は 5本 のままでした
# （この file の 09/19 12:xx の註が「21:00 が 1枠 空きます。何を座らせるかは立った側が決めること」と
#  名指しした当の穴）。**21:00 は 3日 続けて空いています** ＝ 出せる本が 枠より 1本 少ない日が続く形です。
# 6本/日 は `budget.day_upload_cap()` の天井で、**固定2（期限内に届くか）の分母そのもの**です
# （`trend.ungated_yen`／`perf_need_rate` が「日枠が戻って 6本/日 なら 0.9倍／0.3倍」と言う当の 6）。
# ＝ **枠を 6 にして生成器を 5 のままにすると、その 6 は帳の上だけの数になります。**
#
# **なぜ 15年 か**（他の候補を落とした理由 —— 同じ所をもう一度 測らないために書きます）:
#   40年  枠 2200万円 → 税金 0円 ＝ **38年 と落ちが同じ**（`CLAUDE.md` (B)「同じことを言う本」）
#   30年  枠 1500万円 ＝ **`series_taishoku` の基準そのもの**で、09/19 に公開ずみの
#         `2026-09-19-taishokukin-2000man-tedori-short`（2000万円・勤続30年）と**同じ本**になります
#   5年以下 は 短期退職手当等（2分の1 が 300万円 までに制限）＝ **`series_taishoku.tax` が持たない式**
#         ＝ 数を新しく作ることになり、この連作の前提（「数を 1つ も新しく作らない」）を破ります
#   **15年 は `tax()` をそのまま呼べて**（40万円 × 15年 ＝ 枠600万円）、落ちが他の 5本 のどれとも違います。
#
# **コマ8（しくみ）は 20年 の裏返しです**（file 冒頭「年数ごとに効いている線が違う」）——
# 20年 の本は「壁をこえると 70万円」を**こえた側**から見ます。この本は**手前の側**から見ます:
# **同じ5年でも、壁の手前は 200万円・こえた後は 350万円**。20年 の本が持っていない数です。
def y15():
    y, t = 15, tax(AMOUNT, 15)
    t20, t25 = tax(AMOUNT, 20), tax(AMOUNT, 25)
    up15, up20 = t20["deduction"] - t["deduction"], t25["deduction"] - t20["deduction"]
    segs = [
        hook_seg(y, t, "20年はたらいた人とくらべます。"),
        prem_seg(y, ""), RULE_SEG, frame_seg(y), taxable_seg(t), tax_seg(t), result_seg(t),
        # **小数を声に出さない**（オーナー 2026-09-06「点って言ってるとこ」）＝ 「1.75倍」とは言いません。
        # 200万円 と 350万円 を並べるだけで、差は画面の表が持ちます。
        dict(say=f"20年の手前は1年40万円です。あと5年はたらくと枠は{man(up15)}ふえます。"
                 f"20年をこえた5年なら{man(up20)}ふえます。",
             # 板の `show` は 16字 まで（`lint`）。「同じ5年で 200万円 と 350万円」は 19字。
             show=f"5年で {man(up15)}と{man(up20)}",
             sub=f"20年の手前は1年40万円 あと5年はたらくと枠は{man(up15)}ふえる 20年をこえた5年なら{man(up20)}ふえる",
             tag="しくみ", board=["20年の手前 1年40万円", f"15年→20年 ＋{man(up15)}", f"20年→25年 ＋{man(up20)}",
                                "同じ5年でも ちがう"],
             viz={"kind": "table", "title": "同じ5年でふえる枠", "head": ["はたらいた年数", "枠", "5年でふえた分"],
                  "rows": [["15年", man(t["deduction"]), ""], ["20年", man(t20["deduction"]), f"＋{man(up15)}"],
                           ["25年", man(t25["deduction"]), f"＋{man(up20)}"]], "widths": [4, 3, 4]}),
        LOOK_SEG, CTA_SEG]
    why = (f"【なぜ 20年の手前だと枠が小さいのか】\n"
           f"・枠は 20年までが 1年40万円、20年をこえた分が 1年70万円（No.1420）\n"
           f"・15年 → 20年 の5年でふえる枠は 40万円 × 5年 ＝ {man(up15)}\n"
           f"・20年 → 25年 の5年でふえる枠は 70万円 × 5年 ＝ {man(up20)}（同じ5年でも {man(up20 - up15)} 多い）\n"
           f"・15年の枠 {man(t['deduction'])} → 20年 {man(t20['deduction'])}・"
           f"税金 {man(t['tax'])} → {man(t20['tax'])}・手取り {man(t['net'])} → {man(t20['net'])}")
    desc = desc_for(y, t, f"退職金{A}万円を勤続15年で受け取ると、税金を引かれたあとにいくら残るかを計算しました。"
                          "20年はたらいた人との差も出しています。", why)
    return base_script(f"{DATE}-taishokukin-2000man-15nen-short",
                       f"退職金2000万円 勤続15年の手取りは{man(t['net'])} 税金は{man(t['tax'])} #Shorts",
                       f"勤続15年の枠は 40万円×15年 ＝ {man(t['deduction'])}。2000万円から引いた{man(t['over'])}の半分{man(t['taxable'])}に税金がかかり、"
                       f"税金は{man(t['tax'])}、手取りは{man(t['net'])}。20年まであと5年で枠は{man(up15)}ふえるが、"
                       f"20年をこえた5年なら{man(up20)}ふえる。",
                       desc, segs, y)


ALL = [y15, y20, y25, y31, y35, y38]
#: どの枠に座らせるか（`DATE` の `cli.SHORT_SLOTS`・配りの実測で 07:00 がいちばん多い ＝ JOURNAL 09/18 17:0x）。
#:
#: **【2026-09-19 15:5x】刻を字で持つのをやめ、`cli.SHORT_SLOTS` から引くようにしました。**
#: 12:xx に枠が 5→6 になったとき、**動いたのは `cli.SHORT_SLOTS` だけで、この写しは 5 のまま**でした
#: ＝ 21:00 が 3日 続けて空いた形の片側です（もう片側は `ALL` が 5本 だったこと ＝ `y15` の註）。
#: **写しを作らないこと**（METHOD §5 の教訓 7つ目・`SLOT_AT` と同じ）。
#: **覆る条件**: 連作の本数と枠の数がずれたら（`ALL` ≠ `SHORT_SLOTS`）`write()` が鳴らします。
def slots() -> list[str]:
    from .cli import SHORT_SLOTS
    return [f"{DATE} {hhmm}" for hhmm in SHORT_SLOTS]


SLOTS = slots()


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
