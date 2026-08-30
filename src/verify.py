"""投稿前の検査。

無人で本番チャンネルに出すので、生成物が壊れていないかを確認してから投稿する。
1つでも外れたら投稿しない。壊れた動画が上がるより、その日1本落ちるほうがいい。

**ここに何を足すかの基準。** 実際に壊れて、しかも機械が素通りしたものを足す。
思いつきの網羅ではない。これまでの故障はすべて「誰も見ていなかったもの」で、
フレームを抜いて目で見たときにだけ見つかっている。目視が抜けるのは注意力の
問題ではなく手間の問題なので、**手間のかからない側（機械）に寄せる**のが筋。

機械で見られないものは `scripts/inspect_build.py` が1枚にまとめる。そちらは最後の砦で、
ここに書けるものをそちらに残さないこと。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import narrated
from . import forms
from . import frames
from .subtitles import _NUM_TOKEN, _is_katakana
from .util import require, run
from .yomi import remaining_risks

# サムネイルの上限（YouTube）と、いつも作っている寸法
THUMB_MAX_BYTES = 2_000_000
THUMB_SIZE = (1280, 720)
# 実測: 公開済み7本は 39.8 以上、単色は 0.0。あいだに置く。
THUMB_MIN_STDDEV = 12.0
# 量産テンプレート判定を避けるための下限。CLAUDE.md「この作りの根幹」より。
MIN_CHARTS = 3
# 過去の動画と何本の棒が共通なら「同じ図」とみなすか。
# 切り口が違えば共通は0〜1本（同じ金額の偶然はある）。実例で2本以上に置いた。
REPEAT_BARS = 2


class VerificationError(RuntimeError):
    pass


def _probe(path: Path) -> dict:
    require("ffprobe")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise VerificationError(f"ffprobe が読めませんでした: {proc.stderr[:300]}")
    return json.loads(proc.stdout)


def _check_thumbnail(work: Path) -> list[str]:
    """サムネイルは一度も検査されておらず、一度も見られないまま2本壊れて公開された。"""
    thumb = work / "thumbnail.jpg"
    if not thumb.exists():
        return ["サムネイルが作られていない"]

    problems = []
    size = thumb.stat().st_size
    if size > THUMB_MAX_BYTES:
        problems.append(f"サムネイルが {size} バイトで上限の {THUMB_MAX_BYTES} を超えている")
    try:
        from PIL import Image, ImageStat

        with Image.open(thumb) as img:
            if img.size != THUMB_SIZE:
                problems.append(f"サムネイルが {img.size} で、期待は {THUMB_SIZE}")
            spread = min(ImageStat.Stat(img.convert("RGB")).stddev)
        # バイト数ではなく画素のばらつきで見る。バイト数は圧縮率の話で、
        # 中身が空かどうかの話ではない。実測では本物が 39.8 以上、単色が 0。
        if spread < THUMB_MIN_STDDEV:
            problems.append(
                f"サムネイルの画素のばらつきが {spread:.1f} しかなく、ほぼ単色に見える"
            )
    except Exception as exc:
        problems.append(f"サムネイルを開けない: {exc}")
    return problems


def _check_subtitles(work: Path) -> list[str]:
    """字幕は「。」だけの行と、数字の途中での改行で壊れた。どちらも機械で見える。"""
    ass = work / "subtitles.ass"
    if not ass.exists():
        return []

    # Dialogue の書式は Layer..Effect の9項目のあとに本文。本文にも読点が入るので
    # カンマで9回だけ割る。`,,` を目印にすると Name と Effect の両方に当たる。
    rows = [
        row[len("Dialogue:"):].split(",", 9)
        for row in ass.read_text(encoding="utf-8").splitlines()
        if row.startswith("Dialogue:")
    ]
    rows = [r for r in rows if len(r) == 10]
    lines = [r[9].strip() for r in rows]
    if not lines:
        return ["字幕に1行も入っていない"]

    problems = []
    orphans = [t for t in lines if t and not re.search(r"[^\s。、！？…・]", t)]
    if orphans:
        problems.append(f"記号だけの字幕行が {len(orphans)} 行ある（例『{orphans[0]}』）")

    # 行末と次の行頭が両方とも数字・単位なら、かたまりの途中で割れている。
    #
    # **ただし、隣り合う2行が同じ文から折れたものであるときだけ。**
    # 2026-08-15、『手取り増は35万9318円』→『13%なら』で止まりました。
    # **これは折り返しではなく、文の終わりと次の文の始まりです。**
    # 別々の数字が並んでいるだけで、画面上は何も壊れていません。
    # それでも検査は落とし、その回は投稿を1本ぶん失いました
    # （生成し直しても、文の並びが同じなら**必ず再発します**）。
    #
    # 文の切れ目は `subtitles.build` が Name の欄（`seg<番号>`）に刷ります。
    # **欄が空なら、繋げて読む昔のふるまいに戻す**（見落とすより止めるほうを選ぶ）。
    names = [r[4].strip() for r in rows]
    same_sentence = [
        (not x) or (not y) or x == y for x, y in zip(names, names[1:])
    ]
    split_nums = [
        (a, b) for a, b, same in zip(lines, lines[1:], same_sentence)
        if same and a and b and a[-1] in _NUM_TOKEN and b[0] in _NUM_TOKEN
    ]
    if split_nums:
        a, b = split_nums[0]
        problems.append(f"数字の途中で改行している箇所が {len(split_nums)} 件（『{a}』→『{b}』）")

    # **カタカナの語の途中でも割れる。** 2026-08-15、
    # 『残る割合は73.5パーセン』→『トから70.3パーセントへ』が出ました。
    # `subtitles._best_cut` は「カタカナの連続の途中では割らない」と書いてあるのに、
    # **良い切れ目が1つも無いときの最後の1行が、その規則を踏み越えていました。**
    # 直しても、ここで見ていなければ次に同じ形で戻ってきます
    # （数字の割れは見ていたのに、カタカナだけ抜けていた）。
    split_kata = [
        (a, b) for a, b, same in zip(lines, lines[1:], same_sentence)
        if same and a and b and _is_katakana(a[-1]) and _is_katakana(b[0])
    ]
    if split_kata:
        a, b = split_kata[0]
        problems.append(
            f"カタカナの語の途中で改行している箇所が {len(split_kata)} 件（『{a}』→『{b}』）"
        )
    return problems


# ショートで、1枚の絵が画面に出ていてよい秒数の上限。
# 2026-08-05、53秒のショートが**絵3枚**で、1枚あたり16〜20秒静止していた。
# 長尺には chart 3枚の下限があるが、ショートには枚数の規定が無く素通りしていた。
# 「同じ絵が続く」ことがポリシー上の反復判定に当たるのは、尺に関係なく同じ。
MAX_SECONDS_PER_SLIDE = 12.0
# ショート全体の上限（秒）。**1枚あたりの上限だけでは全体を縛れない。**
# 2026-08-09、12枚に分かれた2分0秒のショートが「合格」で通った。
# 1枚ずつは12秒以内だったので、どの検査にも引っかからなかった。
MAX_SHORT_SECONDS = 70.0
# **1枚の絵が、変わらないまま画面に出ていてよい秒数**（ショート）。
# 上の MAX_SECONDS_PER_SLIDE（12秒）とは別のつまみです。あちらは
# `尺 ÷ 文の数` という平均で、**割れなかった1枚は平均に埋もれます。**
#
# 置き方: `src/script_writer.py` の実測で **離脱は 4.7〜5.7秒**に来ます。
# その帯より前に画面が変わっていなければ、変わった意味がありません。
# いっぽう `pipeline.SHORT_SLIDE_SECONDS` は 2.5秒 を狙っていて、
# stat を割れるようにした後の実測は **最長 2.9秒**（`s-tedori-2`）。
# 5.0 は「狙いの倍あっても通る」「離脱の帯には届かせない」の あいだ。
# **投稿を止めるための数字ではありません**（止まるのが最大の損失）。
MAX_SECONDS_PER_PICTURE = 5.0


def _check_slide_hold(work: Path, duration: float) -> list[str]:
    """**1枚ずつ**、変わらないまま何秒出ているかを見る。

    2026-08-15、`s-tedori-2` の `kind=stat` は割る列が無くて1枚のまま
    **5.8秒**止まっていました。`_check_short_pace` は 30秒 ÷ 6文 = 5.0秒 と読み、
    上限12秒を悠々と通しています。**平均は、いちばん悪い1枚を隠します。**

    しかも止まっていたのは**冒頭**でした（`_check_short_opening` が
    1枚目を stat に縛っているので、stat はたいてい先頭に来る）。
    離脱が 4.7〜5.7秒 に来るなら、**動かしたい区間だけが動いていなかった**ことになります。

    秒数は `pipeline` が `slide_seconds.json` に書きます。**無ければ何も言いません**
    （長尺や、古い build を後から検査する場合）。
    """
    path = work / "slide_seconds.json"
    if not path.exists() or duration <= 0:
        return []
    try:
        seconds = [float(x) for x in json.loads(path.read_text(encoding="utf-8"))]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return [f"slide_seconds.json が読めない: {exc}"]
    if not seconds:
        return []
    worst = max(seconds)
    if worst <= MAX_SECONDS_PER_PICTURE:
        return []
    where = seconds.index(worst)
    head = "**冒頭の**" if where == 0 else f"{where + 1}枚目の"
    return [
        f"{head}絵が {worst:.1f}秒 変わらないまま出ている"
        f"（上限 {MAX_SECONDS_PER_PICTURE:.1f}秒 / 全{len(seconds)}枚）。"
        "**離脱は 4.7〜5.7秒 に来ます。**"
        "`visuals.reveal_variants` が割れる形（bars・rows・items、"
        "または stat＋note）にすること"
    ]


#: **完成した図が画面に残らなければならない秒数**（2026-08-27 に足した）。
#: `src/pipeline.SHORT_SLIDE_SECONDS` と同じ 2.5秒。**別の数にしないこと** ——
#: あちらが割り当て、こちらが確かめる、同じ1つの約束です。
MIN_COMPLETE_SECONDS = 2.5


def _check_reveal_hold(work: Path) -> list[str]:
    """**説明している図が、説明のあいだ画面に居るか。**（2026-08-27）

    ## なぜ要るか（オーナーの指摘）

    > **「動画についてまず何言ってるか分かんないね。音声だけで理解できない
    > 説明なのに画面はすぐ切り替わるし。説明を理解するにはかなり視聴者側の
    > 推論が必要だと思う。」**

    このファイルの速さの検査は、2026-08-27 まで**全部が上限**でした:

        MAX_SECONDS_PER_PICTURE = 5.0    1枚が止まってよい上限
        MAX_SECONDS_PER_SLIDE  = 12.0    1文あたりの上限
        MAX_SHORT_SECONDS      = 70.0    尺の上限

    **下限は1つもありません。** 0.3秒 のコマは全部 通ります。そのうえ、
    上限に落ちたときの文言は「**セグメントを増やして画を動かすこと**」
    「`reveal_variants` が割れる形にすること」で、**速いほうへ押しています。**
    つまりオーナーが見た形は、検査を通った結果ではなく、**検査が作った形**です。

    `reveal_variants` は図を「要素を1つずつ足す」コマ列に割り、
    **完成形は最後の1コマにしかありません。** 等分だと、6秒の文は
    3コマ × 2秒 で、**完成形が居るのは最後の2秒**です。読み上げが
    その図について話しているあいだ、画面には未完成の図しかありません。

    ここで見るのは1つだけ ——
    **各文の完成形が `MIN_COMPLETE_SECONDS` 以上 画面に残っているか。**

    `slide_complete.json` が無ければ何も言いません（長尺・古い build）。

    **覆る条件**: 完成形を長く置くほうが `engaged` を下げると実測で出たとき
    （`config/hypotheses.yaml` の `reveal_hold` が測っています）。
    """
    secs_path, idx_path = work / "slide_seconds.json", work / "slide_complete.json"
    if not secs_path.exists() or not idx_path.exists():
        return []
    try:
        seconds = [float(x) for x in json.loads(secs_path.read_text(encoding="utf-8"))]
        idx = [int(x) for x in json.loads(idx_path.read_text(encoding="utf-8"))]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return [f"slide_complete.json / slide_seconds.json が読めない: {exc}"]
    short = [(i, seconds[i]) for i in idx
             if 0 <= i < len(seconds) and seconds[i] + 1e-6 < MIN_COMPLETE_SECONDS]
    if not short:
        return []
    worst = min(short, key=lambda p: p[1])
    return [
        f"**説明の相手の図が {worst[1]:.1f}秒 で消えている**"
        f"（下限 {MIN_COMPLETE_SECONDS:.1f}秒 / 該当 {len(short)}文 / 全{len(idx)}文）。"
        "`reveal_variants` の**完成形**は最後の1コマにしかないので、"
        "ここが短いと**読み上げが説明しているあいだ、画面に完成形がありません**。"
        "`pipeline.reveal_durations` が割り当てます —— "
        "**等分に戻っていないか**を見ること"
    ]


def _check_short_pace(script: dict | None, duration: float) -> list[str]:
    """ショートで同じ絵が長く止まりすぎていないか。

    **枚数ではなく「1枚あたり何秒か」で見る。** 枚数の下限を置くと尺が変わった
    ときにずれる。見たいのは「見ている側にとって画が止まって見えるか」なので、
    秒で持つほうが素直。

    落ちたら作り直し。ショートの作り直しは数分で済む。
    """
    if not script or duration <= 0:
        return []
    segments = script.get("segments") or []
    if not segments:
        return []
    problems = []
    if duration > MAX_SHORT_SECONDS:
        problems.append(
            f"ショートが {duration:.0f}秒 で長すぎる"
            f"（上限 {MAX_SHORT_SECONDS:.0f}秒）。**1本＝1つの計算結果に絞ること**"
        )
    per = duration / len(segments)
    if per > MAX_SECONDS_PER_SLIDE:
        return problems + [
            f"1枚あたり {per:.0f}秒 で絵が止まりすぎている"
            f"（{duration:.0f}秒 / {len(segments)}枚、上限 {MAX_SECONDS_PER_SLIDE:.0f}秒）。"
            "セグメントを増やして画を動かすこと"
        ]
    return problems



def _check_not_repeat(work: Path, script: dict | None) -> list[str]:
    """**過去の動画と同じ図を出していないか。**

    2026-08-07、年金の繰上げショートが、2日前の繰下げショートと
    「ぼかし背景＋2行タイトル → 巨大数字 → 開始年齢べつの横棒 → この計算の前提
    → 横棒 → リスト」という構成まで同じで、**見出しの文言も一致**していた。
    さらに末尾の chart は **180万/255万6千円/331万2千円 と前回と同じ数値の再掲**。
    違いは配色だけだった。

    YouTube は「同じチャンネルの動画を続けて数本視聴した後、繰り返しのように
    感じられる可能性のあるコンテンツ」を収益化の対象外にしている。
    **収益化されなければ収入はゼロ**なので、これは見栄えの話ではない。

    見るのは **chart の数値の集合**。見出しの文言は「この計算の前提」のように
    毎回入れるべき定型があるので、そこで判定すると本末転倒になる。
    chart は計算結果そのものなので、**切り口が本当に違えば数値も変わる。**

    **「丸ごと一致」では捕まらなかった。** 実際の繰上げの図は
    `['136万8千円','180万円','255万6千円','331万2千円']` で、前回の
    `['180万円','255万6千円','331万2千円']` に**1本足しただけ**。
    タプルの完全一致では通り抜ける。**棒の集合の重なりで見る。**

    しきい値は実例で決めた。切り口が本当に違えば共通の棒は0〜1本
    （同じ金額がたまたま出ることはある）。**2本以上共通なら同じ図。**
    """
    if not script:
        return []
    def charts(sc: dict) -> list[tuple]:
        out = []
        for seg in sc.get("segments") or []:
            v = seg.get("visual") or {}
            if v.get("kind") == "chart" and v.get("bars"):
                out.append(tuple(str(b.get("display", "")) for b in v["bars"]))
        return out

    mine = charts(script)
    if not mine:
        # **0枚を「比較するものが無いので合格」にしていた。**
        #
        # 2026-08-10、`s-shitsugyo-4` が **chart 0枚**で通った。
        # ショートは `_check_slides` に script を渡していない（下限を当てない
        # 設計にしてある）ので、**枚数の検査はどこにも無く、
        # この重複検査も `mine` が空だと黙って `[]` を返していた。**
        # つまり **chart を1枚も作らなければ、重複検査ごと消える。**
        #
        # 検査を通すいちばん簡単な方法が「検査対象を作らないこと」になっていた。
        # **これは0枚を許すかどうかの話ではなく、guard が自分で外れる話。**
        #
        # ショートに3枚は多い（1本＝1つの計算結果）。だが **0枚は別**で、
        # 図が1枚も無ければ全部が文字の板になり、
        # 「テンプレートを使用して作成されたと思われるコンテンツ」そのものになる。
        # 公開済みショートは全部1〜3枚入っている。**0枚は前例が無い。**
        return ["chart が0枚。**棒の長さが計算結果そのものなので、"
                "1枚も無いと図が毎回同じ形になる**（量産テンプレート判定の側）。"
                "さらに chart が無いと**過去との重複検査そのものが働かない**"]

    # 比較する相手を2つの出どころから集める。
    #
    # **`build/` だけでは足りない。** `.gitignore` に入っているので
    # 新しいコンテナでは空になり、**この検査は比較0件で黙って通る**
    # （2026-08-09 に気づいた。詳しくは `src/bars.py` の冒頭）。
    # 公開済みのぶんは `data/published_bars.json` から取る。こちらが本命で、
    # `build/` は「まだ公開していないが今日作ったもの」を捕まえるための補助。
    from . import bars

    past_charts: list[tuple[str, list[list[str]]]] = [
        (f"{tid}（公開済み）", ch) for tid, ch in bars.published_charts(exclude=work.name).items()
    ]
    for other in sorted((work.parent).glob("*/script.json")):
        if other.parent.name == work.name:
            continue
        try:
            past = json.loads(other.read_text(encoding="utf-8"))
        except Exception:
            continue
        past_charts.append((other.parent.name, [list(c) for c in charts(past)]))

    problems = []
    for name, other_charts in past_charts:
        # 1つの相手につき1件だけ報告する。同じ相手で何枚も当たっても、
        # 直すべきことは「切り口を変える」の1つなので、並べても長くなるだけ。
        hit = next(
            (
                set(a) & set(b)
                for a in mine
                for b in other_charts
                if len(set(a) & set(b)) >= REPEAT_BARS
            ),
            None,
        )
        if hit:
            problems.append(
                f"図の棒が `{name}` と {len(hit)}本 共通"
                f"（{'・'.join(sorted(hit)[:3])}…）。"
                "**同じ図を出している。** 切り口を変えるか、別の計算結果を出すこと"
            )
    return problems


#: 式に使える演算子。`-` と `−`（U+2212）と `ー`（長音）は見分けが付かない場面が
#: あるので全部受ける。`=` は別に必須なので、ここには入れない。
# **全角も受けること**（2026-08-18 に実物で踏んだ）。1行下の `=` の検査は
# `=` と `＝` の両方を見るのに、こちらは半角だけを見ていました。
# **台本の書き手は `＝` と書くので、隣に置く記号も全角になります** ——
# `59万7200円 ＝ 5万8200円 ＋ 53万9000円` が「演算子が無い」で弾かれ、
# 書き直しを1回まるごと使いました。**幅がそろっていないだけで、欠陥は式の側にありません。**
_OPS = "×÷+*/-−ー―＋－＊／"


def _check_formula_shown(script: dict | None) -> list[str]:
    """**計算式が画面に出ているか。**

    `CLAUDE.md` の根幹は「**前提と計算式を、画面と説明欄に全部出す**」で、
    前提の置き方そのものが独自の視点であり、**視聴者が自分で追試できること**が
    テンプレート量産との違いになる、と書いてある。

    ところが 2026-08-15 の独立評価で、意図を渡していない3体が独立に
    「**計算式が画面に出ていない**」と書いた。実際そのとおりで、
    画面に出ていたのは**前提だけ**だった。**根拠が半分欠けていた。**

    前提だけでは追試できない。「年収600万・扶養なし」を見せられても、
    そこから 35万9318円 がどう出たかは分からない。
    **式が無いと、こちらが計算した証拠が画面のどこにも無い。**
    それは「自分で作成していない資料の読み上げ」と、画面上は区別が付かない。

    見るのは3つ。**式であることだけを見て、値の正しさは見ない**
    （値の出どころは `_check_headline_from_calc` が calc を実行して見る。
    こちらは台本だけで判定できるので `short_script_problems` からも呼べる ——
    落とすのがレンダリングの後ではなく**生成中**になる）。

    1. `formula` を持つ画面が**1本に最低1枚**
    2. その式に `=` がある（`800万円` と数字を再掲しただけのものを落とす）
    3. 演算子が1つ以上ある（`合計 = 35万9318円` は式ではなく言い換え）
    """
    if not script:
        return []
    segs = script.get("segments") or []
    if not segs:
        return []

    found: list[tuple[int, str]] = []
    problems: list[str] = []
    for i, seg in enumerate(segs):
        f = str(((seg.get("visual") or {}).get("formula") or "")).strip()
        if not f:
            continue
        found.append((i, f))
        if "=" not in f and "＝" not in f:
            problems.append(
                f"{i}枚目の formula に `=` が無い（『{f}』）。"
                "**数字の再掲は式ではありません。** 左辺と右辺のある形で書くこと"
            )
        elif not any(op in f for op in _OPS):
            problems.append(
                f"{i}枚目の formula に演算子が無い（『{f}』）。"
                "**言い換えではなく、どう計算したかを書くこと**（× ÷ + −）"
            )
        elif len(re.findall(r"\d", f)) < 2:
            problems.append(
                f"{i}枚目の formula に数字がほとんど無い（『{f}』）。"
                "**視聴者が同じ数を入れて追試できる形にすること**"
            )

    if not found:
        problems.append(
            "**計算式が1枚も画面に出ていません**（visual.formula が全部空）。"
            "この動画の根幹は「前提と計算式を画面に全部出す」ことで、"
            "**前提だけでは追試できず、こちらが計算した証拠が画面に残りません。**"
            "最低1枚に `800万円 = 40万円 × 20年` の形で入れること"
        )
    return problems


#: 語彙と規則は `src/calc/_checks.py` に**1つだけ**置いてあります。
#: **ここで定義し直さないこと**（2026-08-16）。
#:
#: この検査（画面に前提の値が出ているか）は 01:3x に入りましたが、
#: **渡す側（`ASSUMPTIONS`）が空の calc がある**という同じ穴が、
#: そのあと申し送りを8回運んでも閉じませんでした。閉じなかった理由は
#: **片側にしか検査が無かったから**です。いまは calc 側の
#: `_checks.assumption_values()` が同じ語彙・同じ近さで先に見ます。
#: **定義を2つ持つと、その日から片方だけ育ちます。**
from .calc._checks import (  # noqa: E402
    ASSUMPTION_MARKERS as _ASSUMPTION_MARKERS,
    QUANTITY_TAILS as _QUANTITY_TAILS,
    VALUE_NEAR_CHARS as _VALUE_NEAR_CHARS,
    trim_particles as _trim_particles,
)


def _visual_texts(seg: dict) -> list[str]:
    """1コマの**画面に出る文字**を全部集める。読み上げは含めない。"""
    v = seg.get("visual") or {}
    out: list[str] = []
    for key in ("headline", "stat", "note", "stat_source", "formula"):
        out.append(str(v.get(key) or ""))
    out += [str(x) for x in (v.get("items") or [])]
    out += [str(x) for x in (v.get("headers") or [])]
    for row in v.get("rows") or []:
        out += [str(c) for c in (row or [])]
    for bar in v.get("bars") or []:
        if isinstance(bar, dict):
            out += [str(bar.get("label") or ""), str(bar.get("value_label") or "")]
    return [t for t in out if t]


#: 折り返しを検査する画面の欄と、`visuals` のどの関数が折るか。
#: **実際に描く関数と同じものを呼ぶこと。** 限界文字数は欄ごとに違うので
#: （見出し9・箇条書き9・ラベル7・注記はさらに別）、
#: こちらで数字を持つと、片方だけ古くなります。
_WRAPPED_FIELDS = (
    ("headline", "_wrap_head"),
    ("note", "_wrap_note"),
    ("stat_source", "_wrap_note"),
)


def _wrapped_visual_lines(seg: dict, portrait: bool) -> list[tuple[str, list[str]]]:
    """1コマの画面の文字を、**描くときと同じ関数で折って**行に割る。

    返すのは `(元の文, 折れた行)` の組。呼ぶ側が隣り合う行の境目を見ます。
    """
    import html

    from . import visuals

    v = seg.get("visual") or {}
    jobs: list[tuple[str, str]] = []
    for key, fn in _WRAPPED_FIELDS:
        if v.get(key):
            jobs.append((str(v[key]), fn))
    jobs += [(str(x), "_wrap_item") for x in (v.get("items") or []) if x]
    for bar in v.get("bars") or []:
        if isinstance(bar, dict) and bar.get("label"):
            jobs.append((str(bar["label"]), "_wrap_label"))

    # **`note` は2つの幅で描かれます**（2026-08-16 21:5x に、この穴を実物で踏んだ）。
    #
    # `reveal_variants` が1枚を2つに割ると、**数字を伏せた1枚目では
    # 補足が主役になって大きくなります**（`.note.lead`）。
    # 縦向きの1行は **14字 → 6字**。**折れ目が増えるのは狭いほう**なのに、
    # ここは長らく `_wrap_note(text, portrait)`（＝ `lead=False`）しか見ていませんでした。
    #
    # 実物 `s-jikangai-futsu-6kagetsu-126` の注記「45時間以内で回す月の最低ライン」:
    #
    #     lead=False（検査が見ていた）  45時間以内で ／ 回す月の最低ライン   ← 問題なし
    #     lead=True （画面に出たほう）  **45時** ／ **間以内で** ／ 回す月の ／ 最低ライン
    #
    # **検査は緑で通り、目視だけが見つけました。** 広いほうだけ見る検査は、
    # 「いちばん割れやすい描かれ方」を構造的に素通りします。
    # **狭いほうを当てるのは、実際に lead で描かれうる欄だけ**にすること。
    # `visuals.reveal_variants` が `note_lead` を立てるのは
    # **`kind` が `stat` で `stat` と `note` の両方がある**コマだけです
    # （そこだけが2枚に割れて、1枚目の `stat` が空になる）。
    # 全部の `note` に狭い幅を当てると、**描かれない折れ方で鳴ります** ——
    # この回の実測で、`stat_source` に当てた2件が誤報でした（誤報は不投稿）。
    if (v.get("kind") or "stat").strip() == "stat" and v.get("stat") and v.get("note"):
        jobs.append((str(v["note"]), "_wrap_note_lead"))

    out: list[tuple[str, list[str]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for text, fn in jobs:
        if fn == "_wrap_note_lead":
            wrapped = visuals._wrap_note(text, portrait, 0, True)
        else:
            wrapped = getattr(visuals, fn)(text, portrait)
        lines = [html.unescape(x) for x in wrapped.split("<br>") if x]
        key = (text, tuple(lines))
        if len(lines) > 1 and key not in seen:
            seen.add(key)
            out.append((text, lines))
    return out


def _glued(text: str, lines: list[str]) -> list[bool]:
    """行の境目ごとに「**元の文で地続きだったか**」を返す（長さは行数−1）。

    **空白のところで折れたのは、欠陥ではありません。**
    `_wrap` は行頭・行末の空白を捨てるので、折れた行だけを見ると
    `25%` ／ `11,212,500円` と `9589万3334` ／ `円` の区別がつきません。
    **前者は元から空白で区切られた別々の値**で、画面上は何も壊れていない。

    実測（2026-08-16、待ち行列の34本）: この区別を入れる前は 4本が鳴り、
    **そのうち3本が空白での折れ＝誤報**でした。
    """
    pos = 0
    ends: list[int] = []
    starts: list[int] = []
    for line in lines:
        i = text.find(line, pos)
        if i < 0:            # 見つからない（想定外）。地続き扱いで甘くしない
            return [True] * (len(lines) - 1)
        starts.append(i)
        pos = i + len(line)
        ends.append(pos)
    return [text[ends[i]:starts[i + 1]] == "" for i in range(len(lines) - 1)]


#: **数の桁が割れた**とみなす、行末の字。次の行頭が数字のときだけ見ます。
#:
#: 字幕側（`_check_subtitles`）は `_NUM_TOKEN` の両側一致という**広い**規則です。
#: こちらは狭くしてあります。**外し方の損が違うから**です ——
#: 字幕側は生成のやり直しで済みますが、**こちらが誤報を出すと1本が投稿されません**
#: （`verify` は落ちたら上げない）。**投稿が途切れるのが最大の損失**なので、
#: 誤報の側に倒さない。
#:
#: 実測（2026-08-16、待ち行列の34本）。両側 `_NUM_TOKEN` だと 1本が鳴り、
#: それは `9589万3334` ／ `円` ＝ **単位1字が次の行に残る形**でした。
#: 読みにくいが**数としては読める**ので、ここでは鳴らしません
#: （直す先は `_best_cut` の側で、まだ直っていません。`docs/JOURNAL.md` に残す）。
#: 狭めた結果、34本で **0件**。桁の割れだけが鳴ります。
_DIGIT_RUN = set("0123456789,，．.")

#: **2字でひとつの単位**（`時間` `年間` `月間` `日間` `週間` `秒間`）。
#: 前の字は `_NUM_TOKEN` にあるのに後ろの字は無いので、
#: 「両側とも数字のかたまり」の規則をすり抜けます（2026-08-16 に実物で見つけた）。
#: 実物 `s-jikangai-futsu-6kagetsu-126` の注記が **『45時』／『間以内で』**。
#: 折る側（`subtitles._best_cut`）で塞いでありますが、**検査も持たせます** ——
#: 逃げ場が無いときの最後の1行は規則を踏み越えるので（カタカナで実際に起きた）。
_UNIT_HEAD = set("時年月日週秒")


def _check_visual_wrap(script: dict | None, portrait: bool) -> list[str]:
    """**画面の文字の折り返し**を、字幕と同じ目で見る（2026-08-16 に足した）。

    `_check_subtitles` は**読み上げの字幕（.ass）だけ**を見ていました。
    ところが折っているのは同じ `subtitles._chunk` で、
    `visuals._wrap` が**見出し・箇条書き・注記・棒のラベルの全部**を
    そこへ委ねています。**折り方は共通なのに、検査は片側にしか無かった。**

    実物 kLJ2Wsi3gQM（8/25 12:00 予定）の箇条書きが
    **『上限額 9,』／『110円→7,830円』** と割れ、
    **機械検査は緑のまま通しました**（目視で見つけています）。
    字幕側なら `数字の途中で改行している` で落ちていた形です。

    **だから塞ぐのは桁区切りの1件ではなく、片側しか見ていなかったこと**の
    ほうです。ここを足しておけば、次に `_best_cut` が別の理由で
    踏み越えたときも、画面側で止まります。

    **割り引いて読むこと**: ここは `tighten=0`（＝見積もりどおり収まった場合）で
    折ります。`visuals.render()` は入りきらないときに `tighten` を上げて
    **もっと狭く折り直す**ので、そちらで新しく出る割れ目は見えません。
    """
    if not script:
        return []
    bad_num: list[tuple[str, str, str]] = []
    bad_kata: list[tuple[str, str, str]] = []
    bad_unit: list[tuple[str, str, str]] = []
    for seg in script.get("segments") or []:
        for text, lines in _wrapped_visual_lines(seg, portrait):
            for (a, b), glued in zip(zip(lines, lines[1:]), _glued(text, lines)):
                if not glued:
                    continue      # 空白のところで折れただけ（別々の値）
                if a[-1] in _DIGIT_RUN and b[0].isdigit():
                    bad_num.append((text, a, b))
                elif _is_katakana(a[-1]) and _is_katakana(b[0]):
                    bad_kata.append((text, a, b))
                elif a[-1] in _UNIT_HEAD and b[0] == "間" and len(a) >= 2 \
                        and a[-2] in _NUM_TOKEN:
                    bad_unit.append((text, a, b))

    problems = []
    if bad_num:
        text, a, b = bad_num[0]
        problems.append(
            f"画面の文字が数字の途中で折れている箇所が {len(bad_num)} 件"
            f"（『{text}』→『{a}』『{b}』）"
        )
    if bad_kata:
        text, a, b = bad_kata[0]
        problems.append(
            f"画面の文字がカタカナの語の途中で折れている箇所が {len(bad_kata)} 件"
            f"（『{text}』→『{a}』『{b}』）"
        )
    if bad_unit:
        text, a, b = bad_unit[0]
        problems.append(
            f"画面の文字が2字の単位の途中で折れている箇所が {len(bad_unit)} 件"
            f"（『{text}』→『{a}』『{b}』）"
        )
    return problems


def _check_assumption_value_shown(script: dict | None) -> list[str]:
    """**前提として名前を出した量の値が、画面のどこかに出ているか。**

    2026-08-15 の独立評価が、**2本続けて同じ欠け**を指した。3体とも独立に:

    > 手取り率が何パーセントなのか、最後まで画面に出ない。だから31か月を検算できない。

    実物（`5SEWUmEzxcs`）の読み上げは
    「手取り率は制度の値ではなく、**この計算での仮定です**」で、
    **その仮定の値はどのコマにも出ていなかった。** 前の本（`2sEAxqibFIM`）も
    「1万210円の210円がどこから来るのか画面にない」で、**同じ種類**。

    `CLAUDE.md` の根幹は「**前提と計算式を、画面と説明欄に全部出す**」で、
    **視聴者が自分で追試できること**がテンプレート量産との違いだと書いてある。
    結論の数字は `_check_headline_from_calc` が calc と突き合わせ、
    式の形は `_check_formula_shown` が見る。**入力の値だけ、誰も見ていなかった。**

    ここで見るのは1つだけ ——
    **前提だと名乗っているコマが量の名前を出したなら、その量の値が画面にあること。**

    - 見るのは `visual`（＝画面）。読み上げに数字があっても、
      **画面に無ければ視聴者は止めて確かめられない**（3体はそこを突いた）
    - 名乗りの印（`仮定` `前提` …）が無いコマは見ない。
      **結論の言い換えまで拾うと、直しようのない指摘が増える**
    - 量は**語尾**で拾う（`〜率` `〜日数`）。一覧にすると、
      次に書かれる calc の量に当たらない

    **射程の外**（承知のうえ）: 「1万210円の**210円**」のような、
    前提ではなく**途中の導出**が落ちている形はここでは捕まらない。
    別の壊れ方なので、見たらそのとき足すこと。

    **欄と欄のあいだは必ず区切ること**（2026-08-24 に踏んで直した）。
    `_visual_texts` は**欄ごと・セルごとに1つずつ**返すので、
    継ぎ目なしで繋ぐと**隣り合わない字が1語に見えます。** 実物:

        headers = ["前提の項目", "内容"]   rows = [["使った割合", "任意解約"], ...]
        → 繋ぐと `…前提の項目内容使った割合…`
        → 語尾 `割合` で拾って **『項目内容使った割合』**（そんな量はどこにも無い）
        → 画面に「＝ 数字」の形で出るはずもなく、**必ず落ちる**

    この日の長尺 8本のうち **3本がこの検査で止まり**、うち1本がこの継ぎ目でした。
    **表を出すコマほど当たりやすい** —— セルが多いほど継ぎ目が増えるからです。
    量の名前が**2つの欄をまたぐことはありません**。だから区切っても
    本物の指摘は1件も減りません（`tests/test_assumption_value.py` が押さえます）。
    """
    if not script:
        return []
    segs = script.get("segments") or []
    if not segs:
        return []

    # 量の名前に**使われない字**なら何でもよい。改行にしてある。
    _SEP = "\n"
    screen = _SEP.join(t for seg in segs for t in _visual_texts(seg))
    named: list[str] = []
    for seg in segs:
        text = str(seg.get("narration") or "") + _SEP + _SEP.join(_visual_texts(seg))
        if not any(m in text for m in _ASSUMPTION_MARKERS):
            continue
        for m in re.finditer(r"[一-龥ぁ-んァ-ヶー]{1,8}?(?:" + "|".join(_QUANTITY_TAILS) + ")", text):
            word = _trim_particles(m.group(0))
            if word not in named:
                named.append(word)

    problems = []
    for word in named:
        shown = False
        for m in re.finditer(re.escape(word), screen):
            near = screen[max(0, m.start() - _VALUE_NEAR_CHARS):m.end() + _VALUE_NEAR_CHARS]
            if re.search(r"\d", near):
                shown = True
                break
        if not shown:
            problems.append(
                f"**前提として『{word}』を出しているのに、その値が画面のどこにもありません。**"
                "視聴者は結論を検算できず、**画面には「計算した」と書いてあるだけ**になります"
                "（独立評価の3体が2本続けてここを突きました）。"
                f"どこかのコマに『{word} ＝ 〇〇』の形で、"
                "**calc の出力に出ているとおりの値**を出すこと"
            )
    return problems


#: 法令の引用の形。`雇用保険法22条・23条` `労働基準法37条5項` `雇用保険法61条の7第5項`。
#: **緩く取ること。** ここで拾い損ねた引用は、下の照合にも掛かりません。
_LAW_CITATION_RE = re.compile(
    r"[一-龥ぁ-んァ-ヶー]{2,12}法"                                  # 法令名（〜法）
    r"(?:施行(?:令|規則))?"                                          # 施行令・施行規則
    r"\s*第?\s*[0-9０-９]+\s*条"                                     # 第22条
    r"(?:\s*の\s*[0-9０-９]+)?"                                      # 61条の7
    r"(?:\s*[・、,]?\s*第?\s*[0-9０-９]+\s*[条項号](?:\s*の\s*[0-9０-９]+)?)*"
)


def _trim_law_citation(text: str) -> str:
    """`所定給付日数は雇用保険法22条・23条` → `雇用保険法22条・23条`。

    法令名は漢字だけなので、`法` より前にある**最後のひらがな・カタカナ**で切る。
    **判定には使いません**（緩いまま拾うほうが安全）。**直し方を見せるときだけ**
    使います —— 助詞ごと見せると「この形のまま写せ」の形が壊れます
    （2026-08-16、`_check_assumption_value_shown` が同じ形の間違いをしています）。
    """
    head = text.split("法", 1)[0]
    cut = max((i for i, c in enumerate(head) if "ぁ" <= c <= "ヿ"), default=-1)
    return text[cut + 1:] if cut >= 0 else text


def _normalize_citation(text: str) -> str:
    """照合用に均す。全角数字を半角へ、空白を落とす。**中黒は落とさない。**

    **中黒を落とすと、この検査が捕まえるべきものを自分で通します** ——
    実際に画面に出た欠陥が「`22条・23条` の中黒が消えて `22条23条` になった」
    だからです。区切りの有無こそが、条番号が壊れているかどうかの境目。
    """
    return re.sub(r"\s", "", text.translate(str.maketrans("０１２３４５６７８９", "0123456789")))


def _calc_module_path(work: Path) -> Path | None:
    """テーマ（＝ build のディレクトリ名）から `src/calc/<名前>.py` を引く。

    引けなければ `None`。**引けないことを欠陥として報告しないこと** ——
    `calc` の無いテーマは正常に存在します。
    """
    root = Path(__file__).resolve().parent.parent
    try:
        import yaml
        topics = yaml.safe_load(
            (root / "config" / "topics.yaml").read_text(encoding="utf-8")
        )["topics"]
    except Exception:
        return None
    for t in topics:
        if str(t.get("id")) == work.name:
            name = str(t.get("calc") or "").strip()
            path = root / "src" / "calc" / f"{name}.py"
            return path if name and path.exists() else None
    return None


def _check_law_citation_verbatim(work: Path, script: dict | None) -> list[str]:
    """**画面と読み上げに出る条文の引用が、calc が書いている引用と一字一句同じか。**

    2026-08-16、独立評価の3体が `8PMLfjjCe4w` について
    「**`雇用保険法22条23条` の条番号が壊れている**」と独立に書きました
    （1体は「読み上げは『別表』なのに画面は条番号で、一致しない」とも）。

    **出どころを測ったら、生成側でも描画側でもありませんでした。**

        src/calc/shitsugyo.py  「所定給付日数は雇用保険法22条・23条の別表どおり」
        画面（表の1行）          「雇用保険法22条23条」          ← 中黒が消えている
        読み上げ                「日数は雇用保険法の別表」        ← 条番号を言っていない

    折り返し（`_wrap`）を実物の文で走らせても中黒は残ります。**落としたのは
    台本の書き手**で、`ASSUMPTIONS` を表の1行に詰めるときに区切りごと消えました。
    `雇用保険法22条23条` は法令の引用として**存在しない形**です。

    これは見栄えの話ではありません。`CLAUDE.md` は
    「**制度や金額には必ず適用条件を添える。裏の取れない数字は動画に入れない**」と
    書いています。**書き手が引用を言い換えられる限り、裏取りは毎回ここで壊れます。**
    数字（`_check_headline_from_calc`）と式（`_check_formula_shown`）と
    前提の値（`_check_assumption_value_shown`）は突き合わせているのに、
    **条文の引用だけ、誰も突き合わせていませんでした。**

    だからここで見るのは1つ ——
    **引用は写すものであって、書き直すものではない。**

    照合の相手は calc の**モジュールの本文**（docstring の「根拠」と `ASSUMPTIONS`）で、
    実行の出力ではありません。`python -m src.calc.shitsugyo` の 70行に条番号は
    1つも出てきません（出るのは表と金額です）。**裏を取った記録が置いてあるのは
    モジュールの側**なので、そちらを正本にします。

    **射程の外**（承知のうえ）:

    - **calc が書いている引用そのものが間違っている場合は捕まりません。**
      ここが見るのは「写したか」だけです。裏取りは題材を選ぶ段の仕事
      （`docs/trigger_main.md` §4）
    - `calc` の無いテーマ・`topics.yaml` が読めない回は**素通しにします。**
      引用の照合ができないことを理由に投稿を止めるのは割に合いません
    """
    if not script:
        return []
    segs = script.get("segments") or []
    if not segs:
        return []

    path = _calc_module_path(work)
    if path is None:
        return []
    try:
        source = _normalize_citation(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    allowed = [_trim_law_citation(c) for c in _LAW_CITATION_RE.findall(path.read_text(encoding="utf-8"))]
    problems: list[str] = []
    seen: set[str] = set()
    for seg in segs:
        texts = _visual_texts(seg) + [str(seg.get("narration") or "")]
        where = "画面"
        for i, text in enumerate(texts):
            if i == len(texts) - 1:
                where = "読み上げ"
            for m in _LAW_CITATION_RE.finditer(text):
                cited = _trim_law_citation(m.group(0))
                key = _normalize_citation(cited)
                if key in source or key in seen:
                    continue
                seen.add(key)
                near = "／".join(dict.fromkeys(allowed)) or "（この calc は条文を1つも引いていません）"
                problems.append(
                    f"**{where}の『{cited}』が、`{path.name}` の書いている引用と一致しません。**"
                    "条文の引用は**写すもので、書き直すものではありません**"
                    "（2026-08-16、`雇用保険法22条・23条` の中黒が落ちて"
                    "`雇用保険法22条23条` という存在しない条番号が画面に出ました。"
                    "独立評価の3体が別々に指しています）。"
                    f"`{path.name}` にあるのは: {near}。"
                    "**この形のまま写すか、条番号を出さずに『別表』とだけ書くこと**"
                )
    return problems


def _check_adjacent_repeat(script: dict | None) -> list[str]:
    """**1本の中で、隣り合う2枚が同じ画に見えていないか。**

    `_check_not_repeat` は**過去の動画との**重複だけを見ている。
    **同じ動画の中で隣り合う2枚**は、どこも見ていなかった。

    2026-08-15、独立評価の3体が、意図を渡していないのに独立に
    「隣り合う2枚が、見出しも同じで棒が1本増えるだけ」と書いた。
    8/15 16:0x の回は6体が同じことを言っている。**通算9体・2回の持ち越し。**
    それでも機械の検査は全部通っていた —— **見ている場所が無かったから。**

    YouTube は「同じチャンネルの動画を続けて数本視聴した後、繰り返しのように
    感じられる可能性のあるコンテンツ」を収益化の対象外にしている。
    1本の中で同じ画が続くのは、その**もっと手前**の状態で、
    engaged（すぐスワイプされなかった割合）にも直接効く。

    見るのは2つ。**どちらも「隣り合う」ときだけ**当てる。
    離れた位置に同じ見出しが再登場するのは、まとめや対比として成立する。

    1. **見出しが同一**（空白と全半角の差は無視）。1枚めくって同じ文字が
       上に出ていれば、視聴者から見て画面は変わっていない
    2. **chart の棒が包含関係**。`{A,B}` の次が `{A,B,C}` なら、
       それは「棒が1本増えるだけ」そのもの。`_check_not_repeat` は
       **共通2本以上**で落とすが、あれは*別の動画*が相手のときだけ働く

    2 の「片方が空」は包含に数えない（0本の chart は 1 の対象外の別問題で、
    `_check_not_repeat` が chart 0枚として別に落とす）。
    """
    if not script:
        return []
    segs = script.get("segments") or []

    def norm(text: str) -> str:
        # 全角空白・半角空白・改行を落とすだけ。文言そのものは変えない。
        return "".join(str(text or "").split()).replace("　", "")

    def bars_of(seg: dict) -> set[str]:
        v = seg.get("visual") or {}
        if v.get("kind") != "chart":
            return set()
        return {str(b.get("display", "")) for b in (v.get("bars") or [])}

    problems: list[str] = []
    for i in range(len(segs) - 1):
        a, b = segs[i], segs[i + 1]
        va = (a.get("visual") or {})
        vb = (b.get("visual") or {})
        ha, hb = norm(va.get("headline")), norm(vb.get("headline"))
        if ha and ha == hb:
            problems.append(
                f"{i}枚目と{i + 1}枚目の見出しが同一（{va.get('headline')!r}）。"
                "**隣り合う2枚で画面が変わっていない。** どちらかの見出しを、"
                "そのコマで新しく分かることに変えること"
            )
        ba, bb = bars_of(a), bars_of(b)
        if ba and bb and (ba <= bb or bb <= ba):
            grew = sorted(bb - ba) or sorted(ba - bb)
            problems.append(
                f"{i}枚目と{i + 1}枚目の chart が包含関係"
                f"（棒が{len(grew)}本増えるだけ: {'・'.join(grew[:3])}…）。"
                "**同じ図の描き直しになっている。** 軸か切り口を変えるか、1枚にまとめること"
            )
        # 3. **隣り合う表が、枠も行数も同じで、本文まで似ている**（2026-08-29 に足した）
        for p in _same_shaped_table(i, va, vb):
            problems.append(p)
    return problems


#: 隣り合う表を「同じ絵」とみなす、本文の一致率のしきい値。
#:
#: **1〜2 は見出しと棒しか見ておらず、表は素通りでした。** 2026-08-29 の実測で、
#: 長尺の生成失敗の主因が `_check_slides` の
#: 「隣り合う図解が**見た目には変わっていない**」に入れ替わっており
#: （08-25 以降 2/3。`config/hypotheses.yaml` の判定）、その落ちた組は
#: **どちらも表** —— 見出し行が同じ・行数も同じで、**桁の並びだけが違う**ものでした:
#:
#:     6枚目  亡くなった日 / 未支給の月数 / 未支給年金の額
#:            1日 3か月 450000円 ／ 10日 3か月 450000円 ／ 13日… ／ 14日…
#:     7枚目  亡くなった日 / 未支給の月数 / 未支給年金の額
#:            15日 1か月 150000円 ／ 16日… ／ 20日… ／ 28日…
#:     → 128px の灰色で比べた差は **画面の 0.60%**（門は 1.0%）
#:
#: **これは段階表示ではありません。** `visuals.reveal_variants` が作る
#: 「行が1つずつ増える」組は**行数が違う**ので、ここには当たりません。
#:
#: **しきい値の測り方**（`data/critique_queue/*.plan.json` の公開ずみ 540本）:
#:
#:     隣り合う table で見出し行が同一                  924組  ← 段階表示。**当てない**
#:       そのうち行数も同じ                              18組
#:         本文の一致率が 70% 以上                        0組   ← **誤報 0/540**
#:     この回に落ちた 1組                                       **73.8%**
#:
#: 公開ずみ側の最大は **60.8%** で、落ちた側は **73.8%**。あいだは 13ポイント 空いています。
#: **ただし当たりは n=1 です。** しきい値をこの1件から置いていることを隠しません。
#:
#: **覆る条件**: (1) 誤報が1件でも出たら戻すこと（通る台本が書き直しの3回を
#: 使い切ると、かえって歩留りが下がります —— `script_writer.long_script_problems`
#: の「厳しくしないこと」）。(2) 2件目の当たりが 70% を下回ったら、
#: しきい値を下げるのではなく**別の量**が要ります（一致率は「ink がどれだけ
#: 塗り替わるか」の代理でしかありません）。
#: **検査**: `tests/test_adjacent_table_shape.py`。
SAME_TABLE_TEXT_RATIO = 0.70


def _same_shaped_table(i: int, va: dict, vb: dict) -> list[str]:
    """隣り合う2枚が「枠も行数も同じで、本文まで似ている表」なら1件 返す。

    **レンダリング前に分かるものを、レンダリング後まで持ち越さないため**です
    （`script_writer.long_script_problems` の冒頭と同じ理由 ——
    ここで言えば同じセッションが3回まで書き直せますが、`_check_slides` で
    落ちると `claude -p` と合成とレンダリングを全部 捨てます）。
    """
    import difflib

    if va.get("kind") != "table" or vb.get("kind") != "table":
        return []

    def norm(text: str) -> str:
        return "".join(str(text or "").split()).replace("　", "")

    ha = [norm(h) for h in (va.get("headers") or [])]
    hb = [norm(h) for h in (vb.get("headers") or [])]
    if not ha or ha != hb:
        return []
    ra = va.get("rows") or []
    rb = vb.get("rows") or []
    # **行数が違えば段階表示**（`visuals.reveal_variants` は先頭からの部分列）。
    # 実測で 924組 中 906組 がこちらです。**当てません。**
    if not ra or len(ra) != len(rb):
        return []

    ta = "".join(norm(c) for row in ra for c in row)
    tb = "".join(norm(c) for row in rb for c in row)
    if not ta or not tb:
        return []
    ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
    if ratio < SAME_TABLE_TEXT_RATIO:
        return []
    return [
        f"{i}枚目と{i + 1}枚目の表が、見出し行（{' / '.join(ha)}）も行数（{len(ra)}行）も同じで、"
        f"本文の {ratio * 100:.0f}% が同じ文字です。"
        "**離れて見ると同じ絵に見えます**（実測でこの形は画面の1%も塗り替わりません）。"
        "片方の**列そのもの**を変えるか（別の量を並べる）、"
        "2枚を1枚の表にまとめて、行を増やすこと"
    ]


def _plan_frames(work: Path, script: dict | None,
                 from_script: bool = False) -> list[dict] | None:
    """**画面に出るコマの列**。読めなければ `None`、無ければ空。

    正本は `work/slides_plan.json`（`pipeline` が**割った後**を書き出す唯一の場所）。
    **無いときは台本の `visual` で代用します** —— 台本を書いている最中は
    まだレンダリングしていないので、そこにしか絵がありません
    （`script_writer.long_script_problems` がこの道を通ります）。

    **代用しても答えは変わりません。** 割るのは `visuals.reveal_variants` で、
    あれは `bars`/`rows`/`items` の**先頭からの部分列**しか作らないので、
    割った後のコマ全部を合わせた値の集合は、割る前の1枚と**同じ**です。
    `narrated.unshown()` が見ているのはその集合だけです。

    `from_script=True` は「**ファイルがあっても台本を見る**」。
    台本を書いている最中の呼び手はこちらを使うこと —— いまは
    `pipeline` が `generate()` の**前に** `work` を `rmtree` するので
    残骸は在りませんが、**その順序に頼ると、順序が変わった日に
    「新しい読み上げ × 前の回の絵」を突き合わせて黙って誤報を出します。**
    """
    path = work / "slides_plan.json"
    if path.exists() and not from_script:
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if isinstance(plan, list):
            return [v for v in plan if isinstance(v, dict)]
        return []
    if not script:
        return []
    return [s["visual"] for s in script.get("segments", [])
            if isinstance(s, dict) and isinstance(s.get("visual"), dict)]


def _check_narrated_shown(work: Path, script: dict | None,
                          from_script: bool = False) -> list[str]:
    """**読み上げが言った数が、絵に1つも出ていないか**（2026-08-17）。

    独立評価で2体が「図解の棒に、読み上げが言った行が無い」と書き、
    申し送りが3回運ばれました。中身と実測は `src/narrated.py` の冒頭にあります。

    **`_check_assumption_value_shown` とは向きが逆です。** あちらは
    「計算の入力が画面にあるか」で、こちらは「**耳で言った答えが目に出ているか**」。
    実物84本で、両者が同時に当たる本は**1本もありません**。

    **見るのは動画ぜんたいです**（文ごとではありません）。文ごとに当てると
    実測 15件/13本 になりますが、そのうち抜き取った2件はどちらも
    **隣の文の絵に出ていました**（`78ssJSwULTg` の足切り10万円、
    `E5i0YfIkmnA` の課税価格3億円）。**誤報は不投稿**なので、
    確かめていない厳しさをここに置きません。ぜんたいで見ると
    **84本中3本・4件で、抜き取った全部が本物**でした。

    ## **長尺にも掛けます**（2026-08-26 に実測して変えた。**それまで掛けていなかった**）

    ここは長く「**ショートだけに掛けます**（長尺は構成が違う）」でした。
    呼ぶ側が `if portrait:` の中に置いていたので、**長尺は素通り**です。
    そして `portrait` は動画の実物ではなく `video_cfg["resolution"]` から来るので、
    **`--short` を付けずに作った本は、この検査を1度も通っていません。**

    **どこが痛いか。** `CLAUDE.md` は「**4,000時間の門に入るのは長尺だけ**」と
    書いています。つまり**収益化の可否を背負っているのは長尺のほう**で、
    根幹の一文（「**前提と計算式を、画面と説明欄に全部出す**」「視聴者が自分で
    追試できることがテンプレート量産との違い」）が効くのも長尺です。
    **その長尺だけが無検査でした。**

    ### 実測（`data/critique_queue/` の控え 430本。門が入った 08/17 より後）

        ショート（コマ>文・5〜6行・94〜140字）  397本 → 漏れ **0本**
        長尺  （コマ=文・14〜25行・1473〜2191字） 33本 → 漏れ **7本（21%）**

    **門が入った後の漏れは、100% が長尺です。** 掛かっている側は完璧に効き、
    掛かっていない側だけが漏れていました。

    ### 誤報を数えた（**誤報は不投稿**なので、先にこれを見ること）

    長尺の指摘 **10件を全部** 目で確かめ、**10/10 が本物**でした
    （どれも `narrated.shown_values()` の集合に1つも無い）:

        plmBPZqqP1U 2万5262・12万6310   還付額そのもの（答え）
        mRisqvcqmm4 1万7510             国民年金保険料の前提
        DyEcaMK5ZU8 1万7510             同上
        jeRBnxQjBvY 330万・110万        公的年金等控除の適用条件
        a63FzIUV2wI 1544万8761          声で言った3点を図が1つも持っていない
        jYoDuz0S9z4 81万6000            3級の最低保障から導いた額
        xQ2EzmkHRjw 37万2500            控除前の所得税額（答え）

    ### **`orientation` を証拠に使わないこと**（この穴を1回隠しました）

    `scripts/critique_queue.py` の `orientation` は
    `"縦" if script.get("short", True) else "横"` です。**台本に `short` という鍵は
    ありません**（`VideoScript` に無い）。だから `.get` の既定 `True` が必ず出て、
    **控え 469本が469本とも「縦」**です。**定数であって、向きではありません。**

    2026-08-25 の申し送りは、この欄を読んで「4本とも縦なのに門を素通りした
    ＝ 門が壊れている」と書き、次の回に「`--dry-run` で作って
    `work/slides_plan.json` を控えと突き合わせろ」と残していました。
    **突き合わせても何も出ません**（同じファイルの `shutil.copy2` なので必ず一致する）。
    **壊れていたのは門ではなく、向きを見た計器のほうです。**
    向きを知りたいなら **コマ数と文の数**を見ること（長尺は `reveal_variants` を
    通らないので必ず `コマ = 文`、ショートは必ず `コマ > 文`）。

    ### 覆る条件

    - **長尺の誤報が出たら**、そのときは「文ごと」ではなく**動画ぜんたい**で
      見ていることを先に確かめること（上の節）。それでも誤報なら、
      長尺だけ `narrated.FLOOR` を上げるか、ここから外して理由を書くこと
    - **歩留りが落ちたら。** この検査は `script_writer.long_script_problems` にも
      入れてあるので、**生成中に3回まで書き直させてから**ここに来ます。
      それでも長尺の歩留りが目に見えて落ちるなら、書き直しの指示文
      （`LONG_FIX_GUIDANCE`）が効いていないほうを先に疑うこと
    """
    if not script:
        return []
    frames = _plan_frames(work, script, from_script)
    if frames is None:
        return ["slides_plan.json が読めない"]
    if not frames:
        return []
    problems: list[str] = []
    for seg in script.get("segments", []):
        line = str(seg.get("narration") or "")
        for tok in narrated.unshown(line, frames):
            problems.append(
                f"読み上げ「{line}」の {tok} が、画面のどこにも出ていません。"
                "**耳で言って目に出していない数です。** 棒か行か見出しに足すこと"
            )
    return problems


#: **一息（1コマ）で、耳に持たせてよい数の上限**（2026-08-27 に足した）。
#:
#: 5 にしてある理由は下の `_check_ear_load` の実測にあります。
#: **4 にしないのは、書き直しの輪が3回しかないから**です
#: （`long_script_problems` の冒頭「厳しくしないこと —— ここで余分に落とすと、
#: 通る台本が書き直しの回数を使い切って、かえって歩留りが下がります」）。
EAR_LOAD_MAX = 5

#: **1回の書き直しで、この検査が出す指摘の上限**（2026-08-27）。
#:
#: 控え539本に当てた実測では、**捕まる 75本（14%）の1本あたり 6.9件**。
#: 書き直しの輪は **3回しかありません**（`script_writer.generate`）。
#: 全部を並べると、他の検査（`_check_not_repeat` など）の指摘が
#: **同じ画面の下のほうへ押し出されます** —— この repo が何度も踏んでいる
#: 「言っているのに読まれない」の形です。
#: **重い順に3件**だけ出し、残りは件数で言います（**消していません**）。
EAR_LOAD_REPORT = 3


def _check_ear_load(script: dict | None) -> list[str]:
    """**一息で、耳がいくつ数を持たされているか**（2026-08-27・オーナー指摘）。

    ## 出どころ（オーナー原文・2026-08-27 21:0x）

    > 「一つの考えなんだけどさ、動画についてまず何言ってるか分かんないね。
    > **音声だけで理解できない説明なのに画面はすぐ切り替わるし。**
    > 説明を理解するにはかなり視聴者側の推論が必要だと思う。」

    ## `narrated.py` と向きが逆です（**両方 要ります**）

        narrated.py   耳が言った数 → **絵に出ているか**（出ていないと検算できない）
        ここ          耳が言った数 → **いくつ持たされるか**（多いと追えない）

    `narrated` を通した本は「全部 画面に出ている」ので**目では追えます**。
    ところが**耳だけでは追えません** —— そして
    `status.py` の実測では、再生の **99.8% が `SHORTS_FEED`**、
    1再生あたり **20秒（尺の56%）**。**多くの視聴者は最後まで見ていません。**

    ## 数え方 —— **見出しの数も数えます**

    `narrated.numbers()` をそのまま使うので、「2人で16万5千円」は **2個**です
    （「2人」と「16万5千円」）。**耳はどちらも持たされる**ので、そうしています。
    つまり上限 5個 は、おおよそ「**見出しと値の組が2つを超えたところ**」です。

    ## 実測（`data/critique_queue/` の控え **539本・3,834コマ**）

        1コマあたりの数    中央値 2.0 ／ 平均 2.21 ／ **最大 16**
        4個以上            781コマ（20.4%）／ 194本（36%）
        **5個以上**        **514コマ（13.4%）／ 75本（14%）**
        6個以上            371コマ（ 9.7%）／ 62本（12%）

    いちばん重い1コマ（`xaciR1LbaEs`・**この日に予約した本**）:

        「23パーセントは12万9670円が引かれて25万7600円、33.48パーセント。
          33パーセントは16万9210円が引かれて21万8060円、43.69パーセント。…」

    **16個。** 画面には全部 出ています（`narrated` を通っています）。
    **耳では1つも残りません。**

    ## 直し方は「消す」ではなく「置き場所を変える」

    列挙は**画面（`table` / `chart`）の仕事**です。読み上げが言うのは
    **形**（どちらが大きいか・どこで逆転するか・伸びが鈍るのはどこか）と、
    **代表の1つか2つ**。`CLAUDE.md` の根幹（「前提と計算式を、画面と説明欄に
    **全部**出す」）は1文字も緩みません —— **画面には全部 出したまま**、
    耳の負荷だけを下げます。

    ## なぜ `verify.run` の門にしないか

    **誤報は不投稿**で、しかもこれは「作り直せば直る種類」です。だから
    `script_writer.{long,short}_script_problems` に置いて、
    **生成中に3回まで書き直させます**（`_check_narrated_shown` と同じ考え方。
    あちらの docstring「`verify` で落とすと1本 捨てになる」）。

    ## 覆る条件

    - **歩留りが落ちたら**、まず書き直しの指示文（`LONG_FIX_GUIDANCE` /
      `SHORT_FIX_GUIDANCE`）が効いていないほうを疑うこと。それでも落ちるなら
      `EAR_LOAD_MAX` を 6 へ上げる（**外さない** —— 外すと測れなくなります）
    - **歩留りが落ちないなら 4 へ下げること。** 上の実測では
      5→4 で当たるコマが 13.4% → 20.4% に広がります
    - 1本あたり再生（`per_video`）がこれで動かないなら、
      縛っているのは耳の負荷ではありません。**そのときは
      `docs/JOURNAL.md` に測った数を書いて、この検査を弱めること**

    ## **隣の仮説は、測って捨てました**（2026-08-28。**検査を足していません**）

    同じオーナー指摘の後半「説明を理解するにはかなり視聴者側の推論が必要」から、
    2026-08-27 の調査は**もう1つ**の説明を出しています ——
    **「画面を見ないと指示対象が分からない語で埋まっている」**
    （実例 `data/critique_queue/E53Lh0NsFkw.json` のコマ12: 4文のあいだに
    「帯の左端／右端／左端／右端／帯の幅／この2つの線」）。
    ただしあちらは**数を出していません**（「語彙の取り方で 24〜118回 に散る」ので
    再現しなかった）。**残した宿題は「語彙一覧を全部 書き出したうえで数えろ」**でした。

    **書き出して数えました。控え 555本・3,984コマ**（`data/critique_queue/`）:

        狭い語彙  1個以上 **95コマ（2.4%）／ 52本（9.4%）**  0個の本 503本
        広い語彙  1個以上 **359コマ（9.0%）／125本（22.5%）** 0個の本 430本

        狭い = 左端|右端|左側|右側|左から|右から|上のほう|下のほう|真ん中|中央の
               |上から\\d+|下から\\d+|一番上|一番下|いちばん上|いちばん下
               |(この|その|あの|こちらの)(線|棒|帯|矢印|枠|列|行|欄|軸|点|グラフ|図|表|色|部分|ところ)
               |2つの線|2本の棒|画面の|(図|表|グラフ)の(ように|とおり)|ご覧のとおり|見てのとおり
               |(青|赤|緑|黄色|オレンジ|灰色|グレー)(い)?(の|い)?(線|棒|帯|部分|ところ|ほう|方)
        広い = 狭い ＋ 帯|棒|棒グラフ|グラフ|この表|その表|縦軸|横軸|凡例|矢印|色分け|ハイライト|太字|囲み

        いちばん多い語: 帯 246 ／ 棒 102 ／ この表 32 ／ この帯 13 ／ この行 9 ／ 真ん中 9

    **`E53Lh0NsFkw` のコマ12（5個）は、3,984コマ中の最大級です。**
    あの1コマは典型ではなく、**上位 0.1% の外れ値**でした。

    **3つの説明を同じ物差しで並べると、こうなります:**

        コマが読み切れない   ショート 2.27秒/コマ → **88.5%** が読み切れない（08/27 の実測）
        耳の負荷（この検査）  5個以上 **13.4%** のコマ ／ 14% の本
        画面ごしの指示語      **2.4〜9.0%** のコマ ／ 9.4〜22.5% の本

    **桁が1つ違います。** だから**指示語の検査は足していません** ——
    `src/alerts.py` の「一覧が当たりを含まないまま育つ」に当たる形だからです。
    **縛っているのは、まず『読み切れない』のほう**で、そこは
    `slide_pace` の A/B（1コマ 2.5秒 対 4.5秒・判定 2026-09-24）が既に振っています。

    **覆る条件**: `slide_pace` が閉じて 1本あたり再生が動かず、
    この検査（耳の負荷）でも動かないなら、**残るのはここです。**
    そのときは上の広い語彙で門を作ること（**語彙はここに書いてあるので、
    数え直しから始めなくて済みます**）。
    """
    if not script:
        return []
    heavy: list[tuple[int, str]] = []
    for seg in script.get("segments", []):
        line = str(seg.get("narration") or "")
        vals = {v for _t, v, _s in narrated.numbers(line)}
        if len(vals) >= EAR_LOAD_MAX:
            heavy.append((len(vals), line))
    if not heavy:
        return []
    heavy.sort(key=lambda x: -x[0])
    out = [
        f"読み上げ「{line[:40]}…」が、一息で **{n}個** の数を耳に載せています"
        f"（上限 {EAR_LOAD_MAX - 1}個）。**列挙は画面（table / chart）の仕事**です —— "
        "読み上げは『どちらが大きいか・どこで逆転するか・伸びが鈍るのはどこか』の"
        "**形**と、代表の1〜2個だけにして、残りの数は visual の rows / bars に移すこと。"
        "**画面から数を減らさないこと**（減らすと検算できなくなります）"
        for n, line in heavy[:EAR_LOAD_REPORT]
    ]
    if len(heavy) > EAR_LOAD_REPORT:
        out.append(
            f"（同じ形が **ほか {len(heavy) - EAR_LOAD_REPORT}件** あります。"
            "**重い順に上から出しています** —— 台本ぜんたいで、"
            "列挙している文を『形＋代表1〜2個』へ直してください）"
        )
    return out


def _check_adjacent_frames(work: Path) -> list[str]:
    """**画面に出るコマの側で、隣り合う2枚が同じに見えていないか**（2026-08-15 20:5x）。

    `_check_adjacent_repeat` は **script.json（文の側）** を見ています。
    ところが `pipeline` は1つの文の絵を `visuals.reveal_variants` で複数コマに割り、
    **視聴者と独立評価が見ているのは割った後のほう**です。

    **だから「隣り合う2枚が同じ見出し」は、割った後にしか存在しません。**
    8/15 18:5x の回はこの検査を script 側に足して**0件**で通し、
    3体は同じ回の実物を見て同じ指摘を書いています（**通算3回の持ち越し**）。
    実物 `OePniwSIcTE` は8コマ中4コマが該当し、機械の検査は全部通っていました。

    見るのは2つだけ。**割った後のコマの列**（`slides_plan.json`）に当てます。

    1. **隣り合う2枚の見出しが同一** —— 上に出ている文字が同じなら、
       絵が1行増えても視聴者から見て画面は変わっていない
    2. **隣り合う2枚が完全に同じ辞書** —— めくりが水増しになっている

    **無ければ何も言いません。** 長尺と、この直しより前に作った build が
    落ちても意味がないからです（`slide_seconds.json` と同じ扱い）。
    """
    path = work / "slides_plan.json"
    if not path.exists():
        return []
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"slides_plan.json が読めない: {exc}"]
    if not isinstance(plan, list):
        return []

    def norm(text: str) -> str:
        return "".join(str(text or "").split()).replace("　", "")

    problems: list[str] = []
    for i in range(len(plan) - 1):
        a, b = plan[i], plan[i + 1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        if a == b:
            problems.append(
                f"{i + 1}コマめと{i + 2}コマめが完全に同じ絵です。"
                "**めくりが水増しになっている。** 割る要素が足りないなら割らないこと"
            )
            continue
        ha, hb = norm(a.get("headline")), norm(b.get("headline"))
        if ha and ha == hb:
            problems.append(
                f"{i + 1}コマめと{i + 2}コマめの見出しが画面上で同一"
                f"（{a.get('headline')!r}）。"
                "**絵が増えても、上の文字が同じなら画面は変わって見えません。**"
                "めくりなら `_reveal_headline` が『＋増えた要素』か『2/3』を足すはず"
            )
            continue
        if _same_lead(a, b):
            problems.append(
                f"{i + 1}コマめと{i + 2}コマめで、**画面の主役が同じまま**です"
                f"（{_lead_of(a)!r}）。"
                "変わったのは注記や式のような小さい1行だけで、"
                "**視聴者から見て画面は据え置きに見えます。**"
                "めくるなら、主役そのもの（数字・棒・行・項目）を変えること"
            )
    return problems


#: 前提だと名乗っている印。`_check_assumption_value_shown` と同じ語彙にしてあります
#: （あちらは script.json の側、こちらは割った後のコマの側）。
_ASSUMPTION_MARK = re.compile(r"前提|仮定")
_HAS_DIGIT = re.compile(r"[0-9０-９]")


def _plan_visible_text(visual: dict) -> str:
    """そのコマで**画面に出る文字**を、ぜんぶ1本に繋ぐ。

    見出しだけを見ないこと（2026-08-16 23:xx に実測で決めた）。
    実物 `_kUTXa1t9ZA` は前提を **`note` に**書いており
    （`給付は非課税・社保免除・賞与なしの前提`）、
    **見出しだけを見た数え方では「前提が無い本」に入りました。**
    視聴者は見出しも注記も同じ画面で見ます。**分ける理由がありません。**
    """
    parts: list[str] = [
        str(visual.get(key) or "")
        for key in ("headline", "stat", "note", "note_lead", "formula", "stat_source")
    ]
    parts += [str(x) for x in visual.get("items") or []]
    parts += [str(x) for x in visual.get("headers") or []]
    for row in visual.get("rows") or []:
        parts += [str(x) for x in (row if isinstance(row, (list, tuple)) else [row])]
    for bar in visual.get("bars") or []:
        parts.append(str(bar))
    return " ".join(p for p in parts if p)


def _check_assumptions_on_screen(work: Path) -> list[str]:
    """**前提が画面に1枚も出ていない本を止める**（2026-08-16 23:xx）。

    `CLAUDE.md` の根幹は「**前提と計算式を、画面と説明欄に全部出す**」で、
    **視聴者が自分で追試できること**がテンプレート量産との違いです。
    収益化されなければ収入はゼロなので、これは見栄えではなく到達可能性の条件。

    `src/script_writer.py` 531行は書き手にそう指示していますが、
    **指示だけで検査がありませんでした。** すぐ上の 326行は同じ話について
    「指示に書いても守られないので機械で見る」と書いて検査を入れており、
    **片方だけ機械にしてあった**形です（この作りで通算9回目）。

    ## 申し送りの数字は、そのまま採っていません（**測り直しました**）

    前の回は **「前提の表が1枚も無い本が 33/61」** と書いて渡してきました。
    `data/critique_queue/*.plan.json` の61本で数え直すと、そうではありません。

        前提の名乗りが1枚も無い（見出しだけ見る）        **1 / 61**
        前提の名乗りが1枚も無い（画面の文字を全部見る）  **0 / 61**
        `kind == "table"` の前提コマが無い               **33 / 61**  ← 申し送りの数字

    **33本は「前提が無い」ではなく「前提が表の形をしていない」でした。**
    実際には `steps`（15本）・`stat`（10本）・`compare`（9本）で出ており、
    **前提コマに値が1つも無い本は 0本**です。
    申し送りのとおり `table` を要求すると、**半分以上が落ちます。**
    **誤報は不投稿**なので、そこには置きません（`docs/trigger_main.md` §5）。

    だから見るのは**形ではなく、あるか**です。実測で 61/61 が通ります。

    1. 前提だと名乗っているコマが**1枚も無い**
    2. 名乗ってはいるが、**そのコマに値が1つも無い**（名前だけの前提は追試できない）

    `_check_assumption_value_shown` とは見ている先が違います。あちらは
    **script の前提文に出てくる量の値**が画面のどこかにあるかで、
    **前提のコマそのものが存在するか**は誰も見ていませんでした。

    **ショートだけに掛けます**（長尺は構成が違う）。呼ぶ側で `portrait` を見ています。
    """
    path = work / "slides_plan.json"
    if not path.exists():
        return []
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"slides_plan.json が読めない: {exc}"]
    if not isinstance(plan, list) or not plan:
        return []

    marked = [
        v for v in plan
        if isinstance(v, dict) and _ASSUMPTION_MARK.search(_plan_visible_text(v))
    ]
    if not marked:
        return [
            "**計算の前提が、画面に1枚も出ていません。**"
            "この動画は制度の解説ではなく自分で計算した結果の発表で、"
            "**前提と式を画面に出すことだけが追試の手段**です。"
            "`src/calc/` の `ASSUMPTIONS` を、途中の1コマに出すこと"
        ]
    if not any(_HAS_DIGIT.search(_plan_visible_text(v)) for v in marked):
        return [
            "**前提のコマはありますが、値が1つも出ていません。**"
            f"（{marked[0].get('headline')!r}）"
            "「手取り率は仮定です」とだけ書いても視聴者は追試できません。"
            "**置いた量の値そのもの**を、同じ画面に出すこと"
        ]
    return []


# 「主役」＝そのコマで面積をいちばん食っている要素。
# 種類ごとに、どのキーがそれに当たるかを持つ。ここに無い種類は stat 扱い。
LEAD_KEYS = {
    "chart": "bars",
    "table": "rows",
    "steps": "items",
    "compare": "items",
    "stat": "stat",
}
# 主役の外側にある、小さい1行たち。**ここだけが変わっても「変わった」とは言えません。**
SIDE_KEYS = {"headline", "note", "formula", "note_lead", "stat_source",
             "scale_max", "scale_base", "scale_bars"}


def _lead_of(visual: dict):
    """そのコマの主役を返す。"""
    kind = (visual.get("kind") or "stat").strip()
    return visual.get(LEAD_KEYS.get(kind, "stat"))


def _same_lead(a: dict, b: dict) -> bool:
    """**主役が同じままで、脇の小さい行だけが変わった2枚**か（2026-08-15 22:0x）。

    ## なぜ画素で見ないのか（**測ってから決めています**）

    `slide_change_ratios` は既にあり、`NEAR_DUPE_RATIO`（1%）を下回る組を
    落とします。**それでも `0MC_rlov7Ng` は通り、独立評価の3体が3体とも
    「1コマ目と2コマ目が実質同じ絵」と書きました**（通算4回目の持ち越し）。

    `scripts/bake_slides.py` で実物（`s-tedori-1`・13枚）を測ると、こうです。

        0→1  **7.06%**  stat の2枚（数字も見出しも式も同じ・21字の注記が増えるだけ）
        4→5    6.02%    chart の2枚（**棒が1本ふえる**。本物の段階表示）

    **偽物のほうが、本物より大きく出ています。** 順序が逆転しているので、
    `NEAR_DUPE_RATIO` をどこに置いても「偽物だけ落として本物を通す」線は引けません。
    **しきい値の調整では直りません。**

    理由は測ってみれば単純で、`.body` が中央寄せだからです。注記が1行入ると
    **その下に入るぶん、大きな数字が上へずれます。** 画素はごっそり変わりますが、
    **増えた情報はゼロ**です。画素は「動いたか」を測っていて、
    見たいのは**「新しいものが出たか」**でした。**測る対象が違っていました。**

    だから、画面に出る側の構造（`slides_plan.json`）で見ます。
    **主役が同じで、脇の小さい行しか変わっていなければ、据え置きです。**
    """
    if (a.get("kind") or "stat").strip() != (b.get("kind") or "stat").strip():
        return False
    if _lead_of(a) != _lead_of(b):
        return False
    # 主役の外で「本当に何も変わっていない」組は上の `a == b` が拾うので、
    # ここに来るのは必ず脇のどれかが違う組。
    changed = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    return bool(changed) and changed <= SIDE_KEYS


def _check_headline_from_calc(work: Path, script: dict | None) -> list[str]:
    """**冒頭に出す数字が、こちらの計算から出たものであること。**

    この作りの根幹は「制度を解説するのではなく、自分で計算した結果を発表する」。
    制度のまとめ直しは、どれだけ丁寧でも「自分で作成していない資料の読み上げ」の側に
    落ち、収益化されない。**収益化されなければ収入はゼロ**なので、これは
    見栄えではなく到達可能性の話。

    ところが 2026-08-05 の残業代ショートは、冒頭が「除外できる手当は7つだけ」だった。
    7 は労基法37条5項の列挙の数であって、`src/calc/` が計算した数字ではない。
    **機械の検査は全部通った。** `_check_short_opening` は「1枚目が stat か」しか
    見ておらず、**その数字の出どころは誰も見ていなかった。**

    ここで見る。計算をもう一度走らせ、冒頭 stat の数字が出力に含まれるか確かめる。
    キャッシュではなく実行するのは、保存した値と台本がずれる余地を作らないため。

    数字が1つも入っていない stat（「7つだけ」の「7」も拾う）も落とす。
    **落ちたら作り直し。** ショートの作り直しは数分で済む。

    ## **ショートだけに掛けています。理由は「構成が違うから」ではありません**

    呼ぶ側が `if portrait:` の中に置いています。**その理由を 2026-08-26 に
    測り直しました** —— 「長尺は構成が違う」は成り立ちません:

        長尺 33本の**1コマめは 33本とも数字入りの `stat`**（100%）
        その33本に実際に当てると、**落ちるのは 0本**（誤報も 0）

    **構成は同じで、いま捕まるものが無いだけ**です。
    `script_writer.long_script_problems` の「厳しくしないこと」に従って
    見送っています。**捕まる本が出たら、外へ出してよい。**

    **同じ日に、同じ形で 21% の漏れが出ています** ——
    `_check_narrated_shown` は「ショートだけに掛けます（長尺は構成が違う）」と
    書いたまま `if portrait:` の中にあり、**長尺が1本も通っていませんでした。**
    **理由が測られていない除外は、この形で腐ります。**
    """
    if not script:
        return []
    segments = script.get("segments") or []
    if not segments:
        return []
    visual = segments[0].get("visual") or {}
    stat = str(visual.get("stat") or "")
    source = str(visual.get("stat_source") or "")
    if not re.search(r"\d", stat):
        return [f"冒頭の数字に数値が入っていない（『{stat}』）。"
                "ショートの冒頭は計算結果の数字1つにする"]

    # テーマ ID は build ディレクトリ名。そこから calc モジュールを引く。
    try:
        import yaml
        topics = yaml.safe_load(
            (Path(__file__).resolve().parent.parent / "config" / "topics.yaml").read_text(encoding="utf-8")
        )["topics"]
    except Exception as exc:                       # 設定が読めないだけで投稿を止めない
        return [f"topics.yaml が読めず、冒頭の数字の出どころを確かめられません: {str(exc)[:60]}"]

    name = ""
    for t in topics:
        if str(t.get("id")) == work.name:
            name = str(t.get("calc") or "").strip()
            break
    if not name:
        return []                                  # calc の無いテーマは対象外

    import subprocess
    import sys as _sys

    try:
        proc = subprocess.run([_sys.executable, "-m", f"src.calc.{name}"],
                              capture_output=True, text=True, timeout=300,
                              cwd=str(Path(__file__).resolve().parent.parent))
    except Exception as exc:
        return [f"src.calc.{name} を実行できず、冒頭の数字を確かめられません: {str(exc)[:60]}"]
    if proc.returncode != 0:
        return [f"src.calc.{name} が失敗して、冒頭の数字を確かめられません"]

    # **申告された出どころを、計算の出力と突き合わせる。**
    #
    # 最初は stat の数字そのものを出力から探した。**それでは効かない。**
    # 台本は計算結果を言い換える（「ずれ 31か月」→「最大2年7か月」）ので、
    # 正しい動画まで落ちた。逆に「7つだけ」の 7 は1桁なので、どんな出力にも
    # たまたま現れる。**桁数でしきいを置いたのも勘だった。**
    #
    # 数字の見た目からは出どころを判定できない。だから**台本に申告させる**。
    # 言い換える前の値を写させて、それが出力にあるかを見る。
    # 写せない＝計算に無い数字、ということになる。
    if not source:
        return [f"冒頭の数字『{stat}』に出どころ（stat_source）の申告が無い。"
                "計算結果のどの行から取ったのかを写させること"]

    # **連続一致を要求したら、これも厳しすぎた。**
    # 台本は「一般の扶養控除 **合計** 52,399円」のように列名を挟んで書く。
    # 52,399円は表に実在するのに落ちた。**「そのまま写せ」は守られない前提で組む。**
    #
    # 見るのは**申告の中の数字が全部、出力にあるか**。
    #   ずれ 31か月            → 31 がある ✓
    #   一般の扶養控除 合計 52,399円 → 52399 がある ✓
    #   労基法37条5項の7つ      → 2桁の数字が 37 だけで、条番号。下で落とす
    #
    # 1桁は偶然どこにでも現れるので照合に使えない。**2桁以上が1つも無ければ落とす。**
    # 計算結果に1桁しか出てこないことは、この作りではまず無い
    # （金額・日数・月数のどれかが必ず2桁以上になる）。
    # **数字の照合だけでは、実際に起きた壊れ方を止められない。**
    # 「労基法37条5項の7つ」は 2桁の 37 を含み、37 は 91,837 の中に偶然現れるので通る。
    # かといって3桁以上を要求すると「ずれ 31か月」（正しい）が落ちる。
    # **桁数でしきいを置くのは、ここでも間違い。**
    #
    # 観測した壊れ方は「**条文の列挙から数字を取った**」というもの。
    # なら条文の引用そのものを見る。出どころは計算の出力の中になければならず、
    # 計算の出力に条番号は出てこない。これは狙いを絞った目印であって、
    # あらゆる誤りを捕まえるものではない。**別の壊れ方を見たら、また足すこと。**
    if re.search(r"\d\s*(条|項|号|別表)", source):
        return [f"冒頭の数字の出どころ『{source}』が条文の引用になっている。"
                "**制度の条文から数字を取っている。** この動画で出すのは"
                "`src/calc/` が計算した結果であって、条文の項目数ではない"]

    out = re.sub(r"[\s,、　]", "", proc.stdout)
    runs = [n for n in re.findall(r"\d+", re.sub(r"[\s,、　]", "", source)) if len(n) >= 2]
    if not runs:
        return [f"冒頭の数字の出どころ『{source}』に2桁以上の数字が無い。"
                "**計算結果ではなく制度の項目数や条文番号を大きく出していないか。**"
                "ショートの冒頭は計算して出した数字にすること"]
    missing = [n for n in runs if n not in out]
    if missing:
        return [f"冒頭の数字の出どころ『{source}』のうち {'・'.join(missing)} が"
                f" src.calc.{name} の出力に無い。**計算していない数字が混ざっている。**"]
    return []


def _to_yen(text: str) -> set[int]:
    """文中の金額を、桁の揃った整数にして取り出す。

    「30万」「30万円」「1万6544円」「287,000円」を同じ土俵に載せる。
    **表記が違うだけで見逃す**のを防ぐため。
    """
    out: set[int] = set()

    # **万の式を先に食い、読んだところは消してから素の数字を拾う。**
    #
    # 2026-08-09、これをやっていなかったので「35万9318円」から
    # 359,318 と **9,318 の両方**が出ていた。9,318 は計算出力に出てこないので、
    # `_check_title_from_calc` が正しいタイトルを誤って落とした。
    # **検査そのものの偽陽性で、作り直させていた。**
    #
    # **小数の「万」を取りこぼさないこと。** `35.9万` を素直に書くと
    # 正規表現が **`9万` のほうに食いついて 90,000** を返す（2026-08-09 に発生）。
    # 90,000 は計算出力に無いので検査は落ちるが、**理由が嘘になる。**
    # 「35.9万」の正体は 359,318円 を丸めたもので、落とすべきなのは
    # **丸め**のほう。数字を直せと言われた側は 90,000 を探しに行ってしまう。
    rest_text = []
    last = 0
    # **「万」の前後に空白を許さないこと。** 表は列を空白で並べるので、
    # `\s*` を挟むと **`300万    450,000円` を1つの数として食う**（3,450,000）。
    # 読んだところは消す作りなので、**450,000 が二度と拾われない。**
    # 2026-08-09、これで `年収べつの手取り` の社会保険料の列が丸ごと
    # 「計算出力に無い」扱いになった。**許可する数の集合が黙って縮む**ので、
    # 正しい台本を落とす側に倒れる。実在の金額表記に空白は入らない。
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)万(\d[\d,]*)?\s*千?", text):
        man = float(m.group(1).replace(",", ""))
        tail = m.group(2)
        val = int(round(man * 10_000))   # man は小数のことがある（35.9万）
        if tail:
            r = int(tail.replace(",", ""))
            val += r * 1_000 if m.group(0).rstrip().endswith("千") else r
        out.add(val)
        rest_text.append(text[last:m.start()])
        last = m.end()
    rest_text.append(text[last:])

    for m in re.finditer(r"(\d[\d,]{2,})", " ".join(rest_text)):
        out.add(int(m.group(1).replace(",", "")))
    return out


def _check_title_from_calc(work: Path, script: dict | None, topic: dict | None) -> list[str]:
    """**タイトルの金額が、渡した計算出力に実在するか。**

    2026-08-09、長尺のタイトルが「売上30万でも申告不要の条件」だった。
    **30万円は計算出力に無い**（実際の売上は 28万7千・34万2千・43万5千）。
    モデルが丸めて書いた。

    `_check_headline_from_calc` は**縦向き（ショート）にしか当たっていなかった**ので、
    長尺のタイトルは誰も見ていなかった。**裏の取れない数字を動画に入れない**のは
    この作りの根幹で、尺で例外を作る理由はない。

    見るのは**1000以上の整数**だけ。パーセントや条文番号は別の規則
    （`_check_headline_from_calc`）が見る。
    """
    if not script or not topic:
        return []
    from .script_writer import calc_block

    try:
        block = calc_block(topic)
    except Exception:
        return []                      # 計算が引けないテーマは対象外
    if not block:
        return []

    have = _to_yen(block)
    problems = []
    for label, text in (("タイトル", script.get("title", "")),
                        ("サムネ", str(script.get("thumbnail_line1", ""))
                         + " " + str(script.get("thumbnail_line2", "")))):
        for n in sorted(_to_yen(text)):
            if n >= 1000 and n not in have:
                problems.append(
                    f"{label}の「{n:,}」が計算出力にありません。"
                    "**裏の取れない数字を出さないこと。** 丸めるのも駄目"
                )
    return problems


def _check_count_matches(script: dict | None) -> list[str]:
    """**「3つ」と言いながら4項目出していないか。**

    2026-08-09、長尺の最後で音声が「明日やることを3つ」、画面が4項目だった。
    目視で見つかったが、**これは機械で見える種類**（数字と個数の突き合わせ）。

    数が主役のチャンネルで画面と音声が食い違うのは、内容の正しさとは別に
    **信頼を落とす。** 前提を全部画面に出すことで検証可能性を担保している以上、
    画面と音声のずれは根幹に触る。

    見るのは narration の「Nつ」と、同じセグメントの items の数だけ。
    **広げないこと。** 「3種類」「3パターン」まで拾うと誤検出が出る
    （別のものを数えている場合がある）。
    """
    if not script:
        return []
    problems = []
    for i, seg in enumerate(script.get("segments") or []):
        items = (seg.get("visual") or {}).get("items") or []
        if not items:
            continue
        m = re.search(r"([1-9１-９])\s*つ", seg.get("narration") or "")
        if not m:
            continue
        said = int(m.group(1).translate(str.maketrans("１２３４５６７８９", "123456789")))
        if said != len(items):
            problems.append(
                f"{i}番目で音声が「{said}つ」と言っているのに、画面の項目は{len(items)}個。"
                "**数が合っていない。** どちらかに揃えること"
            )
    return problems


def _check_short_opening(script: dict | None) -> list[str]:
    """ショートの1枚目は stat（大きい数字1つ）であること。

    ショートは最初の1画面で離脱が決まるので、GOAL.md は「冒頭2秒で数字を出す」と
    決めてある。ところが自動生成した1本は chart で始まっていた。棒グラフは
    読むのに時間がかかるので、2秒では入ってこない。

    これは「壊れてはいないが、決めたことを黙って外している」たぐいの外れ方で、
    いちばん見つけにくい。だから機械に見せる。ショートの作り直しは5分で済み、
    毎日の投稿義務は長尺のほうなので、ここは落として作り直させてよい。
    """
    if not script:
        return []
    segments = script.get("segments") or []
    if not segments:
        return ["台本にセグメントがない"]
    problems = []
    kind = (segments[0].get("visual") or {}).get("kind")
    if kind != "stat":
        problems.append(
            f"ショートの1枚目が {kind} になっている（stat であること）。"
            "最初の1画面で離脱が決まるので、冒頭は大きい数字1つにする"
        )
    problems += _check_opening_fragment(segments[0].get("narration") or "")
    return problems


# 冒頭で「中身の無い言い残し」とみなす文の長さ（句点を除く）。
# 「動きます」は4字。実際に出たのはこれ（2026-08-15）。
OPENING_FRAGMENT_CHARS = 6


def _check_opening_fragment(narration: str) -> list[str]:
    """冒頭に、数字も語も持たない**短い言い残しの文**が付いていないか。

    2026-08-15、`s-tedori-2` の冒頭が

        料率15なら35万9318円。動きます。

    で出ました。**「動きます。」は人が言う日本語ではありません。**
    前の文の述語だけが千切れて残った形です。

    **どの機械検査も通りました。** `_check_short_opening` は
    「1枚目が stat か」しか見ておらず、`_check_headline_from_calc` は
    「その数字が計算から出ているか」しか見ていません。
    **どちらも、文として読めるかを見ていません。**

    冒頭は 0.9〜2秒 で、離脱は 4.7〜5.7秒 に来ます（`src/script_writer.py` の実測）。
    **いちばん効く場所に、意味の無い1文を置いていました。**

    **冒頭のセグメントだけを見ます。** 途中の文にも同じことは起こりえますが、
    ここを広く取ると正しい言い切り（「年収500万円。」のような体言止め）まで
    落として**投稿を止めます**。止めるのが最大の損失なので、狭く取ること。
    数字・英数字・カタカナのどれかを含む文は、内容があるとみなして通します。

    **「短くて数字が無い」だけでは足りませんでした**（この回に実際に誤爆した）。
    投稿済み `7b2-Z6Jw5DQ` の冒頭「月給30万で年6万2500円。休日次第です」の
    **「休日次第です」を落としました。これは千切れた述語ではなく、中身のある節です。**
    分けているのは漢字の数です。**言い残しは述語だけなので漢字が1字**
    （動きます・下がります・戻ります・ご覧ください）。
    中身のある短い節は名詞を持つので2字以上になります（休日次第です・税は別です）。
    """
    sentences = [s for s in re.split(r"(?<=[。！？])", narration) if s.strip()]
    if len(sentences) < 2:
        return []
    bad = [
        s for s in sentences
        if len(s.rstrip("。！？")) <= OPENING_FRAGMENT_CHARS
        and not re.search(r"[0-9０-９A-Za-z゠-ヿ]", s)
        and len(re.findall(r"[一-鿿]", s)) <= 1
    ]
    if not bad:
        return []
    return [
        f"冒頭に中身の無い短い文がある（『{bad[0]}』）。"
        "前の文の述語だけが千切れて残った形で、人が言う日本語になっていない。"
        "**冒頭は離脱がいちばん多い場所です。**1文で言い切ること"
    ]


# 「見た目には変わっていない」と言える差の上限。
# 小さく縮めた灰色画像どうしを比べ、値が NEAR_DUPE_LEVEL 以上ちがう画素が
# 全体の何割あるか。この割合を下回ったら、視聴者には同じ絵に見えているとみなす。
# **しきい値は実測で置くこと**（下の `slide_change_ratios` を実物に掛ける）。
NEAR_DUPE_RATIO = 0.010
NEAR_DUPE_LEVEL = 24
# 比べる前に縮める大きさ。細部（アンチエイリアスの揺れ・1文字の差）を落として、
# **離れて見たときに気づくかどうか**に近づける。
NEAR_DUPE_THUMB = 128


def slide_change_ratios(slides: list[Path]) -> list[float]:
    """隣り合う図解が、画面のどれだけを塗り替えているか（0〜1）を順に返す。

    **バイト一致では捕まらないものを見るためにある。** 2026-08-15、独立評価の
    3体が独立に「同じ絵が2コマ続く」「実質3枚」と書いてきた回で、
    `_check_slides` のバイト比較は**1件も見つけませんでした。**
    段階表示（`visuals.reveal_variants`）は表に1行足すだけでも
    別のバイト列になるので、**ハッシュが違うことは「絵が変わった」の証拠になりません。**

    縮めて灰色にしてから比べるのは、見たいのが「画素が違うか」ではなく
    **「視聴者が変化に気づくか」**だからです。原寸で比べると、
    影や縁のわずかな差だけで「変わった」ことになってしまいます。
    """
    from PIL import Image, ImageChops

    def small(path: Path):
        im = Image.open(path).convert("L")
        im.thumbnail((NEAR_DUPE_THUMB, NEAR_DUPE_THUMB))
        return im

    out: list[float] = []
    prev = small(slides[0]) if slides else None
    for path in slides[1:]:
        cur = small(path)
        if cur.size != prev.size:          # 寸法が違えば別の絵
            out.append(1.0)
        else:
            hist = ImageChops.difference(prev, cur).histogram()
            total = sum(hist) or 1
            out.append(sum(hist[NEAR_DUPE_LEVEL:]) / total)
        prev = cur
    return out


def _check_slides(work: Path, script: dict | None) -> list[str]:
    """同じ絵が続くこと自体がポリシー上の risk。chart の枚数もここで数える。

    「テンプレートを使用して作成されたと思われるコンテンツ」に当たると
    収益化されない。収益化されなければ RPM がいくつでも収入はゼロなので、
    これは見栄えの話ではなく到達可能性の話。
    """
    problems = []
    slides = sorted((work / "slides").glob("*.png"))
    if slides:
        digests = [hashlib.sha1(p.read_bytes()).hexdigest() for p in slides]
        dupes = sum(1 for a, b in zip(digests, digests[1:]) if a == b)
        if dupes:
            problems.append(f"隣り合う図解が同じ画像になっている箇所が {dupes} 件")

        # バイトは違うが、見た目は変わっていない組。
        # **バイト一致のぶんは上で出しているので、ここでは除きます**
        # （同じ1組を2行で報告しても、直すことは1つしかない）。
        ratios = slide_change_ratios(slides)
        near = [i for i, r in enumerate(ratios)
                if r < NEAR_DUPE_RATIO and digests[i] != digests[i + 1]]
        if near:
            worst = min(ratios[i] for i in near)
            problems.append(
                f"隣り合う図解が**見た目には変わっていない**箇所が {len(near)} 件"
                f"（{len(slides)}枚中。いちばん小さい差は画面の {worst * 100:.1f}%）。"
                f"実質 {len(slides) - len(near)} 枚に見えている。"
                "**段階表示は、足した要素が離れて見て分かる大きさでなければ"
                "『同じ絵の据え置き』です**"
            )

    if script:
        kinds = [s.get("visual", {}).get("kind") for s in script.get("segments", [])]
        charts = kinds.count("chart")
        if charts < MIN_CHARTS:
            problems.append(
                f"chart が {charts} 枚しかない（下限 {MIN_CHARTS} 枚）。"
                "計算結果で図の形を変えるのが量産テンプレート判定との分かれ目"
            )
    return problems


def _check_yomi(script: dict | None) -> list[str]:
    """合成音声が確実に読み違える形が、TTS に渡る文字列に残っていないか。

    2026-08-16 に「額」が「ひたい」と読まれていたのを、オーナーが動画を聞いて
    見つけた。ここには音の検査が1つも無かったので6日間残った。

    見ているのは音そのものではない。`src/yomi.py` の置換を通したあとに、
    **既知の壊れる形が1文字でも残っていないか**だけ。残っていなければ、
    その字はエンジンに届かないので誤読しようがない。音の実測は
    `scripts/probe_yomi.py`（Google TTS の出力を直接比べる）が担当する。
    """
    if not script:
        return []
    problems = []
    for i, seg in enumerate(script.get("segments", [])):
        for why in remaining_risks(str(seg.get("narration") or "")):
            problems.append(f"セグメント{i + 1} の読みが直っていない（{why}）")
    return problems


#: **人間の職業・資格の名前**。ここに無い肩書きは素通りします（下の「覆る条件」）。
_PROFESSION_WORDS = (
    "経理", "人事", "労務", "総務", "財務",
    "税理士", "公認会計士", "会計士", "社会保険労務士", "社労士",
    "行政書士", "司法書士", "弁護士", "弁理士", "中小企業診断士",
    "ファイナンシャルプランナー", "ファイナンシャル・プランナー", "FP",
    "銀行員", "証券マン", "保険外交員", "保険募集人",
    "キャリアアドバイザー", "キャリアコンサルタント", "採用担当",
    "コンサルタント", "アドバイザー", "専門家", "プロ",
)
_PROF = "|".join(re.escape(w) for w in _PROFESSION_WORDS)
#: 話し手が自分を指す語。**視聴者を指す語（あなた・皆さん）は入れないこと。**
_FIRST_PERSON = "私|僕|俺|自分|筆者|当方|わたし|ぼく"

#: 「人間の専門家として語っている」形。**当てるのは話し手の側だけ**です。
#:
#: 落とさないもの（実例で確かめた・下の docstring の「落とさないもの」）:
#:   「税理士に確認してください」  ← 相手が専門家。話し手の名乗りではない
#:   「会社員として働く人は」      ← 主語が視聴者。職業語も一覧に無い
#:   「専門家にご確認ください」    ← 説明欄の定型文（config/channel.yaml の footer）
_HUMAN_EXPERT_PATTERNS: tuple[tuple[str, str], ...] = (
    (rf"元[・\s]?(?:{_PROF})",
     "「元・<職業>」と、実在しない経歴を名乗っています"),
    (rf"(?:{_FIRST_PERSON})[はがも、]?[^。！？\n]{{0,14}}(?:{_PROF})"
     rf"(?:として|の担当|の仕事|畑|部門|歴)?(?:でした|です|だった|をしてい|を担当|にい)",
     "一人称で職業・肩書きを名乗っています"),
    (rf"(?:{_PROF})として(?:の)?(?:経験|立場|視点|目線|感覚)",
     "職業の立場から語る形になっています"),
    (r"(?:専門家|プロ)として",
     "専門家を名乗っています"),
    (rf"(?:実務|現場)[でをのは][^。！？\n]{{0,12}}"
     rf"(?:回して|担当して|扱って|やって|見て|回した|担当した)"
     rf"(?:き|い)?(?:た|ました|ています)",
     "実務経験を持っていると書いています"),
    (rf"(?:{_FIRST_PERSON})の(?:経験|実務|現場|担当)(?:上|では|から|だと)",
     "自分の経験を根拠にしています"),
    (rf"(?:{_FIRST_PERSON})[はがも、]?[^。！？\n]{{0,14}}"
     rf"(?:年間|年ほど|年)[、]?[^。！？\n]{{0,8}}(?:勤め|在籍し|担当し|やってき)",
     "勤続年数という経歴を名乗っています"),
)


def _check_no_human_expert_claim(script: dict | None) -> list[str]:
    """**人間の専門家を装っていないか**（2026-08-30 に足した。**停止の解除条件 1・2**）。

    ## なぜ要るか

    2026-08-30、オーナーが `AUTOMATION_PAUSED.md` を `origin/main` へ直接 push して、
    いまの作り方を止めました。挙がっている理由の中心は次の2行です。

        - AI-generated personas presenting themselves as human experts on sensitive topics
        - AI personas providing financial guidance or interpreting legal rules

    実物がありました。`config/channel.yaml` の `persona` が
    **「元・事業会社の経理／人事で、制度を実務で回してきた立場」**と名乗り、
    `src/script_writer.py:1086` から**毎本の台本の指示文**に入っていました。
    **そんな人はいません。** 合成音声が、税・保険・キャリアという
    **視聴者が自分の金で動く題**を、架空の実務経歴を根拠に語る形です。
    `CLAUDE.md` が「手段として成立しない」と名指ししている2つの片方
    （**なりすまし**）でもあります。

    ## **設定を直しただけでは閉じません。だからここに置きます**

    `persona` は**台本を書かせる指示文の一部**でしかありません。
    書き手（LLM）は、そこに無い経歴を自分で足すことがあります ——
    「元・経理」を消しても、narration に
    **「私が担当していたころは」**と書かれれば、視聴者から見える形は同じです。

    **設定は入口、ここは出口です。** 出口に置くと、
    `persona` が将来どう書き換わっても、**出来上がった台本のほうで落ちます。**
    `script_only_problems()` に入れてあるので、**レンダリングの前**に当たります
    （動画1本 15分を焼いてから落とすのではなく、台本の時点で作り直しへ回る）。

    ## 落とさないもの（**視聴者と第三者の側は当てません**）

        「税理士に確認してください」    相手が専門家。話し手の名乗りではない
        「会社員として働く人は」        主語が視聴者
        「専門家にご確認ください」      説明欄の定型文（`channel.yaml` の footer）

    ## 覆る条件（3つ）

    1. **実在する人間が実名で出演し、その経歴が事実になったら**、これは
       「装う」に当たりません。**そのときはこの検査ごと外すこと**
       （`config/channel.yaml` の `persona` の「覆る条件」と対です）
    2. **語の一覧（`_PROFESSION_WORDS`）は網羅ではありません。**
       ここに無い肩書き（例:「元・国税調査官」の *調査官*）は素通りします。
       **踏んだら足すこと** —— 網羅を先に書こうとすると、
       視聴者を指す語まで拾って偽陽性で投稿が止まります（そちらのほうが高い）
    3. **偽陽性が出て投稿が止まったら、パターンを狭めること。**
       `CLAUDE.md`「投稿が途切れるのが最大の損失」より —— ただし
       **`persona` に経歴を戻すことでは直さないこと。** それは元の穴です
    """
    if not script:
        return []
    problems: list[str] = []
    fields: list[tuple[str, str]] = [
        ("タイトル", str(script.get("title") or "")),
        ("説明欄", str(script.get("description_body") or "")),
    ]
    for alt in script.get("title_alternatives") or []:
        fields.append(("タイトルの別案", str(alt or "")))
    for i, seg in enumerate(script.get("segments") or []):
        fields.append((f"セグメント{i + 1}", str(seg.get("narration") or "")))
        for line in _visual_texts(seg):
            fields.append((f"セグメント{i + 1} の画面", str(line or "")))

    for where, text in fields:
        if not text:
            continue
        for pattern, why in _HUMAN_EXPERT_PATTERNS:
            hit = re.search(pattern, text)
            if hit:
                problems.append(
                    f"**{where}が人間の専門家を装っています**（{why}）: "
                    f"「{hit.group(0)}」。"
                    "**このチャンネルに実在の経歴はありません。**"
                    "根拠は経験ではなく、置いた前提と計算式のほうに書くこと"
                    "（AUTOMATION_PAUSED.md の解除条件 1・2）")
                break
    return problems


def _check_form_tag(script: dict | None, duration: float) -> list[str]:
    """**長尺に `#Shorts` の札を付けて出さない**（2026-08-25 に実測で見つけた）。

    YouTube のショートの区切りは **3分**です。それを超えた本に `#Shorts` を
    付けても Shorts のフィードには出ません。**出ないのに、題名の一等地を使い、
    ブラウズと検索の側には「これはショートだ」と言います。**

    実物（この回に控え493本を突き合わせた）:

        WuTf0Z-tRJc   **5分51秒**   … #Shorts   公開済み・**1再生**
        CfzcVmRncPg   **5分9秒**    … #Shorts   予約 08/27 09:00

    後者は **day_cap の切り分けの日（08/27）**に載っていました。
    `scripts/reschedule.py --spread` は**1日のショートの本数に上限**をかけるので、
    長尺をショートと数えると、その日の枠を1本ぶん食いつぶし、
    **本物のショートを後ろの日へ押し出します**（＝密度の損・対照の破壊）。

    ## 逆向き（ショートなのに札が無い）は落としません

    実測で3本ありました（`pMHDwK5tB2E` / `YmJ7psxW3co` / `FSAN9tjIX10`）。
    こちらも上限から漏れるので直すべきですが、**投稿を止める理由にはしません** ——
    札が無くても Shorts のフィードには尺で載るので、**動画そのものは正しい**。
    途切れるほうが高いので（CLAUDE.md）、**印字だけして通します。**
    `src.forms.mislabelled()` が後から数え直せます。
    """
    if not script or duration <= 0:
        return []
    title = str(script.get("title") or "")
    tagged = "#Shorts" in title
    long_form = duration > forms.SHORT_MAX_SECONDS
    if long_form and tagged:
        return [f"**{duration / 60:.1f}分の長尺に `#Shorts` が付いています**"
                "（3分を超えるとショートのフィードには出ません。題名から外すこと）"]
    if not long_form and not tagged:
        print(f"[verify] 注意: {duration:.0f}秒 のショートに `#Shorts` がありません"
              "（投稿は止めません。1日の本数の上限から漏れます）")
    return []


#: 直近 何本と見比べるか。**ポリシーの原文が「続けて数本視聴した後」と言っている**ので、
#: 生涯の平均ではなく**並び**を見ます（`src/frames.recent()`）。
FRAME_WINDOW = 20

#: 直近の窓のうち、同じ枠が何割を超えたら落とすか。
#:
#: **0.5 なのは、振り分けが4通りだからです。** 期待は 25% で、20本の窓で
#: 半分を超える確率は二項分布で **1.4%** —— つまり「たまたま偏った」で
#: 落ちるのは 100本に1〜2本、その1本は言い回しを変えれば通ります。
#: **0.6 や 0.7 にすると、いまの控えの 61%（「明日やる」）が素通りします。**
FRAME_MAX_SHARE = 0.5

#: 窓がこれより浅ければ**何も言いません**。
#: `src/bars.py` と同じ理由 —— 新しい実行環境では控えがゼロになることがあり、
#: そこで「比較対象が無い＝合格」ではなく「**判定していない**」を明示するためです。
FRAME_MIN_HISTORY = 8


def _check_frame_repeat(script: dict | None, portrait: bool,
                        topic_id: str = "") -> list[str]:
    """**直近の本と同じ枠で始まって・終わっていないか**（2026-08-30・**解除条件3**）。

    ## なぜ要るか

    `_check_not_repeat` は **chart の数値**、`_check_adjacent_repeat` は
    **1本の中の隣り合う2枚**を見ています。**どちらも「入り方と締め方」を見ていません。**

    2026-08-30 に測ったら、そこが揃っていました（`python -m src.frames`）:

        長尺 134本   1行目の頭4文字  「計算しま」 **84%** ＝ 実効 **2.4本ぶん**
                     最終行の頭4文字 「明日やる」 **61%** ＝ 実効 **3.8本ぶん**
        ショート 558本 最終行の頭4文字「あなたの」 **45%**
                     最終行の末尾6文字「てください。」**40%**

    **中身は散っています**（題の族 526・出だしの形 689／694本。
    `legacy_corpus.variety()`）。**揃っていたのは枠だけ**で、
    YouTube が収益化の対象外に置くのは、まさにそこです ——
    "generic or unoriginal templates **giving the impression of mass production**"。

    ## **入口だけでは閉じません**（解除条件1・2 と同じ形）

    入口は `script_writer.opening_form()` / `closing_form()` の振り分けです。
    **が、振り分けは指示文の一部でしかなく、書き手はそこから外れられます。**
    実際、揃っていた 84% / 61% / 45% は**指示文に直書きされた文句の写し**でした。
    **入口だけを塞ぐと、次に指示文を書き換えた回が黙って穴を開け直せます。**

    だから出口にも同じ門を置きます。**`script_only_problems()` に入れてあるので、
    22本のクリップを焼く前**に当たります。

    ## 何と比べるか

    **直近 {FRAME_WINDOW}本の控え**（同じ向きだけ）。生涯の平均ではありません ——
    ポリシーの原文が「同じチャンネルの動画を**続けて数本視聴した後**、
    繰り返しのように感じられる」と言っているのは、並びの話だからです。

    **`topic_id` を渡すこと。** 渡さないと、撃ち直した自分の前の案を相手にします
    （`script_writer.used_bars()` が同じ理由で同じことをしています）。

    ## **この門が当たる所と、当たらない所**（2026-08-30 に実測した。**隠さない**）

    控えの旧い本を「これから出す本」として当て直すと、こうなりました:

        長尺    80本中 **78本 が落ちる**（1行目「計算しま」が窓の 80%、
                最終行「明日やる」が 55%）
        ショート 80本中 **0本**

    **ショートに当たらないのは、閾値が 0.5 で、実測が 45% だからです**
    （最終行の頭「あなたの」）。**これは見落としではなく、そう決めた結果です** ——
    0.4 まで下げれば当たりますが、4通りの振り分けでは期待 25% に対し
    20本の窓で 40% を超える確率が **10%** あり、**10本に1本が
    「たまたま偏った」で書き直しになります**（1回 約250秒）。

    **だからショート側を締めているのは、この門ではなく入口のほう**です ——
    `script_writer.CLOSING_RULES` の4通りが**全部「あなたの◯◯は」で
    始めるなと言っている**ので、割り当ての上限がそのまま 30% になります。

    **覆る条件**: 再開後にショートの最頻が 50% を超えたら、この門が拾います。
    45% のまま動かないなら、**窓と閾値を一緒に動かすこと**
    （窓 40本・閾値 0.4 なら誤検知は 2.6%）。片方だけ動かすと誤検知が跳ねます。

    ## **覆る条件**

    - 振り分けの通り数を4から増やしたら、`FRAME_MAX_SHARE` を引き下げること
      （4通りで 0.5 は「期待の2倍」。8通りなら 0.3 が同じ厳しさです）
    - 見る場所（頭4文字・末尾6文字）は `src/frames.py` の定数です。
      **こちらに写さないこと** —— 2か所に置くと、片方だけ動かしたときにずれます
    """
    if not script:
        return []
    segs = script.get("segments") or []
    narration = [str(s.get("narration") or "") for s in segs]
    mine = frames.axes(narration)
    if not mine:
        return []

    history = frames.recent(k=FRAME_WINDOW, portrait=portrait, exclude=topic_id)
    if len(history) < FRAME_MIN_HISTORY:
        print(f"[verify] 枠の重なりは判定していません（直近の控えが {len(history)}本 で、"
              f"{FRAME_MIN_HISTORY}本 に足りません）")
        return []

    sigs = [frames.axes(h.get("narration") or []) for h in history]
    sigs = [s for s in sigs if s]
    problems: list[str] = []
    labels = {"opening": "読み上げ1行目の頭", "closing": "最終行の頭",
              "closing_tail": "最終行の末尾"}
    for ax, label in labels.items():
        same = sum(1 for s in sigs if s.get(ax) == mine[ax])
        share = same / len(sigs)
        if share > FRAME_MAX_SHARE:
            problems.append(
                f"{label}が {mine[ax]!r} で、**直近{len(sigs)}本のうち {same}本"
                f"（{share:.0%}）が同じ**です。"
                f"**続けて数本 見た人には、同じ動画の作り直しに見えます**"
                f"（YouTube はそれを収益化の対象外にしています）。"
                f"この本だけ、そこの言い回しを変えること"
                f"（型そのものは `script_writer.{'opening' if ax == 'opening' else 'closing'}_form()`"
                f" がテーマIDで決めていて、変えられません）"
            )
    problems += _check_screen_frame_repeat(script, history)
    return problems


def _check_screen_frame_repeat(script: dict | None,
                               history: list[dict]) -> list[str]:
    """**画面の側**の同じ門（2026-08-30 夜に足した。上の門の続き）。

    ## なぜ別に要るか（**実測で、読み上げより揃っていました**）

    上の門は `frames.axes()` ＝ **読み上げ**しか見ていません。
    控えの `*.plan.json` を同じ 4文字で測ると、こうです
    （`python -m src.frames`・API 0単位）:

        長尺 134本    読み上げの最終行の頭「明日やる」 61%
                      **画面の最後のコマの見出し「明日やる」 83%**（実効 2.1本ぶん）
        ショート 521本 画面の同じ所が「あなたの」29% ＋「あなたは」25%

    **視聴者が続けて数本 見て最初に気づくのは、耳より目のほうです。**
    そして解除条件3を閉じた回は、入口（`OPENING_RULES`/`CLOSING_RULES`）も
    出口（上の門）も**読み上げの文だけ**を相手にしていました ——
    つまり **「読み上げは4通りに散ったが、画面には同じ見出しが並ぶ」が素通り**します。

    ## 比べ方（上の門と同じ。**定数を写さないこと**）

    窓・閾値・頭の文字数は上と同じものを使います（`FRAME_WINDOW` /
    `FRAME_MAX_SHARE` / `frames.SCREEN_CLOSE_HEAD`）。
    **履歴の側は `<video_id>.plan.json`** で、`<id>.json` とは**別々に欠けます**
    （`build_perf` の註）。読めた本が `FRAME_MIN_HISTORY` に足りなければ、
    **「合格」ではなく「判定していない」と印字して黙ります**（`src/bars.py` と同じ扱い）。

    ## この門が見ないもの

    **1枚目の `kind`**（実測で長尺もショートも 100% `stat`）は、揃っていても
    落としません —— 4通りの入り方が**どれも結論の数字を先に言い切れ**と
    言っているので、そこは維持率の要件そのものです（`frames.screen_axes` の docstring）。

    ## 覆る条件

    - 割った後のコマ（`slides_plan.json`）は見出しに `2/2` や `＋…` が付きますが、
      **頭4文字は動きません。** 付く場所が頭に変わったら、この門は誤検知します
    - 画面の軸を増やすなら `frames.SCREEN_AXES` に足すこと。**ここに写さない**
    """
    if not script:
        return []
    plan = [dict(s.get("visual") or {}) for s in (script.get("segments") or [])]
    mine = frames.screen_axes([p for p in plan if p])
    if not mine:
        return []

    sigs = []
    for h in history:
        vid = str(h.get("video_id") or "")
        if not vid:
            continue
        s = frames.screen_axes(frames.plan_of(vid))
        if s:
            sigs.append(s)
    if len(sigs) < FRAME_MIN_HISTORY:
        print(f"[verify] 画面の枠の重なりは判定していません（直近の控えのうち "
              f"*.plan.json が読めたのは {len(sigs)}本 で、{FRAME_MIN_HISTORY}本 に足りません）")
        return []

    problems: list[str] = []
    for ax in frames.SCREEN_AXES:
        same = sum(1 for s in sigs if s.get(ax) == mine[ax])
        share = same / len(sigs)
        if share > FRAME_MAX_SHARE:
            problems.append(
                f"**最後のコマの見出し**が {mine[ax]!r} で、**直近{len(sigs)}本のうち "
                f"{same}本（{share:.0%}）が同じ**です。"
                "**読み上げを変えても、画面に同じ見出しが並べば同じ動画に見えます**"
                "（実測で、画面の側のほうが読み上げより揃っていました: 83% 対 61%）。"
                "締め方の型（`script_writer.closing_form()`）に合わせて、"
                "**見出しのほうも書き換えること**"
            )
    return problems


#: **動画を作らなくても分かる検査**（`check` と `src/pipeline.py` が同じものを撃つ）。
def script_only_problems(script: dict | None, portrait: bool) -> list[str]:
    """**script.json だけで判定できる不備。レンダリングの前に当てるためのもの。**

    ## なぜ要るか（2026-08-29 に、同じ本で **2回** 踏んで足した）

    `src/script_writer.generate()` は書き直しの輪を **3回**まわし、
    それでも残ったときに、こう印字して**台本をそのまま返します**:

        [script] 警告: N件がまだ残っています。パイプラインが合成前に止めます

    **止まりません。** `src/pipeline.py` は、そのあと
    スライドを焼き、22本のクリップを焼き、音声を合成し、字幕を焼き込んで、
    **いちばん最後の `check()` で落とします**（実測 **1本 15分**）。
    `batch_build` は1回 作り直すので、**1本の失敗に 30分**かかります。

    実測（2026-08-29 18:5x・`kouki-jougen-89000-sagaru`）:

        [render] クリップ 22/22 → 字幕焼き込み + 音声合成
        VerificationError: **前提として『率』を出しているのに、
                            その値が画面のどこにもありません。**

    **この指摘は `_check_assumption_value_shown(script)` で、引数は script だけ**です
    —— 動画も画像も見ていません。**16分 前に同じ答えが出せました。**

    ## ここに何を入れるか

    **`check()` が `script` **だけ**を引数に取る検査**です。
    `work`（焼いた画像・過去の控え）や `duration`（尺）を要るものは入れません
    —— それらは作らないと分からないので、**早く当てようがありません。**

    **`check()` は、この関数を呼びます。** 並べ直さないこと ——
    ここと向こうで別々に並べると、**片方だけ増えたときに静かにずれます**
    （`tests/test_script_gate_before_render.py` が、その日に赤くなります）。
    """
    problems: list[str] = []
    if portrait:
        problems += _check_short_opening(script)
    problems += _check_visual_wrap(script, portrait)
    problems += _check_count_matches(script)
    problems += _check_adjacent_repeat(script)
    problems += _check_formula_shown(script)
    problems += _check_assumption_value_shown(script)
    problems += _check_yomi(script)
    problems += _check_no_human_expert_claim(script)
    problems += _check_frame_repeat(script, portrait)
    return problems


def check(path: Path, video_cfg: dict, min_minutes: float, work: Path,
          topic: dict | None = None) -> float:
    """問題があれば VerificationError。無ければ尺（秒）を返す。"""
    probe = _probe(path)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(probe.get("format", {}).get("duration") or 0)
    width, height = video_cfg["resolution"]

    problems: list[str] = []
    if not video:
        problems.append("映像トラックが無い")
    if not audio:
        problems.append("音声トラックが無い")
    if duration < min_minutes * 60:
        problems.append(
            f"尺が {duration / 60:.1f}分 で下限の {min_minutes}分 未満"
            "（8分を切るとミッドロール広告を入れられない）"
        )
    if video and (int(video.get("width", 0)) != width or int(video.get("height", 0)) != height):
        problems.append(f"{video.get('width')}x{video.get('height')} で、期待は {width}x{height}")

    # 先頭が真っ黒なら、素材の生成か合成のどこかが黙って失敗している。
    # 一様な画は PNG にするとほとんど圧縮されるので、バイト数で判定できる。
    if video:
        frame = work / "_first.png"
        run(["ffmpeg", "-y", "-v", "error", "-ss", "0.4", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=160:90", str(frame)])
        size = frame.stat().st_size if frame.exists() else 0
        frame.unlink(missing_ok=True)
        if size < 1200:
            problems.append(f"冒頭のフレームが真っ白か真っ黒に見える（{size} バイト）")

    problems += _check_thumbnail(work)
    problems += _check_subtitles(work)

    script = None
    script_path = work / "script.json"
    if script_path.exists():
        try:
            script = json.loads(script_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"script.json が読めない: {exc}")
    # ショート（縦画面）は1本＝1つの計算結果なので chart の下限は当てない。
    # 代わりに、冒頭が大きい数字1つで始まっているかを見る。
    portrait = height > width
    problems += _check_slides(work, None if portrait else script)
    # **動画を作らなくても分かるぶんは、1か所にまとめてあります**（2026-08-29）。
    #     `src/pipeline.py` が**レンダリングの前に**同じ関数を撃つので、
    #     ここと向こうが別々に並べていると、**片方だけ増えたときに静かにずれます。**
    #     （実害は `script_only_problems` の docstring。1本 15分 × 2回）
    problems += script_only_problems(script, portrait)
    if portrait:
        problems += _check_headline_from_calc(work, script)
        problems += _check_short_pace(script, duration)
        problems += _check_slide_hold(work, duration)
        # **上限と下限は必ず並べて置くこと**（2026-08-27）。
        # 片方だけだと、検査そのものが速いほうへ押します（`_check_reveal_hold`）。
        problems += _check_reveal_hold(work)
        problems += _check_assumptions_on_screen(work)
    # **これは `portrait` の外に出しています**（2026-08-26 に実測して移した）。
    # 中に置いていた間、**長尺は1本も通っていませんでした** ——
    # 控え430本で、門の入った 08/17 より後の漏れは
    # **ショート 0/397・長尺 7/33（21%）で、100% が長尺**。
    # `CLAUDE.md`「4,000時間の門に入るのは長尺だけ」＝
    # **収益化を背負っている側だけが無検査**でした。
    # 誤報は 10件を目で確かめて 0件（詳しくは関数の docstring）。
    problems += _check_narrated_shown(work, script)
    problems += _check_title_from_calc(work, script, topic)
    problems += _check_form_tag(script, duration)
    problems += _check_not_repeat(work, script)
    problems += _check_adjacent_frames(work)
    problems += _check_law_citation_verbatim(work, script)

    if problems:
        raise VerificationError("投稿前の検査に落ちました: " + " / ".join(problems))

    codec = audio.get("codec_name") if audio else "?"
    charts = 0
    if script:
        charts = [s.get("visual", {}).get("kind") for s in script.get("segments", [])].count("chart")
    print(
        f"[verify] 合格: {duration / 60:.1f}分, {video.get('width')}x{video.get('height')}, "
        f"音声 {codec}, chart {charts}枚, サムネ・字幕とも異常なし"
    )
    return duration
