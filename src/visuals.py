"""画面を自前で作る。

Simple のプロモ動画は自分のゲームを Playwright で録画して素材にしている。
うちは解説チャンネルで撮る対象が無いので、代わりに図解を HTML で組み、
同じく Chromium で撮る。フリー素材と違って完全に自前なので、
「量産された無個性コンテンツ」判定に対する材料にもなる。

出力は 2560x1440 の PNG。最終の 1920x1080 より大きく撮って縮小するので、
ゆっくり寄っても文字が甘くならない。
"""
from __future__ import annotations

import html
import math
import re
from pathlib import Path

VIEWPORT = (1280, 720)            # deviceScaleFactor=2 で 2560x1440 になる
VIEWPORT_PORTRAIT = (540, 960)    # 同 1080x1920。ショート向け
SCALE = 2

# 動画ごとに見た目を変えるための配色。テーマIDから決めるので、同じ回は毎回同じ、
# 別の回は必ず別になる。
#
# なぜ要るか: YouTube は「テンプレートを使用して作成されたと思われるコンテンツ」
# 「同じチャンネルの動画を続けて数本視聴した後、繰り返しのように感じられる
# コンテンツ」を収益化の対象外にしている。固定の1配色・固定の数種類の版面を
# 毎日繰り返すのは、まさにその見え方になる。
THEMES = [
    {"accent": "#ffcc00", "bg": "#10141c", "glow": "90,120,190"},    # 黄 × 紺
    {"accent": "#4dd8a0", "bg": "#0e1a18", "glow": "60,150,130"},    # 緑 × 深緑
    {"accent": "#ff8a5c", "bg": "#1a1310", "glow": "180,100,70"},    # 橙 × 焦茶
    {"accent": "#7aa8ff", "bg": "#0f1320", "glow": "80,110,200"},    # 青 × 藍
    {"accent": "#e879b0", "bg": "#19101a", "glow": "160,80,140"},    # 桃 × 紫
]


def theme_for(topic_id: str, index: int | None = None) -> dict:
    """配色を決める。

    index を渡すと、そこから順番に回す。**連続する回が必ず違う色になる**ので、
    こちらを使うこと。パイプラインは投稿済みの本数を渡している。

    index が無いときはテーマIDのハッシュで決める。ただしハッシュは偶然重なるので、
    連続が同じ色にならない保証はない。実際、最初は文字コードの和で割っていて、
    続けて出す2本が同じ緑になった。**「同じ絵を続けない」は保証が要る性質**なので、
    ハッシュは呼び出し側が本数を知らない場合の予備でしかない。
    """
    import hashlib

    if index is not None:
        return THEMES[index % len(THEMES)]
    if not topic_id:
        return THEMES[0]
    return THEMES[hashlib.md5(topic_id.encode("utf-8")).digest()[0] % len(THEMES)]


BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1280px; height: 720px; overflow: hidden; }
body {
  font-family: "Noto Sans CJK JP", "Noto Sans JP", "Hiragino Sans", sans-serif;
  background: {BG};
  color: #f2f4f8;
  display: flex; flex-direction: column;
  /* 下は字幕の帯を空ける。字幕は下端から 72px の位置に 64px の文字で焼かれる
     （subtitles.py の MarginV と Fontsize）。1080 換算で下 190px ぶんが字幕の
     領域なので、720 換算の 127px より下には何も置かない。 */
  padding: 64px 72px 136px 84px;
  position: relative;
}
body::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 12px;
  background: {ACCENT};
}
body::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(120% 90% at 78% 8%, rgba({GLOW},.22), transparent 60%);
}
.headline {
  font-size: 46px; font-weight: 900; letter-spacing: .01em;
  color: {ACCENT}; line-height: 1.25; margin-bottom: 34px;
}
.body { flex: 1; display: flex; flex-direction: column; justify-content: center; }

/* kind=stat — font-size は文字数から算出して差し込む（_stat_font_px）*/
.stat { font-weight: 900; line-height: 1.02; letter-spacing: -.02em; white-space: nowrap; }
.note { margin-top: 26px; font-size: 34px; font-weight: 700; color: #9fb0cc; }
/* 数字を伏せた1枚目だけ、補足が主役になる（`reveal_variants` の stat）。
   色も本文側へ寄せる —— 薄い灰色のままだと「注釈が1つ浮いている」画になる。 */
.note.lead { margin-top: 0; font-size: 66px; font-weight: 900; line-height: 1.35;
              color: inherit; letter-spacing: -.01em; }

/* kind=steps / compare */
ol, ul { list-style: none; display: flex; flex-direction: column; gap: 22px; }
li {
  display: flex; align-items: baseline; gap: 22px;
  font-size: 42px; font-weight: 700; line-height: 1.35;
}
li .marker {
  flex: 0 0 auto; min-width: 56px; height: 56px; border-radius: 12px;
  background: {ACCENT}; color: {BG};
  font-size: 30px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
}
.compare li .marker { background: #4d7cff; color: #f2f4f8; padding: 0 16px; }

/* kind=table */
table { width: 100%; border-collapse: collapse; font-size: 36px; }
th, td { padding: 18px 20px; text-align: left; }
th {
  font-size: 28px; font-weight: 900; color: {BG}; background: {ACCENT};
}
th:first-child { border-radius: 10px 0 0 10px; }
th:last-child  { border-radius: 0 10px 10px 0; }
td { font-weight: 700; border-bottom: 2px solid rgba(255,255,255,.10); }
tr:last-child td { border-bottom: none; }
td:first-child { color: #9fb0cc; }

/* **このコマで増えたぶん**（`fresh_flags`）。印は次のコマで前の行から外れて
   下へ移るので、画面の中で強調が1つ動きます。増えたのが見出しの文字だけだと
   「実質同じ画面」に見える、という独立評価9体ぶんの実測から。 */
tr.fresh td { background: rgba({GLOW},.30); color: #f2f4f8; }
tr.fresh td:first-child {
  color: {ACCENT}; border-radius: 8px 0 0 8px;
  box-shadow: inset 6px 0 0 {ACCENT};
}
tr.fresh td:last-child { border-radius: 0 8px 8px 0; }
/* 箇条書きは字だけなので、色を変えても塗り替わる面積がほとんどありません
   （実測 5.87% → 5.96%。表は 4.49% → 13.51% で効いていた）。**帯を敷きます。** */
li.fresh {
  color: {ACCENT};
  background: rgba({GLOW},.30);
  border-radius: 12px; margin: -10px -16px; padding: 10px 16px;
  box-shadow: inset 6px 0 0 {ACCENT};
}
li.fresh .marker { box-shadow: 0 0 0 6px rgba({GLOW},.45); }
.bar-row.fresh .bar-label { color: {ACCENT}; font-weight: 900; }
.bar-row.fresh .bar-track { box-shadow: 0 0 0 4px rgba({GLOW},.40); border-radius: 10px; }

/* kind=chart — 棒の長さは計算結果から決まるので、回ごとに形が変わる */
.chart { display: flex; flex-direction: column; gap: 20px; }
.bar-row { display: flex; align-items: center; gap: 20px; }
.bar-label {
  flex: 0 0 240px; text-align: right;
  font-size: 30px; font-weight: 700; color: #9fb0cc;
}
.bar-track { flex: 1; position: relative; height: 52px; }
.bar-fill {
  height: 100%; border-radius: 8px; background: {ACCENT};
  display: flex; align-items: center; justify-content: flex-end;
  padding-right: 16px; min-width: 4px;
  /* 棒の外に数字を出すとき、基準は棒そのもの。これが無いと track が基準になり、
     いつも右端の外へ飛んでいく。 */
  position: relative;
}
.bar-value { font-size: 30px; font-weight: 900; color: {BG}; white-space: nowrap; }
.bar-fill.thin .bar-value {
  color: #f2f4f8; position: absolute; left: calc(100% + 16px);
}
/* 目盛りの起点が0でないときの「途中を省いた」印。斜線の帯は図の作法そのもの。
   これを消すと、縮めた棒が0起点に見える＝誤解を与える図になる。 */
.bar-fill.broken::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 16px;
  border-radius: 8px 0 0 8px;
  background: repeating-linear-gradient(114deg, {BG} 0 5px, {ACCENT} 5px 10px);
}
.chart-base {
  margin-top: 18px; font-size: 26px; font-weight: 700; color: #9fb0cc;
}
/* 計算式。**この動画の根拠の半分がここ。** 前提だけでは視聴者が追試できず、
   式が画面に無いと「自分で計算した」証拠が画面のどこにも残らない
   （2026-08-15、独立評価の3体が独立に「計算式が画面に出ていない」と指摘）。
   本文の下・字幕の帯の上に、1行で置く。 */
.formula {
  margin-top: 24px; padding-left: 18px;
  border-left: 6px solid {ACCENT};
  font-size: 28px; font-weight: 700; line-height: 1.3;
  color: #cdd8ea; letter-spacing: .01em;
}
"""


CONTENT_WIDTH = VIEWPORT[0] - 84 - 72   # 左右の padding を引いた実効幅
STAT_MAX_PX = 172

# 縦向き（ショート）の上書き。横向きの CSS のあとに足して勝たせる。
#
# ショートは画面の下側に UI（タイトル・チャンネル名・ボタン）が重なるので、
# そこには何も置かない。字幕も subtitles.py 側で MarginV=420 まで上げてある。
PORTRAIT_CSS = """
html, body { width: 540px; height: 960px; }
/* 右は 96px。ショートのボタン列（いいね・コメント・共有・音源）が
   画面幅の12〜15%を占めるので、そこには何も置かない。
   2026-08-07、箇条書きが右端94%まで達して「比べ／る」と1文字落ちた。 */
body { padding: 56px 96px 300px 52px; }
body::before { width: 8px; }
.headline { font-size: 40px; margin-bottom: 28px; }
.note { font-size: 28px; margin-top: 20px; }
.note.lead { margin-top: 0; font-size: 58px; line-height: 1.35; }
li { font-size: 34px; gap: 16px; }
li .marker { min-width: 44px; height: 44px; font-size: 24px; border-radius: 10px; }
ol, ul { gap: 16px; }
/* 表のセルは縦向きで狭い（実効幅392px を2〜3列で割る）。
   2026-08-08、「160万／円」「10万／円」と**単位1文字が次行に落ちた。**
   文字を詰め、折り返しそのものを止める。溢れるより1行に収めるほうがまし。 */
table { font-size: 22px; }
th { font-size: 19px; }
th, td { padding: 10px 8px; white-space: nowrap; }
td:first-child, th:first-child { white-space: normal; }
.bar-label { flex: 0 0 168px; font-size: 22px; line-height: 1.15; }
.bar-track { height: 44px; }
.bar-value { font-size: 24px; }
.chart { gap: 16px; }
.bar-fill.broken::before { width: 12px; }
.chart-base { margin-top: 14px; font-size: 21px; }
/* 縦向きは実効幅 392px しかない。式は折り返すと読めなくなるので、
   横向きより一段落として1行に収める。 */
.formula { margin-top: 16px; padding-left: 12px; border-left-width: 4px; font-size: 21px; }
"""
CONTENT_WIDTH_PORTRAIT = VIEWPORT_PORTRAIT[0] - 52 - 96
# ショートの右端に重なる UI（いいね・コメント・共有・音源）を避ける余白（CSS px）。
# **40px では足りなかった**（2026-08-07、ラベルが画面幅の94%まで届いてボタン列に
# 被った）。実機のボタン列は幅の12〜15%を占めるので、540px 幅に対して 80px 取る。
# body の padding-right で 96px 確保したので、ここは仕上げの余白だけ。
SAFE_RIGHT_PORTRAIT = 24
STAT_MAX_PX_PORTRAIT = 96


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _stat_font_px(text: str, portrait: bool = False) -> int:
    """stat が1行に収まる font-size を返す。

    台本の書き手は「およそ1万7千円」のような短い数字を想定しているが、
    「15万円と15万円で30万円」のように長くなることがある。固定サイズだと
    そこで2行に折り返し、下の note が字幕の帯に押し出されて重なる。
    折り返させないために、文字数から先に縮めておく。

    半角は全角のおよそ 0.55 倍の幅として数える。
    """
    width = CONTENT_WIDTH_PORTRAIT if portrait else CONTENT_WIDTH
    cap = STAT_MAX_PX_PORTRAIT if portrait else STAT_MAX_PX
    floor = 34 if portrait else 56
    if not text:
        return cap
    width_em = sum(0.55 if ord(c) < 0x2E80 else 1.0 for c in text)
    return max(floor, min(cap, int(width / max(width_em, 0.5))))


def _css(theme: dict, portrait: bool = False) -> str:
    """配色を差し込んだ CSS。CSS 側に波括弧があるので format は使えない。"""
    css = BASE_CSS + (PORTRAIT_CSS if portrait else "")
    return (
        css.replace("{ACCENT}", theme["accent"])
        .replace("{BG}", theme["bg"])
        .replace("{GLOW}", theme["glow"])
    )


def _em_width(text: str) -> float:
    """文字列の幅を em で見積もる。半角は全角のおよそ 0.55 倍。"""
    return sum(0.55 if ord(c) < 0x2E80 else 1.0 for c in text)


# 箇条書き1行あたりの文字数。実効幅 ÷ 文字サイズ から出す。
# 縦向き: (392 - marker 44 - gap 16) / 34px ≒ 9.8 → 余裕を見て 9
LIST_CHARS_PORTRAIT = 9
LIST_CHARS = 22

# 見出し1行あたりの文字数。実効幅 ÷ font-size。
# 縦向き: 392 / 40px ≒ 9.8 → 余裕を見て 9。横向き: 1124 / 46px ≒ 24
HEAD_CHARS_PORTRAIT = 9
HEAD_CHARS = 24

# 補足（.note）1行あたりの文字数。縦向き 392/28px ≒ 14、横向き 1124/34px ≒ 33。
#
# **2026-08-08、`.note` を数え落としていた。** 前日に「文字を置く場所は
# stat・table・steps・chart の4つ」と数え、翌日に見出しを足して5つにしたが、
# **まだ足りなかった。** 実測（ブラウザに行数を数えさせた）で
# 「課税所得150万円・控除／率0.7％」「労働基準法37条5項・施／行規則21条」と
# 語中で折れていた。**数えて確かめるのをやめて、機械に数えさせる形にした**
# （下の `_LINE_PROBE_JS` と `render()`）。
NOTE_CHARS_PORTRAIT = 14
NOTE_CHARS = 33
# 数字を伏せた1枚目だけ、補足が主役になって大きくなる（`.note.lead`）。
# 縦 392/66px ≒ 6、横 1124/58px ≒ 19。
NOTE_LEAD_CHARS_PORTRAIT = 6
NOTE_LEAD_CHARS = 19

# 棒ラベル。CSS の flex 幅 ÷ font-size（縦 168/22 ≒ 7.6、横 240/30 = 8）。
LABEL_CHARS_PORTRAIT = 7
LABEL_CHARS = 8


def _wrap_item(text: str, portrait: bool, tighten: int = 0) -> str:
    """箇条書きの1項目を、**語の途中で折らずに**改行する。

    2026-08-08、「復興特別所／得税2.1%」「10万円と総／所得5%」と
    **語の途中で折れた。** 日本語には空白が無いので、ブラウザは任意の位置で折る。
    項目を短くしても限界がある（実効332px・34pxで1行9.8文字、
    実際の項目は最長20文字なので必ず2行になる）。

    **折り返すこと自体は避けられない。避けたいのは折る位置。**
    字幕で作った規則（送り仮名・数字・元号・か月を割らない）をそのまま使い、
    `<br>` で明示的に改行する。**同じ問題は同じ道具で解く。**
    """
    return _wrap(text, LIST_CHARS_PORTRAIT if portrait else LIST_CHARS, tighten)


def _wrap_head(text: str, portrait: bool, tighten: int = 0) -> str:
    """見出しを、語の途中で折らずに改行する。

    **箇条書きと同じ問題が見出しにもあった**（2026-08-08）。
    「繰下げると年額はこうなる」は12文字で、9.8文字の枠に入らない。

    この関数は一度**書いただけで呼ばれていなかった。**（同日、実測で発覚。
    「直した」と JOURNAL に書いた時点で、画面はまだ何も変わっていなかった。）
    **書いたら呼び出し側を必ず確かめること。** 片方だけ直す形は4回目。
    """
    return _wrap(text, HEAD_CHARS_PORTRAIT if portrait else HEAD_CHARS, tighten)


def _wrap_note(text: str, portrait: bool, tighten: int = 0, lead: bool = False) -> str:
    """stat の下の補足を、語の途中で折らずに改行する。

    `lead=True` は**数字を伏せた1枚目**（`reveal_variants` の stat）。
    そこだけ文字が大きい（縦 48px・横 40px）ので、**1行に入る字数も減ります。**
    実効幅 ÷ font-size で 392/48 ≒ 8、1124/40 ≒ 28。
    **ここを分けないと、`render()` が溢れを見つけて何段も詰めることになります。**
    """
    if lead:
        limit = NOTE_LEAD_CHARS_PORTRAIT if portrait else NOTE_LEAD_CHARS
    else:
        limit = NOTE_CHARS_PORTRAIT if portrait else NOTE_CHARS
    return _wrap(text, limit, tighten)


def _wrap_label(text: str, portrait: bool, tighten: int = 0) -> str:
    """棒グラフのラベルを、語の途中で折らずに改行する。"""
    return _wrap(text, LABEL_CHARS_PORTRAIT if portrait else LABEL_CHARS, tighten)


def _wrap(text: str, limit: int, tighten: int = 0) -> str:
    """字幕の改行規則で折り、`<br>` を入れる。**画面側に折らせない。**

    `tighten` は「見積もった文字数では収まらなかった」ときに `render()` が
    段階的に上げる。文字幅の見積もりは font によってずれるので、
    **見積もりを当てにせず、実測で足りなければ狭める。**
    """
    from .subtitles import _chunk

    limit = max(limit - tighten, 4)
    text = text.strip()
    if len(text) <= limit:
        return _esc(text)
    # 行頭・行末の空白は捨てる。残すと行頭が1字ぶん下がって折り返しに見える。
    return "<br>".join(_esc(line.strip()) for line in _chunk(text, limit) if line.strip())


# 棒を0起点で描いてよいかの境目。**いちばん短い棒がいちばん長い棒の
# 何割か**で見る。0.65 は実測から置いた（2026-08-15、`s-tedori-2` の3コマ目で
# 率13%→244px・率15%→240px、**長さの差 1.6%**。目視では同じ長さの棒が2本
# 並んでいるだけで、読み上げが言う差が図から読み取れなかった）。
# 0.65 なら短いほうが65%＝目で見て明らかに短い。ここを上げると誤爆が増える。
ZERO_BASE_MIN_RATIO = 0.65
# 起点をずらしたとき、いちばん短い棒に残す長さの目安（軌道に対する割合）。
# 0 に近づけると「消えた棒」に見え、1 に近づけると差がまた潰れる。
SHORT_BAR_TARGET = 0.30


def _nice_floor(x: float, span: float) -> float:
    """`x` 以下でいちばん近い「きりのいい数」。刻みは span の桁で決める。

    起点の数字は**画面に出す**ので、35万283円のような数では読めない。
    span=6318 なら刻み1000 → 35万円、span=3.2 なら刻み1 → 68% になる。
    """
    if span <= 0:
        return 0.0
    step = 10.0 ** math.floor(math.log10(span))
    # 刻みが細かすぎると起点がほぼ x のままになり、短い棒が消える。
    # 逆に粗すぎると起点が0まで落ちる。span の 1/10〜1/2 に収める。
    while step * 5 < span:
        step *= 2 if step * 2 * 5 >= span else 10
    return math.floor(x / step) * step


def chart_base(values: list[float]) -> float:
    """棒の目盛りの起点。0 なら従来どおり0起点で描く（2026-08-15）。

    **0起点は「正しい」が、常に「読める」わけではありません。**
    35万9318円と35万3000円を0から描けば、棒の長さの差は1.6%になり、
    **読み上げが言っている差が図に出ません。** 図が言っていないことを
    声だけが言っている状態で、これは図が無いのと変わらない。

    かといって黙って起点をずらすと、**縮めた棒が0起点に見えて誤解を招きます**
    （収益化ポリシーの「誤解を与える内容」の側）。だから、ずらしたときは
    必ず (1) 棒の頭に斜線の帯を出し、(2) 起点の数字を画面に書く。
    **印と数字を出さないなら、ずらしてはいけません。**
    """
    vals = [v for v in values if v is not None]
    if len(vals) < 2 or min(vals) <= 0:
        return 0.0
    lo, hi = min(vals), max(vals)
    if lo / hi < ZERO_BASE_MIN_RATIO:      # 目で見て差が分かる。触らない
        return 0.0
    span = hi - lo
    if span <= 0:                          # 全部同じ値。ずらしても差は出ない
        return 0.0
    # いちばん短い棒が軌道の SHORT_BAR_TARGET になる起点
    raw = lo - span * SHORT_BAR_TARGET / (1.0 - SHORT_BAR_TARGET)
    base = _nice_floor(raw, span)
    if base <= 0 or base >= lo:            # 0まで落ちた／短い棒が消える
        return 0.0
    return float(base)


def _axis_unit(display: str) -> str:
    """表示文字列の末尾から単位を取る。`35万9318円` → `円`、`73.5%` → `%`。"""
    i = len(display)
    while i > 0 and not display[i - 1].isdigit():
        i -= 1
    unit = display[i:].strip()
    return unit if len(unit) <= 3 else ""


def _first_unit(display: str) -> str:
    """display の**最初の数のうしろ**にある単位を返す。

    `35万9318円` → `円`、`82歳10か月` → `歳`、`73.5%` → `%`。

    **空白で切って先頭を見る形にしないこと**（2026-08-16 18:5x に実物で踏んだ）。
    2026-08-16 16:0x の直しは `display.split()[0]` でした。あれが効くのは
    **数と数のあいだに空白がある**ときだけです。ところが 年金 の族は
    **`82歳10か月` と、空白なしで数を2つ並べます** ——
    `split()` が1個しか返さないので、そのまま末尾から拾って `か月` になり、
    実物 `AoBABYXSUas`（8/31 13:00 予約）の画面に

        棒: `82歳10か月` / `86歳3か月`（value は年の小数 82.83・86.25）
        → **「※ 棒の起点は0ではなく 81か月」**

    が出ていました。**棒は83歳あたりなのに、起点が6年9か月だと言っています。**
    16:0x が直したのと同じ嘘で、**塞いだのは空白のある形だけ**でした。

    だから左から数を食べます。`万億千兆` は**うしろに数が続くときだけ**数の一部
    （`6万2927円` は数、`12万円` の `万` は単位側 ＝ 下の `lstrip` が落とす）。
    """
    s = display.strip()
    i = 0
    while i < len(s) and not s[i].isdigit():
        i += 1
    if i >= len(s):
        return ""
    j = i
    while j < len(s):
        c = s[j]
        if c.isdigit() or c in ",.":
            j += 1
        elif c in "万億千兆" and j + 1 < len(s) and s[j + 1].isdigit():
            j += 1
        else:
            break
    k = j
    # **空白で止めること。** 止めないと `6万2927円 実効22.8%` の単位が
    # `円 実効`（4字）になり、長すぎるとして**丸ごと捨てられます** ——
    # 起点が単位なしの `50,000` になり、16:0x が直した本命が黙って戻ります。
    while k < len(s) and not s[k].isdigit() and not s[k].isspace():
        k += 1
    unit = s[j:k].strip()
    return unit if len(unit) <= 3 else ""


def _fmt_axis(base: float, display: str) -> str:
    """起点の数字を、棒に出ている表示と同じ単位で書く。

    **単位は display の「最初の数」から取ります**（2026-08-16 に直した）。
    `_axis_unit` は末尾から単位を拾うので、display に数が2つ入っていると
    **後ろのほうの単位**を返します。実物（`vS6PGatxPQw` ／ iDeCo）:

        display = "6万2927円 実効22.8%"   value = 62927.0   base = 50000
        → 単位が "%" になり、画面に **「※ 棒の起点は0ではなく 50,000%」**

    **棒の長さを決めているのは `value`＝円のほう**なので、これは嘘です。
    独立評価の3体のうち2体が、別々にこの1行を指しました
    （「単位が壊れていて、グラフの読み方そのものを疑う」）。
    **機械検査は素通りしています** —— 誰も「起点の単位」を見ていませんでした。

    取り方は `_first_unit`（**空白に頼りません**。同日 18:5x に実物で直した）。
    """
    unit = _first_unit(display)
    # **桁の字は単位ではありません**（同日、上を直す途中で実物が出た）。
    # `"12万円"` は末尾から `"万円"` を単位として拾うので、下の万への
    # 書き換えがもう一度 `万` を足し、**「12万万円」**になっていました。
    # これは前からある欠陥で、`display` が万どまりの丸い額のときだけ出ます。
    unit = unit.lstrip("万億千")
    n = round(base, 2)
    if unit.endswith("円") and n >= 10000 and abs(n / 10000 - round(n / 10000)) < 1e-9:
        return f"{round(n / 10000):,.0f}万{unit}"
    if abs(n - round(n)) < 1e-9:
        return f"{round(n):,.0f}{unit}"
    return f"{n:,.1f}{unit}"


def _chart_html(visual: dict, portrait: bool = False, tighten: int = 0) -> str:
    """計算結果を棒グラフにする。

    bars は [{"label": ..., "value": 数値, "display": "12万6千円"}] の形。
    value は棒の長さを決めるためだけに使い、画面に出す文字は display。
    最大値を 100% として引き伸ばすので、**どこにも同じ形の図が出ない**。

    数字を棒の中に入れるか外に出すかは、**実際の幅で決める**。
    以前は「32%未満なら外」と割合で決めていたが、入るかどうかは
    文字数と画面の幅で決まるので、割合では判定できない。
    実際に縦向きで、43.8%の棒に「7万7949円」が入りきらず
    「万7949円」と頭が欠けた。**数字が主役のチャンネルで数字が欠けるのは致命的。**
    """
    bars = [b for b in (visual.get("bars") or [])[:6] if b.get("label")]
    if not bars:
        return ""

    # CSS と揃える。ここがずれると判定もずれるので、変えるときは両方直すこと。
    if portrait:
        content, label_px, font_px, gap = CONTENT_WIDTH_PORTRAIT, 168, 24, 16
    else:
        content, label_px, font_px, gap = CONTENT_WIDTH, 240, 30, 22
    # **ショートは右端に UI（いいね・コメント・共有）が縦に重なる。**
    # 2026-08-05、外に出した棒ラベルが右端 20px まで達していた。切れては
    # いなかったが、実機では UI の下に入って読めない。**枠に収まるだけでは足りない。**
    track_px = max(content - label_px - gap - (SAFE_RIGHT_PORTRAIT if portrait else 0), 1)

    # **`scale_max` があればそれを目盛りにする**（2026-08-15）。
    # 棒を1本ずつ出していく「めくり」を作るとき、`bars` を先頭から切ると
    # ここの `max` が変わり、**同じ棒の長さが枚ごとに伸び縮みします。**
    # 図が嘘になるので、めくりの側から全体の最大値を渡して固定する。
    top = float(visual.get("scale_max") or 0) or \
        max(float(b.get("value", 0)) for b in bars) or 1.0

    # **起点も同じ理由で外から渡せる**（2026-08-15）。めくりの1枚目は棒が1本
    # しか無いので、そこから起点を決めると枚ごとに目盛りが変わります。
    # `scale_base` が来ていればそれを使い、無ければ見えている棒から決める。
    raw_base = visual.get("scale_base")
    base = float(raw_base) if raw_base is not None else \
        chart_base([float(b.get("value", 0)) for b in bars])
    if base >= top:            # 目盛りが壊れる。0起点に戻す
        base = 0.0
    span = top - base or 1.0

    # **縮尺（下の `scale`）も、めくりで枚ごとに動いていました**（2026-08-15、
    # `tests/test_chart_base.py` が見つけた）。`scale_max` と `scale_base` を
    # 固定しても、**収まるかどうかの判定は「見えている棒」だけで走っていた**ので、
    # 1枚目（棒1本）は 100%、2枚目（棒2本）は 86% と、**同じ棒が縮みました。**
    # `scale_max` を入れた回に見落としたのはここです。**目盛りは3つある**
    # （最大値・起点・縮尺）。1つでも見えている棒から決めると図が動きます。
    #
    # だから縮尺と文字の大きさは、**常に全体の棒**（`scale_bars`）から決める。
    ref = [b for b in (visual.get("scale_bars") or bars) if b.get("label")][:6]

    def pct_of(bs: list[dict]) -> list[float]:
        return [max((float(b.get("value", 0)) - base) / span * 100.0, 1.0) for b in bs]

    pcts, ref_pcts = pct_of(bars), pct_of(ref)
    # padding-right 16px と余白を見た、数字1つに要る幅。
    needs = [_em_width(str(b.get("display", ""))) * font_px + 16 * 2 for b in bars]

    # **中に入らないとき外に出すが、外に出しても入らない場合を見ていなかった。**
    # 2026-08-05、税率べつの図で「約10万9千円」が右端で切れた。棒が57%あり、
    # 中には入らず（棒157px < 必要168px）、外に出すと 157+168=325px で
    # 枠の276pxを超える。**どちらでも入らない棒があり得る。**
    #
    # 棒の長さは計算結果そのものなので、1本だけ縮めると図が嘘になる。
    # **全部に同じ倍率をかけて縮める。** 相対の長さは保たれるので、図は正しいまま。
    # 満幅を使わなくなるだけ。
    def fits(k: float, ns: list[float]) -> bool:
        # **見えている棒ではなく `ref`（全体）で判定する。** めくりの途中でも
        # 最後の1枚と同じ縮尺が出るようにするため。
        for pct, need in zip(ref_pcts, ns):
            bar = track_px * pct * k / 100.0
            if bar < need and bar + need > track_px:   # 中にも外にも入らない
                return False
        return True

    # **縮尺だけでは収まらないことがある。**
    # 2026-08-05、縮尺が下限 0.30 に張り付いたまま `fits` が偽で、79px の棒に
    # 229px のラベルを外置きしていた（合計308px > 枠264px）。
    # **収まらないのに、収まらないまま出していた。** 下限に当たったら諦める、
    # という書き方がそうさせた。
    #
    # 縮尺と文字の大きさを**一緒に**探す。図が極端に小さくなるほうが読めないので、
    # 縮尺の下限は 0.5 に上げ、代わりに文字を段階的に落とす。
    scale, size = 1.0, font_px
    for fpx in (font_px, font_px - 3, font_px - 5, font_px - 7):
        # 判定に使う幅は `ref`（全体）ぶん、描くのに使う幅は見えている棒ぶん。
        ns = [_em_width(str(b.get("display", ""))) * fpx + 16 * 2 for b in ref]
        k = 1.0
        while k > 0.5 and not fits(k, ns):
            k -= 0.01
        if fits(k, ns):
            scale, size = k, fpx
            needs = [_em_width(str(b.get("display", ""))) * fpx + 16 * 2 for b in bars]
            break
    else:
        # どの大きさでも収まらない。**黙って出さない。** 一番小さい字で最善を尽くす。
        scale, size = 0.5, font_px - 7
        needs = [_em_width(str(b.get("display", ""))) * size + 16 * 2 for b in bars]

    rows = []
    fresh = fresh_flags(visual, len(bars))
    for i, (b, pct0, need_px) in enumerate(zip(bars, pcts, needs)):
        pct = pct0 * scale
        cls = " thin" if track_px * pct / 100.0 < need_px else ""
        if base > 0:
            cls += " broken"
        rows.append(
            f'<div class="bar-row{" fresh" if fresh[i] else ""}">'
            f'<div class="bar-label">{_wrap_label(b["label"], portrait, tighten)}</div>'
            f'<div class="bar-track">'
            f'<div class="bar-fill{cls}" style="width:{pct:.1f}%">'
            f'<span class="bar-value" style="font-size:{size}px">'
            f'{_esc(b.get("display", ""))}</span>'
            f"</div></div></div>"
        )
    chart = f'<div class="chart">{"".join(rows)}</div>'
    if base > 0:
        # **黙ってずらさない。** 起点を画面に書かないと、縮めた棒が0起点に見える。
        label = _fmt_axis(base, str(bars[0].get("display", "")))
        chart += f'<div class="chart-base">※ 棒の起点は0ではなく {_esc(label)}</div>'
    return chart


# **このコマで増えた要素に付ける印**（`fresh_flags`）。f-string の中に
# バックスラッシュを書けない（3.11）ので、開きタグは定数で持つ。
FRESH_TR = '<tr class="fresh">'
FRESH_LI = '<li class="fresh">'


def fresh_flags(visual: dict, shown: int) -> list[bool]:
    """`shown` 個のうち、**このコマで増えたぶん**を後ろから数えて True にする。

    **なぜ要るか**（2026-08-16。**独立評価9体ぶんの実測から**）。

    `reveal_variants` は表・棒・箇条書きを1つずつ足していく複数コマに割ります。
    増えた要素は**見出し**に出していました（`_reveal_headline` の「＋600万」）。
    **それでは足りませんでした。** 同日に回した3本 × 3体 ＝ **9体が全員**、
    別々の本について同じ言い方をしています:

        「同じ表に600万の行が1行足されるだけ。表以外は完全に同じ画面」
        「同じ表に3行足しただけで、これも実質同じ画面」
        「差分を積み上げる作りなので、画面は『切り替わる』より『増える』で、
          スクロール中の目には止まって見えます」

    `YhHeqMKql7U` は3体そろって **4/4/3点**（記録した中で最低）。13コマのうち
    **6組が「前のコマ＋1行」**でした。engaged 比率は配信の駆動輪なので、
    ここが止まって見えることは目標に直接効きます。

    **直し方の向き。** 割るのをやめる道は採りません —— 割る前は
    「1枚が5.8秒止まる」で、**そちらのほうが悪いと実測済み**です
    （`reveal_variants` の stat の節）。だから
    **割ったまま、増えた要素そのものを目立たせます。**
    印は最後の要素**だけ**に付き、次のコマでは前の印が消えて次へ移るので、
    画面の中で**位置の変わる強調が1つ動く**ことになります。

    **`kind=stat`（冒頭）には掛かりません。** あちらは 9/5 判定の実験中で、
    触らないことになっています（`config/hypotheses.yaml`）。
    """
    n = int(visual.get("reveal_new") or 0)
    n = max(0, min(n, shown))
    return [i >= shown - n for i in range(shown)] if n else [False] * shown


def _body_html(visual: dict, portrait: bool = False, tighten: int = 0) -> str:
    kind = (visual.get("kind") or "stat").strip()

    if kind == "chart" and visual.get("bars"):
        return _chart_html(visual, portrait, tighten)

    if kind == "table" and visual.get("headers") and visual.get("rows"):
        head = "".join(f"<th>{_esc(h)}</th>" for h in visual["headers"][:3])
        shown = visual["rows"][:4]
        fresh = fresh_flags(visual, len(shown))
        rows = "".join(
            (FRESH_TR if fresh[i] else "<tr>")
            + "".join(f"<td>{_esc(c)}</td>" for c in row[:3]) + "</tr>"
            for i, row in enumerate(shown)
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"

    if kind in ("steps", "compare") and visual.get("items"):
        cls = "compare" if kind == "compare" else "steps"
        markers = ("A", "B", "C", "D") if kind == "compare" else ("1", "2", "3", "4")
        shown = visual["items"][:4]
        fresh = fresh_flags(visual, len(shown))
        items = "".join(
            (FRESH_LI if fresh[i] else "<li>")
            + f'<span class="marker">{markers[i]}</span>'
            + f'<span>{_wrap_item(text, portrait, tighten)}</span></li>'
            for i, text in enumerate(shown)
        )
        return f'<ul class="{cls}">{items}</ul>'

    # 既定は stat。数字が無ければ見出しだけで成立するので何も出さない。
    stat = visual.get("stat") or ""
    note = visual.get("note") or ""
    parts = []
    if stat:
        size = _stat_font_px(stat, portrait)
        parts.append(f'<div class="stat" style="font-size:{size}px">{_esc(stat)}</div>')
    if note:
        # 数字を伏せた1枚目（`reveal_variants` の stat）は、補足しか出るものが
        # ありません。**そのままの大きさだと画面がすかすかに見える**ので、
        # ここだけ主役として大きく出します。数字が出た2枚目では元の大きさに戻り、
        # **主役が入れ替わったことが、そのまま見た目の変化になります。**
        lead = bool(visual.get("note_lead")) and not stat
        cls = "note lead" if lead else "note"
        parts.append(
            f'<div class="{cls}">{_wrap_note(note, portrait, tighten, lead)}</div>'
        )
    return "".join(parts)


def build_html(visual: dict, theme: dict | None = None, portrait: bool = False,
               tighten: int = 0, zoom: float = 1.0) -> str:
    """`tighten` は横（勝手な折り返し）、`zoom` は縦（枠からの溢れ）を直す。

    **2つは別の向きなので、別のつまみが要る。** `tighten` を上げると行数が
    増えて縦には**悪化する**。2026-08-08、縦向きの steps が 27px 溢れていた。
    """
    head = _wrap_head(visual.get("headline", ""), portrait, tighten)
    extra = "" if zoom >= 0.999 else f".body {{ zoom: {zoom:.2f}; }}"
    # 式は `.body`（flex:1 で中央寄せ）の**外**に置く。中に入れると、
    # 中央寄せの一部として本文と一緒に上下に動き、コマごとに位置が変わる。
    # 根拠は毎コマ同じ場所にあるほうが読める。
    formula = str(visual.get("formula") or "").strip()
    formula_html = f'<div class="formula">{_esc(formula)}</div>' if formula else ""
    return (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        f"<style>{_css(theme or THEMES[0], portrait)}{extra}</style></head><body>"
        f'<div class="headline">{head}</div>'
        f'<div class="body">{_body_html(visual, portrait, tighten)}</div>'
        f"{formula_html}"
        "</body></html>"
    )


def _chromium_path() -> str | None:
    """使える Chromium の実体を探す。

    この環境には Chromium が同梱されているが、ビルド番号が playwright の
    期待するものと一致しないことがあり、そのままだと launch が落ちる。
    環境変数で指し直せるようにしてあるが、**それに頼らない。**
    毎日無人で回るので、シェルをまたいで変数が消えた時点で止まる作りは避ける。
    見つからなければ None を返し、playwright の既定に任せる。
    """
    import os

    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", "").strip()
    if explicit and Path(explicit).exists():
        return explicit

    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    if not root.is_dir():
        return None
    for name in ("chrome", "headless_shell", "chrome-headless-shell"):
        for found in sorted(root.glob(f"*/chrome-linux*/{name}")):
            if found.is_file():
                return str(found)
    return None


_LINE_PROBE_JS = """() => {
  let bad = 0;
  for (const s of ['.headline', '.note', '.bar-label', '.chart-base', '.formula',
                   'li > span:not(.marker)']) {
    for (const el of document.querySelectorAll(s)) {
      const r = document.createRange();
      r.selectNodeContents(el);
      // **矩形の数は行数ではない。** `<br>` ごとに高さ0の矩形が1つ余分に付く
      // （2026-08-08 実測: 2行に対し3矩形、3行に対し5矩形）。
      // 数えるのは矩形ではなく、**矩形の上端が何種類あるか**。
      const rows = new Set([...r.getClientRects()].map(x => Math.round(x.top))).size;
      // こちらが `<br>` で指示した行数より多く折れていたら、
      // ブラウザが**勝手な位置で割っている**（＝語の途中で割れうる）。
      if (rows > el.innerHTML.split('<br>').length) bad++;
      if (el.scrollWidth > el.clientWidth + 1) bad++;
    }
  }
  const b = document.body;
  // 縦に溢れると、下端の行が**そのまま切れる**（スクロールバーは出ない）。
  if (b.scrollHeight > b.clientHeight + 1) bad++;
  if (b.scrollWidth > b.clientWidth + 1) bad++;
  return bad;
}"""

# 見積もりが外れたときに文字数の上限を何段階まで詰めるか。
MAX_TIGHTEN = 6
# 縦に溢れたときの縮小。0.75 より下げると、ショートの実機で読めなくなる。
ZOOMS = (1.0, 0.94, 0.88, 0.82, 0.76)


#: めくりの見出しに足す「いま増えた分」の上限。**どちらも「切る」ためではなく、
#: 「入らなければ足さない」ためのしきい値です**（下の `_reveal_headline`）。
REVEAL_LABEL_MAX = 10
REVEAL_HEAD_MAX = 20
#: 要素の名前が入らないときに足す「2/3」の側の上限。**こちらは4文字しか足さない**ので、
#: 名前を足すときより長い見出しまで許せる（`_wrap_head` が2行に折る範囲）。
REVEAL_STEP_MAX = 24


def _reveal_label(key: str, item) -> str:
    """めくりで新しく出た要素を、見出しに足せる短い語にする。

    **長すぎるものは切らずに捨てる。** 2026-08-15、ここを `text[:8]` で
    切ったら、実物の画面に **「＋自己都合などの離」**（「離職」の途中）が出た。
    `src/script_writer.py` の `Bar.label` が
    「『同居特別障害者控除』を『同居特別障害』と切って画面に日本語として
    成立しない文字列が出た」と書いているのと**同じ間違いを、別の場所で
    もう一度やった**ことになる。日本語は語の切れ目が字面に出ないので、
    **機械が安全に切れる位置は無い。**
    """
    if key == "bars":
        text = str((item or {}).get("label", ""))
    elif key == "rows":
        text = str(item[0]) if isinstance(item, list) and item else str(item)
    else:
        text = str(item)
    text = " ".join(text.split())
    return text if len(text) <= REVEAL_LABEL_MAX else ""


def _formula_is_answerable(visual: dict) -> bool:
    """**その式の答えが、いまのコマに出ているか。**

    2026-08-16、`s-souzoku-kosuu-1nin-sa-345` の実画面に、こう並びました:

        A 子1人 基礎控除 4200万円          ← 見えている唯一の行
        4800万円 ＝ 3000万円 ＋ 600万円 × 3人   ← 式

    **台本は正しい**（`items` は「子1人…4200万円」「子2人…4800万円」の2行で、
    式はその2行目のこと）。**壊したのは、めくりで割ったこちらです。**
    下のループが `dict(visual)` で式ごと全コマに配り、
    **答えの行が出る前のコマにも同じ式を置いていました。**

    画面だけを見ると **4200 と 4800 が矛盾して見えます。** 動画の根幹は
    「視聴者が自分で追試できること」なので、**追試すると合わない画面**は
    ただの欠陥ではなく、根幹そのものを崩します。

    `kind=stat` の側は 2026-08-15 に `first["formula"] = ""` で塞いであり、
    **こちらのループにだけ無い**という、片側だけ直した形でした（通算6回目）。

    見るのは1つだけ —— **式の左辺の数が、そのコマのどこかに出ているか。**
    出ていなければ、そのコマでは式を消します（末尾のコマは必ず全部入りなので、
    `_check_formula_shown` の「1本に最低1枚」は保たれます）。
    """
    formula = str(visual.get("formula") or "").strip()
    if not formula:
        return True
    lhs = re.split(r"[=＝]", formula)[0]
    digits = re.findall(r"\d[\d,]*", lhs)
    if not digits:
        return True                      # 数の無い左辺は判定しない（通す）
    parts: list[str] = [str(visual.get(k) or "") for k in
                        ("headline", "stat", "note", "stat_source")]
    for item in visual.get("items") or []:
        parts.append(str(item))
    for row in visual.get("rows") or []:
        parts.extend(str(c) for c in (row if isinstance(row, list) else [row]))
    for bar in visual.get("bars") or []:
        if isinstance(bar, dict):
            parts.extend(str(bar.get(k, "")) for k in ("label", "value", "value_text"))
        else:
            parts.append(str(bar))
    shown = re.sub(r"[,\s]", "", " ".join(parts))
    return all(re.sub(r"[,\s]", "", d) in shown for d in digits)


def _reveal_headline(head: str, label: str, step: int = 0, total: int = 0) -> str:
    """めくりの各コマに「いま何が増えたか」を出す見出しを作る。

    **なぜ要るか**（2026-08-15）。`reveal_variants` は1枚を複数コマに割って
    画面を動かすが、**見出しは全コマで同じ文字列のまま**だった。
    独立評価の3体が「隣り合う2枚が、見出しも同じで棒が1本増えるだけ」と書き、
    8/15 16:0x の回では6体が同じことを書いている。**通算9体・2回の持ち越し。**

    絵が動いていても、**上に出ている文字が同じなら視聴者から見て画面は変わらない。**
    だから増えた要素の名前を見出しに出す。読み上げはこのコマの間ずっと同じ文なので、
    **字幕とはずれない**（割っているのは絵だけ。`reveal_variants` の説明のとおり）。

    **どちらの側も切らない。** 元の見出しを削るのも同じ間違いになる
    （「10年の境界でふえる日数」→「10年の境界でふえる」）。

    ## **「入らなければ足さない」は、直したはずの欠陥をそのまま出していました**
    （2026-08-15 20:5x。**通算3回目の持ち越し**。実物 `OePniwSIcTE`）

    上の「足さずに元のまま出す」を実画面で確かめたら、**その逃げ道のほうが
    既定になっていました。** 8コマ中4コマがそれです。

        2コマめ「60歳以上65歳未満 倒産解雇」 ＋「1年以上」→ 21字 > 20 → **足さない**
        3コマめ  同じ見出し                                     ← **画面が変わらない**
        6コマめ「この計算の前提」 ＋「日額は令和8年8月1日改定の上下限」
                                    → 労働は 10字超 → label が空 → **足さない**
        7コマめ 同じ見出し                                       ← **同じことが2回**

    **つまり、見出しが長い本と、要素の名前が長い本では、この直しは一度も効きません。**
    そして長い見出し・長い項目は珍しくないので、**効かない側が多数派**でした。

    **直し方は「切る」ではありません**（切ると 8/15 に2回やった壊れた日本語に戻る）。
    **足す語を短い側に替えます。** 増えた要素の名前が入らないときは、
    **いま何コマ目かを出す**（`2/3`）。4文字で、日本語を壊さず、必ず入り、
    **視聴者には「まだ続きがある」ことが伝わります**（名前ほどの情報は無いが、
    **同じ見出しが2枚続くよりは確実に良い**）。

    **どちらも入らないほど見出しが長いなら、それは見出しのほうが長すぎます。**
    その場合だけ元のまま返します（`_wrap_head` が折り、`render` が縮めるので
    実害は「marker が出ない」ことだけ）。
    """
    head = " ".join(str(head or "").split())
    if not head:
        return label
    tail = f"　＋{label}" if label else ""
    if tail and len(head) + len(tail) <= REVEAL_HEAD_MAX:
        return head + tail
    if step and total:
        mark = f"　{step}/{total}"
        if len(head) + len(mark) <= REVEAL_STEP_MAX:
            return head + mark
    return head


def reveal_variants(visual: dict, want: int) -> list[dict]:
    """図解1枚を、要素を1つずつ足していく複数枚に割る（2026-08-15）。

    **なぜ要るか。** 独立評価（M13）は3体そろって
    「同じ絵が2コマ続く」「9コマ中の実質4〜5画面」と書いてきました。
    絵と読み上げの文が**1対1で結ばれていた**ので、1つの文が5〜6秒あると
    その間ずっと画面が止まります。

    **文を短くする道は 2026-08-09 に既に潰れています**（140文字を8枚に割ると
    1枚17文字で文にならない。`src/script_writer.py` の定数のコメント）。
    **だから割るのは文ではなく絵のほうです。**

    字幕は文の側（`segment_timeline`）に付くので、**ここで絵を増やしても
    字幕はずれません。** そこがこの直し方の効くところです。

    `want` は欲しい枚数。要素がそれより少なければ、あるだけしか返しません
    （**水増ししない**。同じ絵を2回出したら、直したことになりません）。
    """
    if want <= 1:
        return [visual]
    for key in ("bars", "rows", "items"):
        seq = visual.get(key)
        if not isinstance(seq, list) or len(seq) < 2:
            continue
        n = len(seq)
        k = min(want, n)
        out = []
        prev_cut = 0
        for i in range(k):
            cut = max(1, round(n * (i + 1) / k))
            v = dict(visual)
            v[key] = seq[:cut]
            # **1コマ目以外は、いま増えた要素を見出しに出す。**
            # 見出しが全コマ同じだと、絵が動いていても画面は変わって見えない
            # （`_reveal_headline` の説明）。
            if i and cut > prev_cut:
                v["headline"] = _reveal_headline(
                    visual.get("headline", ""), _reveal_label(key, seq[cut - 1]),
                    step=i + 1, total=k,
                )
            # **いま増えた要素そのものに、印を付ける**（2026-08-16）。
            # 見出しだけを変えても、独立評価の9体は「同じ表に1行足されるだけ」
            # 「実質同じ画面」と書き続けました（下の `reveal_new` の説明）。
            v["reveal_new"] = (cut - prev_cut) if i else 0
            prev_cut = cut
            if key == "bars":
                # 目盛りを全体の最大値で固定する。切っても棒が伸び縮みしない。
                values = [float(b.get("value", 0) or 0) for b in seq]
                v["scale_max"] = max(values) if values else 0
                # **起点も同じ。** 1枚目は棒が1本しか無いので、そこから
                # 決めさせると枚ごとに目盛りが動く（＝図が嘘になる）。
                v["scale_base"] = chart_base(values)
                # **縮尺も同じ。** 収まるかどうかの判定を見えている棒だけで
                # 走らせると、1枚目 100% → 2枚目 86% と同じ棒が縮みます。
                v["scale_bars"] = seq
            # **答えの行がまだ出ていないコマからは、式を外す**（2026-08-16）。
            # `kind=stat` の側にしか無かった守りを、こちらにも入れます。
            if not _formula_is_answerable(v):
                v["formula"] = ""
            out.append(v)
        # 末尾は必ず「全部出ている」状態にする。
        # **見出しだけは戻さない。** 戻すと最後の2コマで同じ文字列が並び、
        # ここで直したはずのものがそこだけ再発します（k=2 のときは全部）。
        last_head = out[-1].get("headline", visual.get("headline", ""))
        last_new = out[-1].get("reveal_new", 0)
        out[-1] = dict(visual)
        out[-1]["headline"] = last_head
        # **印も戻さない。** ここで落とすと、最後の1コマだけ「何が増えたか」が
        # 消えます（`k=2` のときは、割った2枚のうち片方が素のまま）。
        out[-1]["reveal_new"] = last_new
        if key == "bars":
            values = [float(b.get("value", 0) or 0) for b in seq]
            out[-1]["scale_max"] = max(values) if values else 0
            out[-1]["scale_base"] = chart_base(values)
            out[-1]["scale_bars"] = seq
        return out

    # ここから下は `kind=stat`（数字1つと補足1行）。**割る列が無い唯一の種類です。**
    #
    # 2026-08-15 に上のループを足したとき、stat だけ `[visual]` のまま
    # **1枚に落ちていました。** そして stat が来るのは**たいてい冒頭**です
    # （`_check_short_opening` が1枚目を stat に縛っている）。
    # 実測: 8/15 に作った `s-tedori-2` は6文→12枚に割れたが、
    # **stat の2文だけは1枚ずつで、1枚あたり 5.8秒 止まっていました。**
    # `src/script_writer.py` の言うとおり **離脱は 4.7〜5.7秒** に来ます。
    # **いちばん動かしたい区間だけが、唯一動いていませんでした。**
    #
    # 独立評価の3体が独立に「冒頭2コマが同一」と書いたのはこれです。
    # `_check_short_pace` は `尺 ÷ 文の数` で見ているので（30秒 ÷ 6文 = 5秒 < 上限12秒）、
    # **平均に埋もれて1枚も引っかかりません。**
    #
    # 割り方は「数字を先に出し、補足をあとから足す」。数字は動かさないので、
    # **読み上げと画面がずれません**（補足は読み上げの後半に当たる）。
    # 補足が無ければ割れないので、そのまま1枚を返します（**水増ししない**）。
    #
    # **この割り方も、見出しを2コマとも同じにしていました**（2026-08-15 20:5x）。
    # 上のループには `_reveal_headline` が入っているのに、ここだけ素通りで、
    # **しかも stat が来るのは冒頭**です（`_check_short_opening` が1枚目を縛る）。
    # つまり**いちばん見られる2コマが、同じ文字を出していた。**
    # 新しく足した `_check_adjacent_frames` が、実際の生成の1本目で
    # 「1コマめと2コマめの見出しが画面上で同一」と落として見つけました。
    # 足すのは名前ではなく `2/2`（補足は文なので、名前として短く出せません）。
    if (visual.get("kind") or "stat").strip() == "stat":
        if visual.get("stat") and visual.get("note"):
            # **向きを逆にしました**（2026-08-15 22:0x。**実測で決めています**）。
            #
            # ここは長く「数字を先に出し、補足をあとから足す」でした。
            # `scripts/bake_slides.py` で実物を測ったら、**その2枚は
            # 画面の 7.06% しか塗り替えていません。** 数字も見出しも式も同じで、
            # 増えるのは 21字 の注記1行だけ。しかも変わって見えた 7% の中身は
            # **`.body` が中央寄せなので、注記が入ったぶん数字が上へずれた**ぶんです。
            # **情報は増えず、位置だけ動いていました。**
            #
            # `0MC_rlov7Ng` の独立評価3体が3体とも
            # 「1コマ目と2コマ目が実質同じ絵（大見出しが据え置きで小さい注記が
            # 足されるだけ）」と書いたのはこれです（**通算4回目の持ち越し**）。
            #
            # **画素のしきい値では捕まりません。** 同じ本で、棒が1本ふえる
            # 本物の段階表示が **6.02%** でした。**偽物 7.06% > 本物 6.02%** で
            # 順序が逆転しているので、`NEAR_DUPE_RATIO` をどこに置いても
            # 「偽物だけ落として本物を通す」線は引けません（`verify.py` の同名の定数）。
            #
            # **だから、いちばん大きい要素そのものを動かします。** 前提を先に出し、
            # **数字を後から出す。** 画面の主役が「無い→ある」に変わるので、
            # これ以上大きい変化はありません。読み上げとも合います ——
            # 実物の1文目は「50万の昇給。手取りは35万9318円だけ。」で、
            # **数字は後半の文に来ます。**
            #
            # ついでに、同じ回の独立評価が3体中2体で言った
            # 「**前提が数字より後ろにあり、金額を見ている最中は検証できない**」も
            # ここで裏返ります。前提が先に出るので。
            #
            # **危ないところ**（承知のうえで採っています）: 読み上げが1文目の
            # **前半で**数字を言う本では、0.5〜1.5秒だけ画面に数字が無い状態になります。
            # 音と画がずれるのはここだけで、**逆側（同じ絵が2回）は毎本起きていました。**
            first = dict(visual)
            first["stat"] = ""
            first["formula"] = ""
            first["note_lead"] = True
            second = dict(visual)
            second["headline"] = _reveal_headline(
                visual.get("headline", ""), "", step=2, total=2
            )
            return [first, second]
    return [visual]


def render(visuals: list[dict], out_dir: Path, topic_id: str = "",
           theme_index: int | None = None, portrait: bool = False) -> list[Path]:
    """図解を1枚ずつ PNG にする。配色は theme_index があれば順番に回す。

    portrait=True でショート向けの縦画面（1080x1920）にする。

    **折り返しが正しいかは、目視でなくブラウザに数えさせる。**
    2026-08-08、子エージェントの目視は横向きの見出しについて
    「語中で折れている」と報告したが、実測すると1行も折れていなかった
    （見出しの中の空白を改行と読み違えていた）。逆に**本当に折れていた
    縦向きの `.note` は報告に無かった。** 目視は取りこぼすし、無いものを作る。

    収まらなければ**文字数の上限を段階的に詰めて焼き直す**。
    それでも収まらないときは、一番ましだったものを出す。
    **止めない**（1本落とすほうが損失が大きい。CLAUDE.md の4）。
    """
    from playwright.sync_api import sync_playwright

    theme = theme_for(topic_id, theme_index)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    executable = _chromium_path()
    if executable:
        print(f"[visuals] chromium: {executable}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=executable, args=["--font-render-hinting=none"]
        )
        size = VIEWPORT_PORTRAIT if portrait else VIEWPORT
        page = browser.new_page(
            viewport={"width": size[0], "height": size[1]},
            device_scale_factor=SCALE,
        )
        for i, visual in enumerate(visuals):
            path = out_dir / f"slide_{i:03d}.png"
            best, done = (10**9, 0, 1.0), False
            for zoom in ZOOMS:
                for tighten in range(MAX_TIGHTEN + 1):
                    page.set_content(build_html(visual, theme, portrait, tighten, zoom),
                                     wait_until="load")
                    bad = page.evaluate(_LINE_PROBE_JS)
                    if bad < best[0]:
                        best = (bad, tighten, zoom)
                    if bad == 0:
                        done = True
                        break
                if done:
                    break
            if not done:
                # 詰めきっても収まらなかった。一番ましだったところへ戻して焼く。
                page.set_content(
                    build_html(visual, theme, portrait, best[1], best[2]), wait_until="load")
                print(f"[visuals] [!] {i}枚目: 収まらない箇所が {best[0]} 残った"
                      f"（詰め {best[1]} 段・縮小 {best[2]}）。"
                      f"{visual.get('headline', '')!r}")
            page.screenshot(path=str(path))
            paths.append(path)
            adj = "" if (best[1], best[2]) == (0, 1.0) else f"  詰め{best[1]}段 縮小{best[2]}"
            print(f"[visuals] {i + 1}/{len(visuals)} {visual.get('kind', 'stat')}{adj}")
        browser.close()

    return paths
