# 子に渡すプロンプトの正本

**組み立てるのは `scripts/spawn_prompt.py` です。手で書き写さないこと。**

    python scripts/spawn_prompt.py --kind hourly            # 定期の回
    python scripts/spawn_prompt.py --kind owner-full  --note "<原文>"
    python scripts/spawn_prompt.py --kind owner-record --note "<原文>"
    python scripts/spawn_prompt.py --kind hourly --only "<この回はこれだけ>"

`--json` を足すと **`create_session` にそのまま渡せる引数一式**が出ます
（`source_url` / `source_revision` / `environment_id` / `tags` / `prompt`）。

## なぜ道具にしたか（2026-08-20）

**渡し方が親のターンの中にしかなく、子が直せませんでした。** 毎時走るので、
ここの欠陥は他のどこよりも回数を掛けて効きます。そして実測で3つ壊れています:

1. **`source_url` / `source_revision` の付け忘れ** —— 8/17 04:1x と 8/18 23:5x。
   repo の無い子が立ち、**8/17 の回は1件も出せずに終わりました**（26回で初）
2. **親が本文を要約して、条件をまるごと落とす** —— 8/10 に別リポジトリで観測
3. **申し送りが親の文脈にしか無く、子が死ぬと依頼ごと消える** —— 8/15・8/16 に2回

**1 と 2 は、道具が組み立てれば起きません。** 3 は、下の型が
`inbox.py --open` を**先頭の行**に固定することで塞ぎます。

## 型に必ず入るもの（オーナー指定 2026-08-20）

- **申し送りは原文のまま**（`--note`）。要約しない。数字は桁もそのまま
- **同じ枝で走っている他のセッションを名指しする**（`--siblings`）。
  名指しが無いと、2人が同じ日の予約を取り合います（8/15 03:48/03:50 の再発）
- **「この回はこれだけ」と書く**（`--only`）。書かないと1周が丸ごと乗ってきます

## 型を直したくなったら

**このファイルの ```text ブロックを直してください。** 次の発火から効きます。
`tests/test_spawn_prompt.py` が「型が空でないこと」「repo と枝が必ず入ること」
「`--only` を渡したら1周を頼まないこと」を見ています。

---

## kind: hourly

```text
<<lead>>

<<note_block>>

<<siblings_block>>
```

**先頭の1行は2つあります。`--only` を渡したかどうかで入れ替わります。**
渡したのに「1周してください」が残ると、**受け取った子は両方やろうとします。**

## block: lead-round

```text
【定期の回】`docs/trigger_main.md` を読んで、そのとおりに1周してください。
**最低1件は出してから終わること**（同 §4）。最後に自分を archive すること。
```

## block: lead-only

```text
【指名の回】**この回はこれだけです: <<only>>**

`docs/trigger_main.md` の1周はやらないこと。生成も投稿もしない
（§4 の「1件は出してから終わる」も、この回には掛かりません）。
検査を通して push、`docs/JOURNAL.md` に理由を残すこと。
最後に自分を archive すること。
```

## kind: owner-full

```text
【オーナーからの連絡】原文: 「<<note>>」

**いちばん先に `python scripts/inbox.py --open "<この本文>"` を打って push すること**（数秒）。
**あなたが死んでも、次の子がそれを見つけます。** 親は repo を触れないので、
押す前に落ちると依頼ごと消えます（8/15・8/16 に2回消えました）。

`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば
`docs/JOURNAL.md` に書いて push すること。
そのうえで `docs/trigger_main.md` の1周をやること（**最低1件は出す**。同 §4）。
最後に自分を archive すること。

<<siblings_block>>
```

## kind: owner-record

```text
【オーナーからの連絡・記録のみ】原文: 「<<note>>」

**いちばん先に `python scripts/inbox.py --open "<この本文>"` を打って push すること**（数秒）。

`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば
`docs/JOURNAL.md` に書いて push すること。

**`docs/trigger_main.md` の1周はやらないこと。別の子が回しています**
（§4 の「1件は出してから終わる」も、この回には掛かりません。
**記録して push したら、それがこの回の成果です**）。
最後に自分を archive すること。

<<siblings_block>>
```
