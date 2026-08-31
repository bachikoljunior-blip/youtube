# 作りの床 6件（旧 Resume gate）

> **これは switch ではありません。** このファイルが在っても無くても、
> **生成も投稿も1ミリも止まりません。** 止まるのは
> `.owner-pause` がオーナーの手で置かれたときだけです
> （`src/pause_guard.is_paused()` の1か所。検査 `tests/test_pause_needs_owner.py`）。

**なぜこのファイルがあるか**（2026-08-31）。

この6件は 2026-08-30 に `AUTOMATION_PAUSED.md` の `## Resume gate` として
書かれ、**同じファイルが止める switch も兼ねていました。** オーナーは 08-31 に
そのファイルを消しました —— **消えたのは「止める力」であって、
この6件が言っている作りの条件ではありません。**

**条件の本文をここへ写した理由**: 消えたまま放っておくと、
`src/resume_gate.conditions()` が 0件 を返し、`python scripts/eta.py --gate` は
**0/0** と印字します。**「測れていない」ことを「条件が無い」として印字する**のが、
この module がいちばん避けようとしている壊れ方です
（`src/resume_gate` の冒頭「測れないことを誤りゼロとして印字するのが、
この仕掛けの最悪の壊れ方」）。**そして 0/0 は、次に来た側へ
「消えた正本を戻せ」と言い続けます** —— 戻す先が switch だったのが 08-30 の穴でした。
**だから、条件だけを switch から切り離してここに置きます。**

**正本は `data/resume_gate.jsonl`**（閉じた根拠が1件ずつ入っています）。
**ここは条件の文だけ**を持ちます。`python scripts/eta.py --gate` で確かめること。

**外れていたら、開き直して直すこと**（止めないこと）:

    python scripts/eta.py --open-gate <番号> --evidence "<何を測って、どこと食い違ったか>"

**[!] この節に `1.` `2.` で始まる行を足さないこと。** `conditions()` は
`## Resume gate` から次の `##` までの番号つきの行を**全部 条件として数えます**。
08-30 に、字下げしていない番号を3行 足した回が、門を **6件 → 9件** に増やしました。

**覆る条件**: 6件のどれかが実測で外れたら、その件を開き直すこと。
条件そのものを増減してよい —— **ただし「止める」ためには使わないこと。**

---

## Resume gate

**この6件は、チャンネルの作りが満たしていないといけない床です。**
**「止める理由」ではありません**（`CLAUDE.md` 冒頭）。

**この一覧は写しです。正本は `data/resume_gate.jsonl`** ——
**`python scripts/eta.py --gate` を撃って確かめること**（写した瞬間に古くなります。
実際、この節は 08-30 の夜まで「2件が閉じました」のまま、
台帳では 5件 閉じていました）。

1. sensitive-topic AI persona を使わない  **← 2026-08-30 に閉じた**（根拠は `CLAUDE.md` の該当節と `data/resume_gate.jsonl`）
2. human expert を装わない                **← 2026-08-30 に閉じた**（根拠は `CLAUDE.md` の該当節と `data/resume_gate.jsonl`）
3. final videos are materially varied and demonstrate a clear original creative contribution
   **← 2026-08-30 に閉じた**（入口 `script_writer.opening_form()`／`closing_form()` の 4×4 ＋
   出口 `verify._check_frame_repeat()`。1つの型に揃う本は多くても 30.1%）
4. policy-compliant channel concept is reviewed against the current official policy
   **← 2026-08-30 夜に閉じた**（根拠は `CLAUDE.md` の該当節）**。** 公式ポリシーは
   **Last updated: July 15, 2025 のまま**で、当たる条項は (A)(B) の2つ。
   最後まで残った (B)「量そのもの」は、**13本/日 が機械の上限**として入りました
   （`batch_build.cap_by_density()`・検査 `tests/test_density_cap.py`）
5. 既存動画の扱いと新旧テーマ混在リスクを決める  **← 2026-08-30 に閉じた**
   （引っ込めない。理由は `docs/CONSTRAINTS.md` B14 ——名乗りは控え694本に 0件、
   残るのは型で、**出た本を消しても直りません**）
6. monetization path and acquisition economics are recalculated  **← 2026-08-30 に閉じた**
   （`scripts/shorts_subs.py` の解き直し。いちばん近い門を縛っているのは
   密度ではなく変換）
