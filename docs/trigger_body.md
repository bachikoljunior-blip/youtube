親の周です。考える前にこの2行だけ撃ってください。

    git pull --no-rebase origin <<branch>>
    python scripts/next_round.py

WAIT なら何もせずに終える（ただし終わる前に必ず send_later で自分を呼び戻すこと）。
GO <役> なら docs/spawn_prompt.rendered.md の kind: <役> の prompt を1字も変えずに
Agent ツールへ渡す（isolation: "worktree" と run_in_background: true を必ず付ける）。
立てたら python scripts/next_round.py --record <役> を撃ち、data/rounds.jsonl を
commit して push する。

手順の正本は docs/trigger_parent.md の第1節。毎回読み直すこと（サブが書き換えている）。
サブの中身は判断しない。子セッションは立てない（create_session は人のタップを待つ）。
