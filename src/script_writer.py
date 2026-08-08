"""Claude Code CLI で動画台本とメタデータを生成する。

Anthropic API は使わない。サブスクリプションのセッション内で思考させ、
結果を JSON で受け取って pydantic で検証する。
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from . import config
from .claude_cli import ask, follow_up

# 日本語 TTS の実測。speaking_rate=1.0 でおよそこのくらい進む。
#
# 公開・生成した11本を実測したところ **平均 322 字/分・最も遅いもので 297 字/分** だった。
# 数字が主役のチャンネルなので「163万9800円」のような並びが多く、字数のわりに遅い。
#
# ここで1つの値を使うと、下限と上限のどちらかで必ず危険側に外れる。
#   下限（長尺の8.5分）… 速いほうで見積もる → 字数が多くなる → 尺は確実に足りる
#   上限（ショートの60秒）… 遅いほうで見積もる → 字数が少なくなる → 確実に収まる
# だから向きごとに分ける。実際に 360 の一本値でショートが 84秒・66秒と溢れた。
CHARS_PER_MINUTE = 360.0        # 下限を決めるとき（速い側）
CHARS_PER_MINUTE_SLOW = 297.0   # 上限を決めるとき（遅い側・実測の最遅）

# ショートの1セグメントの上限（文字）。**`src/pipeline.py` の
# MAX_SHORT_SEGMENT_CHARS と同じ値にすること。** ずれると、生成側が通した
# ものをパイプラインが落とす（またはその逆）。
# 12秒 × 5.2文字/秒 = 62文字。読み上げの速さは 2026-08-09 の実測。
SHORT_SEGMENT_CHARS = 62


def short_script_problems(script, topic_id: str = "") -> list[str]:
    """ショートの台本の不備を並べる。空なら合格。

    **ここが唯一の正本。** `generate()` は生成中にこれを見て直させ、
    `src/pipeline.py` は音声合成の前にこれを見て落とす。
    **2つの場所に同じ規則を書かない**（片方だけ直す形を 2026-08-08〜09 に
    5回やっている）。

    直させる側と落とす側で条件がずれると、**生成側が通したものを
    パイプラインが落とし続ける**。実際 2026-08-09、長さだけを直させていて
    「明日やること」を返していなかったため、長さが直った台本が
    別の理由で落ち続けた。

    **さらに `verify` との間にも同じずれがあった。** ここは長さしか見ず、
    `verify` は「1枚目が stat か」「過去の図と重なっていないか」まで見る。
    そのため長さの直った台本が**レンダリングまで終わってから**落ちた。
    **台本だけで判定できるものは、全部ここに集める。**
    `verify` は最後の砦として残す（音声や画像が絡むものはあちらでしか見えない）。
    """
    problems = []
    for i, seg in enumerate(script.segments):
        n = len(seg.narration)
        if n > SHORT_SEGMENT_CHARS:
            problems.append(
                f"{i}番目のセグメントが{n}文字（上限{SHORT_SEGMENT_CHARS}）。"
                f"読み上げ約{n / 5.2:.0f}秒で、1枚の絵が12秒以上止まります"
            )
    # **2枚目が「前提」だと、5秒で動画が再スタートして離脱する**（8/9 実測）。
    # 指示に書いても守られないので機械で見る。前提そのものは残す（後ろに置く）。
    if len(script.segments) > 1:
        head2 = (script.segments[1].visual.headline or "") + script.segments[1].narration[:24]
        if "前提" in head2:
            problems.append(
                "2枚目が「前提」になっています。**ここで動画が再スタートし、"
                "5秒地点で離脱します**（2026-08-09 実測、3本とも4.7〜5.7秒で最大の落差）。"
                "前提は残したまま**後ろへ移し**、2枚目は結論の内訳や次の疑問にすること"
            )
    if script.segments and "明日やること" in script.segments[-1].narration:
        problems.append(
            "最後のセグメントに「明日やること」が入っています。"
            "これは長尺だけの型です。ショートの最後は手順ではなく、"
            "**この場所で毎回何が手に入るか**を1つ言うだけにしてください"
        )

    # `verify` が持っている検査のうち、**台本だけで判定できるもの**をここでも当てる。
    # 関数はあちらから借りる（同じ規則を2か所に書かない）。
    from . import config, verify

    data = script.model_dump()
    problems += [p.strip() for p in verify._check_short_opening(data)]
    if topic_id:
        problems += [p.strip() for p in
                     verify._check_not_repeat(config.BUILD_DIR / topic_id, data)]
    return problems


class Bar(BaseModel):
    """kind=chart の棒1本。src/calc の計算結果から作る。"""

    label: str = Field(
        description=(
            "棒の左に出す見出し。全角7文字以内。"
            "**語を途中で切らないこと。** 入りきらないなら短い別の言い方にする。"
            "2026-08-08、『同居特別障害者控除』を『同居特別障害』と切って書き、"
            "画面に日本語として成立しない文字列が出た。"
            "『同居特別』『同居の親族』のように、短くても完結した語にすること"
        )
    )
    value: float = Field(description="棒の長さを決める数値。最大値が全幅になる")
    display: str = Field(description="棒の上に出す文字。『12万6千円』のように読める形で")


class Visual(BaseModel):
    """このセグメントで画面に出す図解。フリー素材ではなく自前で描く。"""

    kind: str = Field(description="stat / table / steps / compare / chart のいずれか")
    headline: str = Field(description="画面上部の見出し。全角18文字以内")
    stat: str = Field(default="", description="kind=stat のとき中央に大きく出す数字。例『約7万7千円』。他の kind では空")
    note: str = Field(default="", description="kind=stat のとき数字に添える条件。例『年収600万・扶養なし』")
    stat_source: str = Field(
        default="",
        description=(
            "kind=stat のとき、その数字の出どころ。**上の計算結果から該当箇所をそのまま写す**"
            "（例『ずれ 31か月』『123,980円』）。言い換えず、表示されているとおりに写すこと。"
            "計算結果に無い数字（制度の項目数・条文番号など）を stat に出してはいけません。"
            "他の kind では空"
        ),
    )
    items: list[str] = Field(
        default_factory=list,
        description="kind=steps は手順を3〜4個、kind=compare は対比を2〜4個。各全角24文字以内。他の kind では空",
    )
    headers: list[str] = Field(default_factory=list, description="kind=table の列名を2〜3個。他の kind では空")
    rows: list[list[str]] = Field(
        default_factory=list,
        description="kind=table の行を2〜4個。各セルは全角12文字以内。他の kind では空",
    )
    bars: list[Bar] = Field(
        default_factory=list,
        description="kind=chart の棒を2〜6本。src/calc で計算した結果をそのまま入れる。他の kind では空",
    )


class Segment(BaseModel):
    narration: str = Field(description="読み上げる文章。1〜3文。話し言葉。記号や箇条書き記号は使わない")
    visual: Visual = Field(description="このセグメントで表示する図解")


class Chapter(BaseModel):
    segment_index: int = Field(description="このチャプターが始まるセグメントの0始まりの番号")
    label: str = Field(description="チャプター名。全角14文字以内")


class VideoScript(BaseModel):
    title: str = Field(description="採用するタイトル。全角32文字以内。数字と具体名を入れる。煽らない")
    title_alternatives: list[str] = Field(description="A/Bテスト用の別案を2つ")
    description_body: str = Field(description="説明欄の本文。3〜5行の要約＋出典の探し方。URLは書かない")
    tags: list[str] = Field(description="検索タグを10〜15個。日本語中心。1語あたり全角20文字以内")
    thumbnail_line1: str = Field(description="サムネ1行目。全角9文字以内。一番強い数字か結論")
    thumbnail_line2: str = Field(description="サムネ2行目。全角9文字以内")
    first_comment: str = Field(
        description="投稿直後に自分で書き込むコメント。本編の要点を数字ごと3行でまとめ、最後に視聴者へ問いかけを1つ。200文字以内。宣伝や依頼は書かない"
    )
    segments: list[Segment] = Field(description="本編。冒頭は結論、次に条件、最後に手順の順で並べる")
    chapters: list[Chapter] = Field(description="チャプター4〜7個")


ROLE = """あなたは日本語YouTubeの動画の構成作家です。

この動画は「制度の解説」ではありません。**自分で計算した結果を発表する動画**です。
ここを取り違えないでください。

なぜか。YouTube は「クリエイターならではの率直な洞察や視点が追加されておらず、
汎用的または独創性のないテンプレートを使用して作成され、大量生産されたような印象を
与える AI 生成コンテンツ」と「自分で作成していない他の資料の内容を読み上げただけの
コンテンツ」を収益化の対象外にしています。制度をまとめ直した解説は、どれだけ丁寧でも
後者に落ちます。収益化されなければ、この動画の価値はゼロです。

だから毎回、src/calc に計算を実装し、**どこにも公開されていない数字**を出してください。
その数字が動画の主役です。解説は、その数字を理解させるための補助です。

**このリポジトリの存在は、台本・説明欄・コメント・タイトルのどこにも書かないこと。**
リンクも名前も匂わせも書かない。「コードを公開しています」とも書かない。
検証可能性は、前提と計算式を画面に出すことで担保します。

必ず入れること:
- 冒頭で、計算して分かったことを数字ごと言い切る。「調べてみました」ではなく「計算しました」。
- 途中で一度、**計算の前提**を画面と音声の両方で明示する。src/calc の ASSUMPTIONS をそのまま使う。
  前提を隠さないことが、この動画の信頼の全部です。
- 終盤で、その数字が視聴者自身の場合にどう変わるかを言う。

守ること:
- 視聴維持率がすべて。冒頭の1セグメント目で「この動画で分かる結論」を数字ごと言い切る。前置き・自己紹介は書かない。長尺では登録の依頼も書かない（維持率が落ちる）。
- 一般論を書かない。金額・割合・期限・書類名など、検証可能な具体を必ず入れる。
- 制度や数字には必ず適用条件を添える。「年収600万・扶養なしの場合」のように。
- 断定できないことは「〜の場合が多い」と書く。絶対・確実・必ず儲かる、は使わない。
- 読み上げ用なので、括弧書き・箇条書き記号・URL・英数字の羅列は narration に入れない。数字は「およそ48万円」のように読める形で書く。
- 各セグメントの narration は 60〜160文字。短く切ってテンポを作る。
- **長尺のみ**: 最後のセグメントは「明日やること」を3つ、手順として言う。
  ショートでは違う（下のショート規則を見ること）。**両方を満たそうとしないこと。**

画面（visual）:
- ナレーションの内容を図解にする。ナレーションの繰り返しにしない。
- 数字を1つ言い切る場面は kind=stat、条件で答えが変わる場面は kind=table、
  やることを並べる場面は kind=steps、二択を比べる場面は kind=compare、
  **計算結果の大小を見せる場面は kind=chart** を使う。
- chart は計算した数字から作る。棒の長さが結果そのものになるので、回ごとに図の形が変わる。
  **1本の動画に chart を最低3枚は入れてください。** これが「テンプレートの繰り返し」との
  分かれ目になります。
- 全部を stat にしない。table と steps と chart が合わせて半分は欲しい。
- table は視聴者が一時停止して読む場所になる。行と列を絞り、数字を入れる。

ショート（--short で作るとき）だけの規則:

- 60秒以内。ナレーション合計およそ300文字。1本＝1つの計算結果に絞る。
- **1セグメントの narration は60文字以内。** ここが一番大事です。
  読み上げは**1秒あたり約5.2文字**（2026-08-09 実測）なので、60文字＝約11.5秒。
  1枚の絵が12秒を超えて止まると検査で落ちます。
  **「セグメントを6個以上」だけでは足りません。** 2026-08-09、6個で作ったのに
  1つが92文字あり、合計465文字＝89秒、1枚15秒で落ちました。
  **枚数ではなく1枚あたりの長さが効きます。**
- セグメントは6〜8個。1つの計算結果を、結論→前提→内訳→自分の場合→次、と刻む。
- **2枚目に「計算の前提」を置かないこと。ここが最大の欠陥です。**
  2026-08-09 の実測: 3本とも **4.7〜5.7秒で最大の落差**、9.4秒で維持率50%割れ。
  内容が違うのに秒数がほぼ一致するので、**題材ではなく構造の問題**。
  5秒は1枚目（結論の数字）が終わる地点で、そこで「まず前提を説明します」と
  **動画が再スタートする。** 視聴者は答えを受け取り、かつ「ここから長い」と判断する。
  **前提は残す**（数字の裏取りは この作りの根幹）**が、置く場所を後ろにする。**
  画面には出し、ナレーションは結論の直後から内訳へ進むこと。
- **1枚目の結論は、完全に決着させないこと。**
  「20万2095円戻ります」で終えず、「20万2095円。**ただし総所得で足切りが変わる**」の
  ように、次の疑問を残す。答えを渡し切ると5秒で見る理由が消える。
- **最後の1セグメントは「このチャンネルが何をする場所か」だけを言うこと。**
  ここに手順や確認方法を入れない（それは1つ前のセグメントでやる）。
- **「明日やること」という言い方をショートで使わないこと。** これは長尺だけの型です。
  上の「長尺のみ」の項に釣られて 2026-08-09 に2回続けて混入し、
  **機械の検査で2回とも落ちました**（`src/pipeline.py` の `_check_short_script`）。
  ショートの最後は手順ではなく、**この場所で毎回何が手に入るか**を1つ言うだけ。

  **2026-08-07 に測って分かった。** 平均視聴率は 51〜102%（102%は繰り返し見られている）
  なのに、856人が最後まで見て**登録は0人**だった。一般的な0.5%なら期待4.3人。
  **最後まで見られているのに登録されない。** つまり動画の出来ではなく、
  **「このチャンネルを登録する理由」が伝わっていない。**

  それまでは「次に何の数字が得られるか」を予告していた（例:「同じ条件を年齢べつに
  全部計算したものが別にあります」）。**これは効かなかった。** 1本の続きを示しても、
  チャンネルを登録する理由にはならない。

  代わりに**この場所の性格**を言う。「毎朝1本、制度の境界をまたぐと金額でいくら
  変わるかを、前提ごと計算して出しています」のように、**何が毎回手に入るのか**を
  1文で示す。チャンネル名からは何のチャンネルか分からないので、ここで補う。

- ただし「チャンネル登録お願いします」とは書かない。依頼ではなく**説明**にする。
- **1つ目のセグメントの visual は必ず kind=stat にすること。** ここは例外なし。
  ショートは最初の1画面で離脱が決まるので、冒頭は大きい数字1つだけを出す。
  chart や table で始めない。棒グラフは読むのに時間がかかり、2秒では入らない。
  検査で落ちるので、守らないと作り直しになる。

タイトル:
- 検索されそうな語を前半に置く。クリックベイトにしない。
- 全角32文字以内。「」や【】は使わない。
- ショートは末尾に #Shorts を付ける。
"""

TASK = """次の条件で動画1本ぶんの台本を作ってください。

# チャンネル
名前: {channel_name}
扱う領域: {niche}
想定視聴者: {audience}

# 書き手の人格
{persona}

# 扱わないこと
{avoid}

# 今回のテーマ
{topic_title}
切り口: {topic_angle}
{calc_block}

# 尺
narration の合計を {min_chars}〜{max_chars} 文字にしてください。
これは読み上げて約{target_minutes}分になる分量です。セグメント数は {min_segments}〜{max_segments} 個が目安。
文字数が足りないと動画が短くなり収益化条件を満たさないので、必ず下限を超えてください。
"""


def _total_chars(script: VideoScript) -> int:
    return sum(len(s.narration) for s in script.segments)


def used_bars(exclude: str = "") -> list[str]:
    """これまでの動画で chart に出した数値を集める。

    `exclude` に自分のテーマIDを渡すこと。**作り直しで捨てた自分の台本まで
    禁止してしまう**（2026-08-07、繰上げを撃ち直したら前回案の「43万2千円」が
    使用済み扱いになり、訴求の弱い「0.76倍」に逃げた）。
    見たいのは**他の動画と被っていないか**であって、自分の過去案ではない。

    **台本を書く側は過去の動画を知らない。** だから同じ calc を使うと、
    同じ行を選んで同じ図を出す。2026-08-07、年金の繰上げが繰下げと
    3本同じ棒を出した（`180万円・255万6千円・331万2千円`）。
    違いは配色だけで、**ポリシーの「繰り返しのように感じられるコンテンツ」**に当たる。

    `verify.py` が投稿前に止めるが、**止めるだけでは作り直しが繰り返される。**
    先に「これは使用済み」と伝えて、別の行を選ばせる。
    """
    import json

    seen: set[str] = set()
    build = config.ROOT / "build"
    if not build.exists():
        return []
    for path in sorted(build.glob("*/script.json")):
        if exclude and path.parent.name == exclude:
            continue
        try:
            script = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for seg in script.get("segments") or []:
            v = seg.get("visual") or {}
            if v.get("kind") == "chart":
                for b in v.get("bars") or []:
                    if b.get("display"):
                        seen.add(str(b["display"]))
    return sorted(seen)


def calc_block(topic: dict) -> str:
    """テーマに紐づいた計算を実行して、その出力をそのまま台本の材料にする。

    これが無いと台本を書く側は数字を**発明する**しかない。裏の取れない数字を
    動画に入れないという方針に対して、これは致命的な穴だった。実際これまでは
    常駐セッションが手で台本を書くことで塞いでいたが、それでは自動で回らない。

    topics.yaml に `calc: モジュール名` を書いておくと、`python -m src.calc.<名前>`
    を実行して、標準出力と ASSUMPTIONS を丸ごとプロンプトに入れる。
    台本を書く側は**そこにある数字しか使えない**。
    """
    name = str(topic.get("calc", "")).strip()
    if not name:
        return ""

    import importlib
    import subprocess
    import sys

    try:
        module = importlib.import_module(f".calc.{name}", package="src")
    except ImportError as exc:
        raise RuntimeError(f"テーマ {topic['id']} の calc: {name} が読み込めません: {exc}") from exc

    # 表の取り違えはここで止める。壊れた数字で台本を書かせない。
    if hasattr(module, "check_tables"):
        module.check_tables()

    proc = subprocess.run(
        [sys.executable, "-m", f"src.calc.{name}"],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"src.calc.{name} が失敗しました: {proc.stderr[-500:]}")

    # **数字が1つも出ていないなら、この仕組みは何も守っていない。**
    # 2026-08-05 に発覚: kojo・shitsugyo・zangyo は関数を定義するだけで
    # `__main__` が無く、標準出力が空だった。calc_block は空のコードブロックを
    # 返し、台本を書く側は「使ってよい数字」がゼロの状態で書いていた。
    # つまり**数字を発明させないために作った仕組みが、半分のテーマで開いていた。**
    # 静かに通すのが一番悪い。ここで止める。
    if not re.search(r"\d", proc.stdout):
        raise RuntimeError(
            f"src.calc.{name} が数字を1つも出力していません。"
            f"`python -m src.calc.{name}` で表が出るように `__main__` を書くこと。"
            "空のまま台本を書かせると、数字を発明させることになります"
        )

    assumptions = getattr(module, "ASSUMPTIONS", [])
    used = used_bars(exclude=str(topic.get("id", "")))
    used_block = ""
    if used:
        used_block = (
            "\n# すでに他の動画で出した数値（**これらを chart に使わないこと**）\n\n"
            "同じ数値の棒を並べると、チャンネルを続けて見た人に「繰り返し」と映ります。\n"
            "YouTube はそれを収益化の対象外にしています。**別の行を選んでください。**\n"
            "2本以上が一致すると投稿前の検査で落ちて、作り直しになります。\n\n"
            "```\n" + "・".join(used[:60]) + "\n```\n"
        )
    return f"""
# この動画で使う数字（計算済み）

**ここに出ている数字だけを使ってください。** 数字を自分で作らないこと。
足し算や割り算で新しい数字を導くのも禁止です。ここに無い数字が必要になったら、
その話題自体を落としてください。裏の取れない数字を動画に入れないためです。

```
{proc.stdout.strip()}
```

# 計算の前提（そのまま画面と音声に出すこと）

{chr(10).join(f"- {a}" for a in assumptions)}
{used_block}"""


def generate(channel: dict, topic: dict) -> VideoScript:
    """台本を1本生成する。尺が足りなければ同じセッションで書き足させる。"""
    cfg = channel["channel"]
    vid = channel["video"]
    model = channel["generation"]["model"]

    target = float(vid["target_minutes"])
    # 上限は「目標＋1.5分」を既定にするが、ショートではこの足し算が効かない。
    # 目標50秒に1.5分を足すと上限が2分22秒になり、**上限が無いのと同じ**になる。
    # 実際それで、60秒のつもりのショートが1.4分で出てきた。
    # max_minutes を明示できるようにして、ショート側から渡す。
    max_minutes = float(vid.get("max_minutes") or (target + 1.5))
    min_chars = int(float(vid["min_minutes"]) * CHARS_PER_MINUTE)
    max_chars = int(max_minutes * CHARS_PER_MINUTE_SLOW)
    if max_chars <= min_chars:
        raise RuntimeError(
            f"尺の上限({max_minutes}分)が下限({vid['min_minutes']}分)を下回っています。"
            "config/channel.yaml の max_minutes を見直してください"
        )

    prompt = ROLE + "\n" + TASK.format(
        channel_name=cfg["name"],
        niche=cfg["niche"],
        audience=cfg["audience"],
        persona=cfg["persona"].strip(),
        avoid="\n".join(f"- {a}" for a in cfg["avoid"]),
        topic_title=topic["title_seed"],
        topic_angle=topic["angle"],
        calc_block=calc_block(topic),
        min_chars=min_chars,
        max_chars=max_chars,
        target_minutes=target,
        min_segments=int(min_chars / 130),
        max_segments=int(max_chars / 80),
    )

    script, session = ask(VideoScript, prompt, model=model)
    chars = _total_chars(script)
    print(f"[script] 初稿: {len(script.segments)}セグメント / {chars}文字")

    if chars < min_chars and session:
        script, _ = follow_up(
            VideoScript,
            session,
            (
                f"narration の合計が{chars}文字しかなく、目標の{min_chars}文字に届いていません。"
                "内容を薄めずに、具体例・数値・手順・よくある間違いを足してセグメントを増やし、"
                "同じ JSON 形式で全体を出し直してください。"
            ),
            model=model,
        )
        chars = _total_chars(script)
        print(f"[script] 加筆後: {len(script.segments)}セグメント / {chars}文字")

    if chars < min_chars:
        print(f"[script] 警告: 目標{min_chars}文字に届きませんでした（{chars}文字）")

    # **ショートは1セグメントが長すぎると落ちる。** 短すぎる側には
    # 書き足させる仕組みがあるのに、**長すぎる側には無かった**（片方だけ）。
    # 2026-08-09、指示に「60文字以内」と書いても 86〜93文字で返ってきて、
    # 前倒し検査に3回続けて落ちた。**文章での指示は守られない。**
    # 落ちた事実を渡して、同じセッションで直させる。
    if max_minutes <= 1.5 and session:
        for attempt in range(3):
            problems = short_script_problems(script, topic.get('id', ''))
            if not problems:
                break
            print(f"[script] ショートの条件を満たしていません（{attempt + 1}回目）:")
            for p in problems:
                print(f"  - {p}")
            script, _ = follow_up(
                VideoScript,
                session,
                (
                    "**この台本は投稿前の検査に落ちます。** 直してください:\n"
                    + "\n".join(f"- {p}" for p in problems)
                    + "\n\n長すぎるセグメントは、**内容を削るのではなく分けてください。**"
                    f"2つに割り、それぞれ{SHORT_SEGMENT_CHARS}文字以内にする。"
                    "**割ったほうの visual は別のものにすること**"
                    "（同じ絵が2枚続くと、これも検査で落ちます）。\n"
                    "同じ JSON 形式で全体を出し直してください。"
                ),
                model=model,
            )
        remaining = short_script_problems(script, topic.get('id', ''))
        if remaining:
            print(f"[script] 警告: {len(remaining)}件がまだ残っています。"
                  "パイプラインが合成前に止めます")

    return script


if __name__ == "__main__":
    # 常駐セッションが台本を書くときに、この JSON スキーマに従わせる。
    #   python -m src.script_writer
    import json

    print(json.dumps(VideoScript.model_json_schema(), ensure_ascii=False, indent=2))
