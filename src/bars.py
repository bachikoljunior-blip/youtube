"""公開した動画が chart に出した数値を、**コンテナをまたいで**覚えておく。

なぜ要るか。同じ図を続けて出すと、YouTube のポリシーの
「同じチャンネルの動画を続けて数本視聴した後、繰り返しのように感じられる
可能性のあるコンテンツ」に当たる。**収益化されなければ収入はゼロ**なので、
これは見栄えではなく到達可能性そのものの問題。

これを防ぐ仕組みは2つあった。`script_writer.used_bars()`（先に「使用済み」と
教える）と `verify._check_not_repeat()`（投稿前に落とす）。
**どちらも `build/*/script.json` だけを見ていた。**

`build/` は `.gitignore` に入っている（`.gitignore:2`）。実行環境は使い捨てで、
リポジトリは起動のたびに clone し直される。**つまり新しいコンテナでは
`build/` が空で、両方とも比較対象ゼロのまま黙って通る。**
エラーも警告も出ない。**止めているつもりで、何も止めていない状態になる。**

2026-08-09 に気づいた。このコンテナがたまたま長く生きていて 27 本ぶんの
build が残っていたので動いて見えていただけで、次の起動では消える。

## ファイルに持つことにした理由

`history.py` は「ファイルに投稿済みを書き溜めると、動画を消したときに嘘になる。
状態はチャンネルそのものが持つ」という作りで、その考えは正しい。
だが**棒の数値は説明欄から復元できない。** 説明欄に埋めるのは、
視聴者に見せる場所を内部都合で汚すことになるのでやらない。

そこで折衷にした。**数値はファイルに置くが、正否はチャンネルに決めさせる。**
読むときに `history.posted_topic_ids()` と突き合わせ、
**チャンネルにもう無いテーマは落とす。** 動画を消せば、その棒はまた使える。
`history.py` が避けたかった「消したのに使用済みのまま」は起きない。

チャンネルが読めなかったときは**落とさない**（ファイルの全件を使う）。
比較対象が多いほうが厳しい側で、黙って通すよりよい。
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

RECORD = config.ROOT / "data" / "published_bars.json"


def _load() -> dict:
    if not RECORD.exists():
        return {}
    try:
        return json.loads(RECORD.read_text(encoding="utf-8"))
    except Exception:
        return {}


def charts_of(script: dict) -> list[list[str]]:
    """台本から chart の `display` の組を取り出す。"""
    out = []
    for seg in script.get("segments") or []:
        v = seg.get("visual") or {}
        if v.get("kind") == "chart" and v.get("bars"):
            out.append([str(b.get("display", "")) for b in v["bars"]])
    return out


def record(topic_id: str, video_id: str, script: dict) -> None:
    """公開した直後に呼ぶ。**公開したものだけを記録する。**

    作って捨てた台本まで数えると、他のテーマを不当に狭める。
    ポリシーが問題にしているのは**視聴者が続けて見られるもの**だけ。
    """
    charts = charts_of(script)
    if not charts:
        return
    data = _load()
    data[topic_id] = {"video_id": video_id, "charts": charts}
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[bars] {topic_id} の chart {len(charts)}枚を記録しました（{RECORD.name}）")


_alive_cache: set[str] | None = None


def _alive() -> set[str] | None:
    """チャンネルに今ある投稿済みテーマID。読めなければ None。"""
    global _alive_cache
    if _alive_cache is not None:
        return _alive_cache
    try:
        from . import history

        _alive_cache = history.posted_topic_ids()
    except Exception as exc:  # 認証が無い・オフライン・API 障害
        print(f"[bars] チャンネルを読めませんでした（記録を全件そのまま使います）: {exc}")
        return None
    return _alive_cache


def published_charts(exclude: str = "") -> dict[str, list[list[str]]]:
    """テーマID → chart の組。チャンネルから消えた動画のぶんは落とす。"""
    alive = _alive()
    out: dict[str, list[list[str]]] = {}
    for topic_id, entry in _load().items():
        if exclude and topic_id == exclude:
            continue
        if alive is not None and topic_id not in alive:
            continue
        out[topic_id] = entry.get("charts") or []
    return out


def published_displays(exclude: str = "") -> set[str]:
    """公開済みの棒の数値を平らにして返す。"""
    seen: set[str] = set()
    for charts in published_charts(exclude).values():
        for bars in charts:
            seen.update(b for b in bars if b)
    return seen
