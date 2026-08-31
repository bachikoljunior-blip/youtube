# youtube

> **2026-08-31: 止まっていません。** 08-30 に `AUTOMATION_PAUSED.md` という**ファイル1枚**で全体が止まり（約22時間・4周ぶんの生成）、オーナー本人がそのファイルを消しました（`1aa1e65a`）。原文は **「勝手にそれで止まるのなし。今後そういうことがないようにして」**。
>
> **いま止まるのは、`.owner-pause` が repo の根に在るときだけ**です。**その印を作るコードは、この repo に1行もありません** —— 人の手でしか置けません。判定は `src/pause_guard.is_paused()` の**1か所**。検査は `tests/test_pause_needs_owner.py`。
>
> **止める仕掛けを足さないこと。作りに問題を見つけたら、止めるのではなく直すこと**（`CLAUDE.md` 冒頭）。08-30 に止めた理由（AI persona が人間の専門家を名乗って sensitive topic を扱う形）は、**名乗りを落とすことで外れました** —— `config/channel.yaml` と `src/verify._check_no_human_expert_claim()`。

## 方式

台本 → 音声 → 図解 → 合成 → 検査 → 投稿 → 実績を見て次を決める。

**GitHub Actions は使いません。** Claude Code の常駐セッションに定期実行を撃ち込む形で動き、
台本の思考はセッションの中で完結します。だから Anthropic の API キーも Claude のトークンも
要りません。必要な秘密情報は **YouTube の3つだけ**です。

- **目標と動き方 → [CLAUDE.md](CLAUDE.md)** … セッション開始時に自動で読まれる
- **立ち上げ・引き継ぎ → [docs/KICKOFF.md](docs/KICKOFF.md)**
- **判断の記録 → [docs/JOURNAL.md](docs/JOURNAL.md)**
- **初回セットアップ → [docs/SETUP.md](docs/SETUP.md)**
- **方針と見通し → [docs/STRATEGY.md](docs/STRATEGY.md)**

## 1本ぶんの流れ

```sh
bash scripts/setup.sh
python -m src.script_writer
python -m src.pipeline --script build/script.json --topic <ID> --dry-run
python -m src.pipeline --script build/script.json --topic <ID>
```

**オーナーが `.owner-pause` を手で置いている間だけ**、生成・アップロード・再スケジュール・タイトル/サムネ変更等の entry point が停止します（`src/pause_guard.BLOCKED_ENTRYPOINTS`）。**その印を機械が置くことはありません。** 置かれていたら、外さずにオーナーへ聞くこと。override（`ALLOW_POLICY_PAUSED_AUTOMATION`）は人が手で確かめるときの口で、自動運転のためのものではありません。

## 構成

```
config/channel.yaml    チャンネル設定
scripts/policy_pause.sh  停止中かどうかを各ターンへ注入（判定は pause_guard に聞く）
src/pause_guard.py     **止まるかどうかを決める、ただ1か所**（`.owner-pause` が在るときだけ）
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
