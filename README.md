# youtube — 広告収益を目標にした自動投稿パイプライン

台本生成 → 音声合成 → 映像合成 → サムネ生成 → YouTube 投稿 → 実績を見てテーマ更新、
までを GitHub Actions で通します。

- **投稿だけ自動、あとは手押し。** 毎日 05:17 JST に1本作られ、その日の19時に公開されます。
  それ以外のワークフローは GitHub の画面からボタンで実行します（PC 不要・スマホ可）。
- 台本の生成は **Anthropic API（従量課金）を使いません**。Claude Code CLI を
  サブスクリプションの OAuth トークンで動かし、思考はそのセッション内で完結します。

- **運用 → [docs/RUNBOOK.md](docs/RUNBOOK.md)** … 頻度の変え方、失敗したときの手順
- **初回セットアップ → [docs/SETUP.md](docs/SETUP.md)** … 鍵の取り方（40〜60分）
- **方針と見通し → [docs/STRATEGY.md](docs/STRATEGY.md)** … RPM の話、月20万に必要な数字、リスク

## ワークフロー

| | 名前 | 実行 |
|---|---|---|
| 0 | 設定をチェックする | 手動（初回と、失敗したとき） |
| 1 | 動画をつくる（投稿しない） | 手動（中身を先に確認したいとき） |
| 2 | 動画をつくって投稿する | **毎日 05:17 JST に自動**＋手動でも追加可 |
| 3 | テーマを実績から入れ替える | 手動（週1回・4本たまってから） |

未投稿テーマが6件を切ると、投稿の直後に自動で5件補充します（日次でも枯れません）。

投稿済みの記録はリポジトリに持ちません。説明欄の末尾に `[t:テーマID]` を入れ、
毎回チャンネルから読み直します。動画を消せば記録も消え、そのテーマはまた作れます。

## 構成

```
config/channel.yaml    チャンネル設定（ニッチ・尺・投稿時刻・声）
config/topics.yaml     トピックプール（週次で自動更新される）
src/claude_cli.py      Claude Code CLI をヘッドレスで叩き、JSON を検証して返す
src/script_writer.py   台本＋メタデータ＋図解の指定を生成
src/tts.py             読み上げ（open-jtalk / Google TTS の自動切替）
src/visuals.py         図解を HTML で組み、Chromium で撮る（素材は全部自前）
src/subtitles.py       ASS 字幕を生成（音声の実尺に合わせる）
src/renderer.py        ffmpeg で合成
src/thumbnail.py       Pillow でサムネイル
src/verify.py          投稿前の検査。1つでも外れたら投稿しない
src/history.py         投稿済みをチャンネルから復元（説明欄の [t:...] を読む）
src/uploader.py        YouTube Data API v3 で投稿
src/analytics.py       維持率 → 次のテーマ
src/pipeline.py        以上を1本ぶん通す
scripts/preflight.py   環境チェック
```

## ローカルで試す

```bash
pip install -r requirements.txt
npm install -g @anthropic-ai/claude-code   # 台本生成に使う
python -m playwright install --with-deps chromium   # 図解の描画に使う
cp .env.example .env      # 値を埋める
sudo apt-get install -y ffmpeg fonts-noto-cjk open-jtalk \
  open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001

python scripts/preflight.py            # 何が足りないか確認
DRY_RUN=true python -m src.pipeline    # 投稿せず build/ に出力
```

## 調整する場所

| やりたいこと | 触る場所 |
|---|---|
| ジャンルを変える | `config/channel.yaml` の `channel.niche` / `persona` |
| 動画を長くする | `config/channel.yaml` の `video.target_minutes` |
| 声を変える | `config/channel.yaml` の `generation.tts`（`engine` / `voice`） |
| 公開時刻を変える | `config/channel.yaml` の `publish.publish_hour_jst` |
| 非公開→公開に切り替える | 「2」実行時の `visibility` で毎回選べる |
| 台本の書き方 | `src/script_writer.py` の `ROLE` |
| 生成モデル | `config/channel.yaml` の `generation.model`（`opus` / `sonnet`） |
| 投稿頻度を変える | `.github/workflows/2-publish.yml` の `cron`（[RUNBOOK](docs/RUNBOOK.md) 末尾） |
