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

VIEWPORT = (1280, 720)   # deviceScaleFactor=2 で 2560x1440 になる
SCALE = 2

BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1280px; height: 720px; overflow: hidden; }
body {
  font-family: "Noto Sans CJK JP", "Noto Sans JP", "Hiragino Sans", sans-serif;
  background: #10141c;
  color: #f2f4f8;
  display: flex; flex-direction: column;
  padding: 64px 72px 72px 84px;
  position: relative;
}
body::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 12px;
  background: #ffcc00;
}
body::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(120% 90% at 78% 8%, rgba(90,120,190,.22), transparent 60%);
}
.headline {
  font-size: 46px; font-weight: 900; letter-spacing: .01em;
  color: #ffcc00; line-height: 1.25; margin-bottom: 34px;
}
.body { flex: 1; display: flex; flex-direction: column; justify-content: center; }

/* kind=stat */
.stat { font-size: 172px; font-weight: 900; line-height: 1.02; letter-spacing: -.02em; }
.note { margin-top: 26px; font-size: 34px; font-weight: 700; color: #9fb0cc; }

/* kind=steps / compare */
ol, ul { list-style: none; display: flex; flex-direction: column; gap: 22px; }
li {
  display: flex; align-items: baseline; gap: 22px;
  font-size: 42px; font-weight: 700; line-height: 1.35;
}
li .marker {
  flex: 0 0 auto; min-width: 56px; height: 56px; border-radius: 12px;
  background: #ffcc00; color: #10141c;
  font-size: 30px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
}
.compare li .marker { background: #4d7cff; color: #f2f4f8; padding: 0 16px; }

/* kind=table */
table { width: 100%; border-collapse: collapse; font-size: 36px; }
th, td { padding: 18px 20px; text-align: left; }
th {
  font-size: 28px; font-weight: 900; color: #10141c; background: #ffcc00;
}
th:first-child { border-radius: 10px 0 0 10px; }
th:last-child  { border-radius: 0 10px 10px 0; }
td { font-weight: 700; border-bottom: 2px solid rgba(255,255,255,.10); }
tr:last-child td { border-bottom: none; }
td:first-child { color: #9fb0cc; }
"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _body_html(visual: dict) -> str:
    kind = (visual.get("kind") or "stat").strip()

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
            f'<li><span class="marker">{markers[i]}</span><span>{_esc(text)}</span></li>'
            for i, text in enumerate(visual["items"][:4])
        )
        return f'<ul class="{cls}">{items}</ul>'

    # 既定は stat。数字が無ければ見出しだけで成立するので何も出さない。
    stat = visual.get("stat") or ""
    note = visual.get("note") or ""
    parts = []
    if stat:
        parts.append(f'<div class="stat">{_esc(stat)}</div>')
    if note:
        parts.append(f'<div class="note">{_esc(note)}</div>')
    return "".join(parts)


def build_html(visual: dict) -> str:
    return (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        f"<style>{BASE_CSS}</style></head><body>"
        f'<div class="headline">{_esc(visual.get("headline", ""))}</div>'
        f'<div class="body">{_body_html(visual)}</div>'
        "</body></html>"
    )


def render(visuals: list[dict], out_dir: Path) -> list[Path]:
    """図解を1枚ずつ PNG にする。"""
    import os

    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    # Chromium が同梱済みで、playwright のビルド番号と合わない環境向けの逃げ道。
    # CI では playwright install が合うものを入れるので、ここは空のままになる。
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", "").strip() or None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=executable, args=["--font-render-hinting=none"]
        )
        page = browser.new_page(
            viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]},
            device_scale_factor=SCALE,
        )
        for i, visual in enumerate(visuals):
            path = out_dir / f"slide_{i:03d}.png"
            page.set_content(build_html(visual), wait_until="load")
            page.screenshot(path=str(path))
            paths.append(path)
            print(f"[visuals] {i + 1}/{len(visuals)} {visual.get('kind', 'stat')}")
        browser.close()

    return paths
