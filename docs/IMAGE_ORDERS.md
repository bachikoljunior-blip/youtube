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

- 注文を置くのはサブ。**置いただけでは絵は来ません**（毎時のセッションが拾うまで最大1時間）。
- 絵が要る本の締切から **2時間 以上** 前に置くこと。来ていなければ、**待たずに**
  いままでどおり `src/visuals.py` の自前の図解で焼くこと（**止めない**）。
- 受け取った画像は `assets/images/` に在る。`src/thumbnail.create(source=…)` にそのまま渡せる。
