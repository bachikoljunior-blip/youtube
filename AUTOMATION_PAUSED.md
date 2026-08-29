# AUTOMATION PAUSED — 2026-08-30

## Status

**動画の生成・アップロード・再スケジュールを停止する。分析とデータ保全だけは続けてよい。**

## Why

YouTube の現行チャンネル収益化ポリシーは、次を収益化不可として明示している。

- mass-produced / generic / repetitive / template-based content
- AI-generated personas presenting themselves as human experts on sensitive topics
- AI personas providing financial guidance or interpreting legal rules

Current channel configuration conflicts with that policy:

- niche: お金・税金・キャリア
- persona: 「元・事業会社の経理／人事」と名乗る
- narration: synthetic TTS
- production: automated template pipeline

このまま投稿を増やしても、目標である YouTube 収益化の到達可能性を上げず、審査時の不適合材料を増やすおそれがある。

Official policy reviewed 2026-08-30:
https://support.google.com/youtube/answer/1311392

## What is blocked

- `python -m src.pipeline`
- upload entry points
- batch/Shorts generation
- title/thumbnail/link/reschedule automation

`src/pause_guard.py` と `src/config.py` が二重に止める。

## What remains allowed

- analytics/status/reach/retention の読取
- 既存データの保存
- monetizable replacement format の調査
- dry analysis that does not generate, upload, schedule, retitle or otherwise modify channel content

## Resume gate

次の全条件が記録されるまで解除しない。

1. sensitive-topic AI persona を使わない
2. human expert を装わない
3. final videos are materially varied and demonstrate a clear original creative contribution
4. policy-compliant channel concept is reviewed against the current official policy
5. 既存動画の扱いと新旧テーマ混在リスクを決める
6. monetization path and acquisition economics are recalculated

## Override

緊急の手動検証だけ、明示的に次を設定したプロセスで許可する。

`ALLOW_POLICY_PAUSED_AUTOMATION=I_ACCEPT_YPP_POLICY_RISK`

通常の自動運転や恒久解除には使わない。
