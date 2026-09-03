# 画像の注文（機械 → ChatGPT Works → リポジトリ）

オーナー原文（2026-09-03 19:3x JST）:

> **「ちゃっとgpt Worksのセッションで毎時実行をさせるプロンプトを書いて。役割はリポジトリ経由であなたの指示を読みあなたが使う画像をgptimages2.0で生成して、リポジトリに送ること。」**

> **「動画内で使う画像はチャットgptのimages2.0を活用して」**（2026-09-03 20:0x JST ＝ **サムネの背景だけでなく、動画の中で使う画像も** ここで作らせる）

つまり **絵を作る係が1体 外に増えました**。うちの機械は「どの絵が要るか」を
**注文票**にして repo へ置くだけ。ChatGPT Works の毎時セッションがそれを読み、
GPT Image 2.0 で焼いて、**同じ repo に画像を push して返します**。

    機械（サブ）        data/image_orders/<id>.json         注文を置く
    ChatGPT Works      assets/images/<id>.<jpg|png>        画像を置く
                       data/image_orders.jsonl             受領・結果を1行 足す

## 注文票 `data/image_orders/<id>.json`

    {
      "id":       "2026-09-04-thumb-bg",       ← ファイル名と同じ。英数と - のみ
      "asked_at": "2026-09-03T19:30:00+09:00",
      "for":      "09/04 の本（1huadpEk6HY）のサムネ背景",   ← 人が読む用
      "prompt":   "GPT Image 2.0 にそのまま渡す文。日本語で可",
      "avoid":    "文字・ロゴ・実在の人物・透かし",           ← 省略可
      "size":     "1280x720",                  ← 1280x720 / 1920x1080 / 1080x1920
      "format":   "jpg",                       ← jpg か png
      "out":      "assets/images/2026-09-04-thumb-bg.jpg",
      "status":   "pending"
    }

**字は生成画像に入れさせません。** 日本語の見出しは `src/thumbnail.py` が後から載せます
（生成画像の中の日本語は崩れる・`prompt` に「文字を入れない」と必ず書くこと）。

## 受領 `data/image_orders.jsonl`（ChatGPT 側が1行 足す）

    {"id":"…","status":"done","out":"assets/images/….jpg","bytes":812345,
     "model":"gpt-image-2.0","delivered_at":"2026-09-03T20:05:00+09:00","note":""}
    {"id":"…","status":"failed","note":"生成が拒否された理由など"}

`status` が `done` の注文票は **`"status": "done"` に書き換えて残す**（消さない ——
オーナー 08/31「消さなくて良いよ時間かかるならわざわざ」）。

## 使う側（機械）

**【2026-09-03 21:2x】ここは長らく文書だけで、機械の側が1行もありませんでした。**
実測: 注文 **0件**・絵 **0件**・`image_orders` を書くコード **0か所**・
`assets/images` を読むコード **0か所**。
**外の毎時セッションは注文が置かれない限り1枚も焼けない**ので、
このままでは絵は永久に来ませんでした
（この repo でいちばん多い壊れ方: **言っている所と、している所が別**）。

**いまは `src/image_orders.py` が持っています**:

    python -m src.image_orders            # いまの注文と、届いている絵・**齢**
    python -m src.image_orders --order <題材>

    image_orders.place(題材, prompt, …)   注文票を置く（**冪等**。同じ id は上書きしない）
    image_orders.image_for(題材)          届いている絵。**無ければ None**
    visuals.bg_image_for(題材)            そのまま `data:` にして返す。無ければ空文字

- 注文は **`src/pipeline.py` が本を焼くたび自動で置きます**（`visuals.render()` の直前）。
  **その本には間に合いません** —— 拾われるまで最大1時間なので、間に合うのは
  **次に同じ題材を焼き直した回**（規則3「次の枠まで改善し続ける」）から。
- 絵が要る本の締切から **2時間 以上** 前に置くこと（`image_orders.LEAD`）。
  来ていなければ、**待たずに** いままでどおり `src/visuals.py` の自前の図解で焼くこと
  （**止めない**）。`image_for()` の `None` が、そのままその合図です。
- **動画の中**では `src/visuals.py` が背景（`.bg-photo`）に敷きます。
  **必ず暗幕（`.bg-veil`）が重なり、絵は `z-index: 0`・文字は `1`** です ——
  主役は**計算した数字**なので、絵が上に来てはいけません（CLAUDE.md の根幹）。
  検査は `tests/test_image_orders.py`（ブラウザに重ね順を数えさせています）。
- **サムネ**は `src/thumbnail.create(source=…)` にそのまま渡せます。
- **外のセッションが止まったことに気づく口**: `python -m src.image_orders` の
  「2時間 以上 待っている注文が N件」。齢が伸び続けたら、向こうが動いていません。
