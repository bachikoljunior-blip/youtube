# youtube — 広告収益を目標にした自動投稿パイプライン

台本生成 → 音声合成 → 映像合成 → サムネ生成 → YouTube 投稿 → 実績を見てテーマ更新、
までを GitHub Actions で毎日自動実行します。

- **まず読む → [docs/SETUP.md](docs/SETUP.md)** … あなたがやる作業（リンク付き・40〜60分）
- **方針と見通し → [docs/STRATEGY.md](docs/STRATEGY.md)** … RPM の話、月20万に必要な数字、リスク

## 何が動くか

| ワークフロー | 実行 | 中身 |
|---|---|---|
| `publish` | 毎日 08:00 JST | 動画を1本作って、その日の19:00 JST 公開で予約投稿 |
| `optimize` | 毎週月曜 10:00 JST | Analytics を読んでトピックプールを入れ替え |

## 構成

```
config/channel.yaml    チャンネル設定（ニッチ・尺・投稿時刻・声）
config/topics.yaml     トピックプール（週次で自動更新される）
src/script_writer.py   Claude で台本＋メタデータを構造化生成
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
| 非公開→公開に切り替える | `config/channel.yaml` の `publish.visibility` を `public` に |
| 台本の書き方 | `src/script_writer.py` の `SYSTEM` |
| 投稿頻度 | `.github/workflows/publish.yml` の `cron` |
