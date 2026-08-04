# youtube — 広告収益を目標にした自動投稿

台本 → 音声 → 図解 → 合成 → 検査 → 投稿 → 実績を見て次を決める、を毎日1本回します。

**GitHub Actions は使いません。** Claude Code の常駐セッションに定期実行を撃ち込む形で動き、
台本の思考はセッションの中で完結します。だから Anthropic の API キーも Claude のトークンも
要りません。必要な秘密情報は **YouTube の3つだけ**です。

- **目標と動き方 → [CLAUDE.md](CLAUDE.md)** … セッション開始時に自動で読まれる。最優先
- **立ち上げ・引き継ぎ → [docs/KICKOFF.md](docs/KICKOFF.md)**
- **判断の記録 → [docs/JOURNAL.md](docs/JOURNAL.md)** … 毎回ここから読む
- **初回セットアップ → [docs/SETUP.md](docs/SETUP.md)** … 鍵の取り方（30〜40分・スマホ可）
- **方針と見通し → [docs/STRATEGY.md](docs/STRATEGY.md)** … RPM、月20万に要る数字、リスク

## 1本ぶんの流れ

```sh
bash scripts/setup.sh                    # ffmpeg・open-jtalk・依存を入れる（何度でも安全）
python -m src.script_writer              # 台本のJSONスキーマを出す
#  → セッションが台本を書いて build/script.json に保存
python -m src.pipeline --script build/script.json --topic <ID> --dry-run
python -m src.pipeline --script build/script.json --topic <ID>
```

`--script` を省くと `claude` CLI で台本を生成しますが、常駐セッションで動かす前提なので
通常は使いません（その経路だけ `CLAUDE_CODE_OAUTH_TOKEN` が要ります）。

## 構成

```
config/channel.yaml    チャンネル設定（ニッチ・尺・投稿時刻・声・再生リスト）
config/topics.yaml     テーマのプール
scripts/setup.sh       実行環境の準備
src/script_writer.py   台本のスキーマと、CLI経由の生成（常駐セッションでは未使用）
src/tts.py             読み上げ（open-jtalk / Google TTS の自動切替）
src/visuals.py         図解を HTML で組み、Chromium で撮る（素材は全部自前）
src/subtitles.py       ASS 字幕（音声の実尺に合わせる）
src/renderer.py        ffmpeg で合成
src/thumbnail.py       Pillow でサムネイル
src/verify.py          投稿前の検査。1つでも外れたら投稿しない
src/history.py         投稿済みをチャンネルから復元（説明欄の [t:...] を読む）
src/uploader.py        投稿・再生リストへの追加・最初のコメント
src/analytics.py       維持率 → 次のテーマ
src/pipeline.py        以上を1本ぶん通す
```

## 設計で効いている点

| | 理由 |
|---|---|
| 8分半を下回ったら投稿しない | ミッドロール広告を複数入れられる下限。RPM の最大要因 |
| 投稿前に尺・解像度・音声・冒頭を検査 | 壊れた動画が本番に出るより、その日1本落ちるほうがいい |
| 投稿済みは説明欄の `[t:ID]` から復元 | ファイルに持つと、動画を消したときに記録が実体とずれる |
| 図解は自前（フリー素材を使わない） | 「量産された無個性コンテンツ」判定への材料。詳細は STRATEGY.md §5 |
| 次のテーマは維持率で選び、3割は無作為 | 再生回数は古い動画ほど積み上がるので物差しにならない |
| 再生リストへ自動追加 | 次の動画へ流れやすくなり、総再生時間が伸びる |

## 調整する場所

| やりたいこと | 触る場所 |
|---|---|
| ジャンルを変える | `config/channel.yaml` の `channel.niche` / `persona` |
| 動画を長くする | `config/channel.yaml` の `video.target_minutes` |
| 声を変える | `config/channel.yaml` の `generation.tts`（`engine` / `voice`） |
| 公開時刻を変える | `config/channel.yaml` の `publish.publish_hour_jst` |
| 再生リスト名を変える | `config/channel.yaml` の `publish.playlist` |
| 投稿頻度を変える | 定期実行トリガーの cron（KICKOFF.md 参照） |
| 台本の書き方 | `src/script_writer.py` の `ROLE` |
