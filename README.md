# youtube — POLICY-PAUSED

> **2026-08-30:** 現行の「合成音声の元・経理／人事ペルソナが、お金・税金・キャリアを自動解説する」方式は停止中です。YouTube の現行収益化ポリシーが、金融・法律などの sensitive topic を人間の専門家として説明する AI persona を収益化不可と明示したためです。生成・投稿系コマンドはコードでも停止しています。詳細は [`AUTOMATION_PAUSED.md`](AUTOMATION_PAUSED.md)。分析と既存データの保全だけは継続できます。

## 旧方式の説明（記録として保存）

台本 → 音声 → 図解 → 合成 → 検査 → 投稿 → 実績を見て次を決める、を毎日1本回す設計でした。

**GitHub Actions は使いません。** Claude Code の常駐セッションに定期実行を撃ち込む形で動き、
台本の思考はセッションの中で完結します。だから Anthropic の API キーも Claude のトークンも
要りません。必要な秘密情報は **YouTube の3つだけ**です。

- **停止理由と解除条件 → [AUTOMATION_PAUSED.md](AUTOMATION_PAUSED.md)** … 最優先
- **目標と動き方 → [CLAUDE.md](CLAUDE.md)** … セッション開始時に自動で読まれる
- **立ち上げ・引き継ぎ → [docs/KICKOFF.md](docs/KICKOFF.md)**
- **判断の記録 → [docs/JOURNAL.md](docs/JOURNAL.md)**
- **初回セットアップ → [docs/SETUP.md](docs/SETUP.md)**
- **方針と見通し → [docs/STRATEGY.md](docs/STRATEGY.md)**

## 旧1本ぶんの流れ（現在はガードが停止）

```sh
bash scripts/setup.sh
python -m src.script_writer
python -m src.pipeline --script build/script.json --topic <ID> --dry-run
python -m src.pipeline --script build/script.json --topic <ID>
```

`AUTOMATION_PAUSED.md` が存在する間、生成・アップロード・再スケジュール・タイトル/サムネ変更等の entry point は停止します。通常運転で override を使わないでください。

## 構成

```
config/channel.yaml    旧チャンネル設定
scripts/policy_pause.sh  Claude の各ターンへ停止状態を注入
src/pause_guard.py     生成・投稿 entry point の hard stop
src/script_writer.py   台本スキーマ
src/tts.py             読み上げ
src/visuals.py         図解
src/subtitles.py       ASS 字幕
src/renderer.py        ffmpeg 合成
src/thumbnail.py       サムネイル
src/verify.py          投稿前検査
src/history.py         投稿済み履歴
src/uploader.py        投稿
src/analytics.py       分析
src/pipeline.py        旧パイプライン
```

## 停止中に許可すること

- `scripts/status.py` 等による分析
- 既存データ・動画・設定の保全
- 現行ポリシーに適合する別形式の調査

チャンネルを削除したり、過去データを捨てたりはしていません。解除条件を満たす新方式が確定するまで、投稿在庫を増やしません。
