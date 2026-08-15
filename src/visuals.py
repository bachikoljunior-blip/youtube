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


def _wrap_note(text: str, portrait: bool, tighten: int = 0) -> str:
    """stat の下の補足を、語の途中で折らずに改行する。"""
    return _wrap(text, NOTE_CHARS_PORTRAIT if portrait else NOTE_CHARS, tighten)


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
    pcts = [max(float(b.get("value", 0)) / top * 100.0, 1.0) for b in bars]
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
        for pct, need in zip(pcts, ns):
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
        ns = [_em_width(str(b.get("display", ""))) * fpx + 16 * 2 for b in bars]
        k = 1.0
        while k > 0.5 and not fits(k, ns):
            k -= 0.01
        if fits(k, ns):
            scale, size, needs = k, fpx, ns
            break
    else:
        # どの大きさでも収まらない。**黙って出さない。** 一番小さい字で最善を尽くす。
        scale, size = 0.5, font_px - 7
        needs = [_em_width(str(b.get("display", ""))) * size + 16 * 2 for b in bars]

    rows = []
    for b, pct0, need_px in zip(bars, pcts, needs):
        pct = pct0 * scale
        thin = " thin" if track_px * pct / 100.0 < need_px else ""
        rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{_wrap_label(b["label"], portrait, tighten)}</div>'
            f'<div class="bar-track">'
            f'<div class="bar-fill{thin}" style="width:{pct:.1f}%">'
            f'<span class="bar-value" style="font-size:{size}px">'
            f'{_esc(b.get("display", ""))}</span>'
            f"</div></div></div>"
        )
    return f'<div class="chart">{"".join(rows)}</div>'


def _body_html(visual: dict, portrait: bool = False, tighten: int = 0) -> str:
    kind = (visual.get("kind") or "stat").strip()

    if kind == "chart" and visual.get("bars"):
        return _chart_html(visual, portrait, tighten)

    if kind == "table" and visual.get("headers") and visual.get("rows"):
        head = "".join(f"<th>{_esc(h)}</th>" for h in visual["headers"][:3])
        rows = "".join(
            "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row[:3]) + "</tr>"
            for row in visual["rows"][:4]
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"

    if kind in ("steps", "compare") and visual.get("items"):
        cls = "compare" if kind == "compare" else "steps"
        markers = ("A", "B", "C", "D") if kind == "compare" else ("1", "2", "3", "4")
        items = "".join(
            f'<li><span class="marker">{markers[i]}</span>'
            f'<span>{_wrap_item(text, portrait, tighten)}</span></li>'
            for i, text in enumerate(visual["items"][:4])
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
        parts.append(f'<div class="note">{_wrap_note(note, portrait, tighten)}</div>')
    return "".join(parts)


def build_html(visual: dict, theme: dict | None = None, portrait: bool = False,
               tighten: int = 0, zoom: float = 1.0) -> str:
    """`tighten` は横（勝手な折り返し）、`zoom` は縦（枠からの溢れ）を直す。

    **2つは別の向きなので、別のつまみが要る。** `tighten` を上げると行数が
    増えて縦には**悪化する**。2026-08-08、縦向きの steps が 27px 溢れていた。
    """
    head = _wrap_head(visual.get("headline", ""), portrait, tighten)
    extra = "" if zoom >= 0.999 else f".body {{ zoom: {zoom:.2f}; }}"
    return (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        f"<style>{_css(theme or THEMES[0], portrait)}{extra}</style></head><body>"
        f'<div class="headline">{head}</div>'
        f'<div class="body">{_body_html(visual, portrait, tighten)}</div>'
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
  for (const s of ['.headline', '.note', '.bar-label', 'li > span:not(.marker)']) {
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
        for i in range(k):
            cut = max(1, round(n * (i + 1) / k))
            v = dict(visual)
            v[key] = seq[:cut]
            if key == "bars":
                # 目盛りを全体の最大値で固定する。切っても棒が伸び縮みしない。
                values = [float(b.get("value", 0) or 0) for b in seq]
                v["scale_max"] = max(values) if values else 0
            out.append(v)
        # 末尾は必ず「全部出ている」状態にする
        out[-1] = dict(visual)
        if key == "bars":
            values = [float(b.get("value", 0) or 0) for b in seq]
            out[-1]["scale_max"] = max(values) if values else 0
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
    if (visual.get("kind") or "stat").strip() == "stat":
        if visual.get("stat") and visual.get("note"):
            first = dict(visual)
            first["note"] = ""
            return [first, dict(visual)]
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
