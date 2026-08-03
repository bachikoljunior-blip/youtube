# youtube — 広告収益を目標にした自動投稿パイプライン

台本生成 → 音声合成 → 映像合成 → サムネ生成 → YouTube 投稿 → 実績を見てテーマ更新、
までを GitHub Actions で通します。

- **スケジュール実行（cron）は使いません。** GitHub の画面から番号順にボタンを押すだけ。
  PC 不要、スマホから操作できます。
- 台本の生成は **Anthropic API（従量課金）を使いません**。Claude Code CLI を
  サブスクリプションの OAuth トークンで動かし、思考はそのセッション内で完結します。

- **毎日の操作 → [docs/RUNBOOK.md](docs/RUNBOOK.md)** … 押すボタンとリンクだけ
- **初回セットアップ → [docs/SETUP.md](docs/SETUP.md)** … 鍵の取り方（40〜60分）
- **方針と見通し → [docs/STRATEGY.md](docs/STRATEGY.md)** … RPM の話、月20万に必要な数字、リスク

## ワークフロー

すべて手動実行（`workflow_dispatch`）です。

| | 名前 | いつ押すか |
|---|---|---|
| 0 | 設定をチェックする | 初回と、失敗したとき |
| 1 | 動画をつくる（投稿しない） | 中身を先に確認したいとき |
| 2 | 動画をつくって投稿する | **毎日これ** |
| 3 | テーマを実績から入れ替える | 週1回・4本たまってから |

## 構成

```
config/channel.yaml    チャンネル設定（ニッチ・尺・投稿時刻・声）
config/topics.yaml     トピックプール（週次で自動更新される）
src/claude_cli.py      Claude Code CLI をヘッドレスで叩き、JSON を検証して返す
src/script_writer.py   台本＋メタデータを生成（pydantic で構造を担保）
src/tts.py             Google Cloud TTS で読み上げ
src/assets.py          Pexels から背景素材
src/subtitles.py       ASS 字幕を生成（音声の実尺に合わせる）
src/renderer.py        ffmpeg で合成
src/thumbnail.py       Pillow でサムネイル
src/uploader.py        YouTube Data API v3 で投稿
src/analytics.py       実績 → 次のトピック
src/pipeline.py        以上を1本ぶん通す
scripts/get_refresh_token.py  初回だけ実行するOAuth
scripts/preflight.py          環境チェック
```

## ローカルで試す

```bash
pip install -r requirements.txt
npm install -g @anthropic-ai/claude-code   # 台本生成に使う
cp .env.example .env      # 値を埋める
sudo apt-get install -y ffmpeg fonts-noto-cjk

python scripts/preflight.py            # 何が足りないか確認
DRY_RUN=true python -m src.pipeline    # 投稿せず build/ に出力
```

## 調整する場所

| やりたいこと | 触る場所 |
|---|---|
| ジャンルを変える | `config/channel.yaml` の `channel.niche` / `persona` |
| 動画を長くする | `config/channel.yaml` の `video.target_minutes` |
| 声を変える | `config/channel.yaml` の `generation.tts.voice` |
| 公開時刻を変える | `config/channel.yaml` の `publish.publish_hour_jst` |
| 非公開→公開に切り替える | 「2」実行時の `visibility` で毎回選べる |
| 台本の書き方 | `src/script_writer.py` の `ROLE` |
| 生成モデル | `config/channel.yaml` の `generation.model`（`opus` / `sonnet`） |
| あとで自動実行に戻す | `.github/workflows/2-publish.yml` に `schedule:` を足す（[RUNBOOK](docs/RUNBOOK.md) 末尾） |
