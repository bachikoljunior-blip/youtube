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

from .subtitles import _NUM_TOKEN
from .util import require, run

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
    lines = [r[9].strip() for r in rows if len(r) == 10]
    if not lines:
        return ["字幕に1行も入っていない"]

    problems = []
    orphans = [t for t in lines if t and not re.search(r"[^\s。、！？…・]", t)]
    if orphans:
        problems.append(f"記号だけの字幕行が {len(orphans)} 行ある（例『{orphans[0]}』）")

    # 行末と次の行頭が両方とも数字・単位なら、かたまりの途中で割れている。
    split_nums = [
        (a, b) for a, b in zip(lines, lines[1:])
        if a and b and a[-1] in _NUM_TOKEN and b[0] in _NUM_TOKEN
    ]
    if split_nums:
        a, b = split_nums[0]
        problems.append(f"数字の途中で改行している箇所が {len(split_nums)} 件（『{a}』→『{b}』）")
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
        return []

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
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*万\s*(\d[\d,]*)?\s*千?", text):
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
    kind = (segments[0].get("visual") or {}).get("kind")
    if kind != "stat":
        return [
            f"ショートの1枚目が {kind} になっている（stat であること）。"
            "最初の1画面で離脱が決まるので、冒頭は大きい数字1つにする"
        ]
    return []


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

    if script:
        kinds = [s.get("visual", {}).get("kind") for s in script.get("segments", [])]
        charts = kinds.count("chart")
        if charts < MIN_CHARTS:
            problems.append(
                f"chart が {charts} 枚しかない（下限 {MIN_CHARTS} 枚）。"
                "計算結果で図の形を変えるのが量産テンプレート判定との分かれ目"
            )
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
    if portrait:
        problems += _check_short_opening(script)
        problems += _check_headline_from_calc(work, script)
        problems += _check_short_pace(script, duration)
    problems += _check_count_matches(script)
    problems += _check_title_from_calc(work, script, topic)
    problems += _check_not_repeat(work, script)

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
