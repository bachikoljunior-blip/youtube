#!/usr/bin/env python3
"""**親トリガーの正本を repo に置き、実物とのズレを見る道具**（2026-08-20 に作った）。

## なぜ要ったか

`docs/TRIGGER.md` は「自動実行の正本」と名乗っていましたが、**正本ではありません。**
実物は Claude Code の Routine 側にあり、**子がこの repo を1文字書き換えても、
発火は1秒も変わりません。** 実際 2026-08-12 には、この文書が `9 */6`、
実物が `9 */12`、親の見立てが `9 */8` と**3か所とも違って**いました。

**だから「写して合わせる」をやめます。**

- **値の正本は `docs/trigger_spec.json`**（機械が読む。`docs/TRIGGER.md` の表は人向けの写し）
- **本文の正本は `docs/trigger_body.md`**（識別子は `<<key>>` で埋める）
- **当てるのはこの道具**

## 子から書ける欄と、書けない欄（2026-08-20 に実測。**推測ではありません**）

`mcp__bf7c680d-…__update_trigger` を子の環境から実際に撃ちました。

    name              通った
    cron_expression   通った（`9 * * * *` を当て直して確認）
    enabled           同じ口（未実測）
    prompt            **弾かれた** ——
      「editing the prompt of a routine whose fires deliver into a session
        that is not your own is not available via this tool」

**つまり ③（cron）は完全に子の側にあり、①（本文）は子の側にありません。**
本文だけは、**そのトリガーが撃ち込む先のセッション本人**——つまり親——しか直せません。
親は自分の発火先が自分自身なので、**ツールの権限としては親からは通ります。**

**しかし「人手は要りません」は偽でした**（2026-08-24 に実測して外した）。
**権限が通ることと、承認なしで進むことは別です:**

    2026-08-24 12:10:35Z  親が update_trigger を撃つ
                          → SESSION_STATUS_REQUIRES_ACTION
                          → Waiting on permission: …update_trigger
                          → **オーナーが承認するまで親が止まり、次の発火が届かない**

**親は鎖の復帰口です。** そこを承認待ちにする手は、**鎖ごと止めます**
（同型の実測3件: 8/22 に18時間・8/16 に依頼1件・8/23 に引き継ぎ直後）。

**だから本文は、もう誰も直しません。**

    子   `docs/trigger_body.md` を直す（`--emit-body` が当てるべき姿を出す）
    親   **何もしない。** 実物の本文が古いままでも壊れません ——
         本文が持つのは識別子と「`docs/trigger_parent.md` を読め」だけで、
         規則は全部その文書にあり、子がいつでも書き換えられます
    人   **識別子が変わったときだけ**、`docs/FOR_OWNER.md` の窓から1回頼む
         （上振れのおまけ。計画の柱にしない ——`CLAUDE.md`「動き方の帰結 2.」）

**ここを「子が直せます」と書かないこと。** 書くと、次の子が撃って弾かれ、
弾かれたことに気づかないまま「直した」と日誌に書きます。
**「親が直せます」も書かないこと。** 書くと、次の親がそこで止まります。

**MCP はこの Python から呼べません**（呼べるのはエージェント本体だけ）。
なので分担はこうです:

    エージェント  list_triggers の返りを丸ごとファイルへ保存する
    この道具      保存された姿を正本と突き合わせ、**ズレを名指しする**
    エージェント  印字された update_trigger をそのまま撃つ

`scripts/quota.py --ingest` と同じ形です（あちらも MCP の返りを人手で運びます）。

## 使い方

    python scripts/trigger_sync.py --emit-body          # 当てるべき本文を出す
    python scripts/trigger_sync.py --ingest <file>      # list_triggers の返りを積む
    python scripts/trigger_sync.py --check              # 積んだ姿と正本を比べる（既定）
    python scripts/trigger_sync.py --plan               # 直すための MCP 呼び出しを出す

`--check` は**ズレていたら 1 で落ちます。** 古い観測（既定 24時間）も落とします ——
**「見ていない」と「合っている」は別**で、混ぜると 8/12 の3か所バラバラに戻ります。

## この設計が覆る条件

- **`update_trigger` が子から通らなくなったら** —— そのときは `--plan` の出力を
  `docs/FOR_OWNER.md` の窓に載せる側へ変えること（人手が要ると明記する）
- **親が1つでなくなったら** —— 正本を配列にして、この道具を回すこと
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "trigger_spec.json"
SEEN = ROOT / "data" / "trigger_seen.json"

# **親が byte 比較するための、差し込み口を埋め終えた本文。**
# 親は repo を触れず、`<<key>>` を埋める手も持ちません。テンプレートだけ置くと、
# 「違うかどうか」を親が目で判断することになり、**そこが 8/12 の3か所バラバラの入口**です。
# だから **1ファイル取って、受け取った本文と突き合わせるだけ**で済む形を置きます。
# `tests/test_trigger_sync.py` が、この写しの古さを落とします。
RENDERED = ROOT / "docs" / "trigger_body.rendered.md"

# 正本と突き合わせる欄。**本文（body）を必ず含めること。**
# ここから body を外すと、①（本文の移し残し）が二度と見えなくなります。
FIELDS = ("cron_expression", "enabled", "name",
          "persistent_session_id", "environment_id", "body")

# **誰が直せるか。2026-08-20 に実際に撃って分けました**（上の docstring）。
CHILD_WRITABLE = ("name", "cron_expression", "enabled")   # `update_trigger` が受ける
PARENT_ONLY = ("body",)                                   # 撃ち込む先の本人だけ
RECREATE_ONLY = ("persistent_session_id", "environment_id")  # 立て直すしかない


def load_spec(path: Path = SPEC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render_body(spec: dict, root: Path = ROOT) -> str:
    """`docs/trigger_body.md` の `<<key>>` を正本の値で埋める。

    `str.format` を使っていないのは、本文に `{` が入っても壊れないためです。
    """
    body = (root / spec["body_file"]).read_text(encoding="utf-8")
    for key, value in spec.items():
        if isinstance(value, str):
            body = body.replace(f"<<{key}>>", value)
    left = [t for t in body.split("<<")[1:] if ">>" in t]
    if left:
        raise SystemExit(f"[!] 埋まらない差し込み口が残っています: <<{left[0].split('>>')[0]}>>")
    return body.strip()


def observed(dump: dict | list, trigger_id: str) -> dict | None:
    """`list_triggers` / `update_trigger` の返りから、当該トリガーの姿を抜く。

    どちらの形でも受けます —— **返りの形は2つあり、片方しか受けないと
    「積んだつもりで積めていない」回が出ます。**
    """
    rows: list[dict] = []
    if isinstance(dump, list):
        rows = [r for r in dump if isinstance(r, dict)]
    elif isinstance(dump, dict):
        if isinstance(dump.get("data"), list):
            rows = [r for r in dump["data"] if isinstance(r, dict)]
        elif isinstance(dump.get("trigger"), dict):
            rows = [dump["trigger"]]
        elif "id" in dump:
            rows = [dump]
    for row in rows:
        if row.get("id") != trigger_id:
            continue
        ccr = (row.get("job_config") or {}).get("ccr") or {}
        events = ccr.get("events") or []
        body = ""
        if events:
            body = (((events[0].get("data") or {}).get("message") or {})
                    .get("content") or "")
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "cron_expression": row.get("cron_expression"),
            "enabled": bool(row.get("enabled", False)),
            "persistent_session_id": row.get("persistent_session_id"),
            "environment_id": ccr.get("environment_id"),
            "body": body.strip(),
            "next_run_at": row.get("next_run_at"),
            "last_fired_at": row.get("last_fired_at"),
        }
    return None


def spec_fingerprint(spec: dict, root: Path = ROOT) -> str:
    """正本の「比べる側」だけを縮めた指紋。

    **観測より後に正本が変わったかを見分けるためだけ**のものです。
    ファイルの更新時刻では見分けられません —— このリポジトリは回ごとに
    clone し直されるので、**全ファイルの mtime がコンテナの起動時刻**になり、
    「いつも観測より新しい」になってしまいます。
    """
    want = {k: spec[k] for k in FIELDS if k in spec}
    want["body"] = render_body(spec, root)
    blob = json.dumps(want, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def ingest(path: Path, spec: dict, seen_path: Path = SEEN) -> dict:
    dump = json.loads(Path(path).read_text(encoding="utf-8"))
    got = observed(dump, spec["trigger_id"])
    if got is None:
        raise SystemExit(
            f"[!] 保存された返りに {spec['trigger_id']} がいません。\n"
            "    `list_triggers` の返りを**まるごと**保存すること"
            "（limit を絞ると落ちます）。")
    got["ingested_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # 観測したその時の正本の姿。**後で正本だけが変わったかを見分ける唯一の手がかり。**
    got["spec_fingerprint"] = spec_fingerprint(spec)
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    seen_path.write_text(json.dumps(got, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    return got


def load_seen(seen_path: Path = SEEN) -> dict | None:
    if not seen_path.exists():
        return None
    try:
        return json.loads(seen_path.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None


def _age_hours(seen: dict) -> float | None:
    raw = seen.get("ingested_at")
    if not raw:
        return None
    try:
        then = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600.0


def diff(spec: dict, seen: dict | None, root: Path = ROOT) -> list[str]:
    """正本と、積んだ姿の食い違いを1行ずつ返す。空なら一致。"""
    if seen is None:
        return ["**実物を一度も見ていません。** `list_triggers` の返りを保存して "
                "`--ingest <file>` を打つこと"]
    want = {k: spec[k] for k in FIELDS if k in spec}
    want["body"] = render_body(spec, root)
    out: list[str] = []
    for key in FIELDS:
        if key not in want:
            continue
        a, b = want[key], seen.get(key)
        if a == b:
            continue
        if key == "body":
            # **「当てること」と言わないこと**（2026-09-01 08:2x に直した）。
            # ここは長らく「`--emit-body` を当てること」と印字していましたが、
            # **`--emit-body` は当てません。当てるべき姿を印字するだけ**です。
            # 実際に当てるには `update_trigger` が要り、**この repo は
            # その道を意図して閉じてあります**:
            #
            #   親が撃つ  2026-08-24 12:10Z 実測 → `SESSION_STATUS_REQUIRES_ACTION`
            #             ＝ 承認待ちで親が止まり、**そこへは次の発火も届きません**
            #             （`docs/trigger_parent.md`「トリガー本文の正本」——
            #              この節はそれを理由に**空にしてあります**）
            #   子が撃つ  2026-08-20 と 08-24 の2回、道具ごと弾かれています
            #             （"editing the prompt of a routine whose fires deliver
            #               into a session that is not your own is not available"）
            #
            # **つまり、この行は「誰にもできないこと」を毎周 命じていました。**
            # 同じ文書の中で先に読まれる側が禁を破る形で、`trigger_parent.md` が
            # 「先に読まれる側が勝つので、禁のほうは効きません」と書いている、
            # まさにその形です。**鳴らすのはよい。命じるのが誤りでした。**
            #
            # **古いままで何も壊れません** —— 本文が持っているのは識別子と
            # 「`docs/trigger_parent.md` を読め」だけで、**規則は全部 repo にあり、
            # 子がいつでも書き換えられます。** 壊れるのは識別子が変わったときだけ。
            #
            # **覆る条件**: `update_trigger` が承認待ちにならずに通るように
            # なったら（`docs/trigger_parent.md` の同じ節の覆る条件と対）、
            # ここは「当てること」に戻してよい。
            out.append(f"body: 本文が正本と違います（正本 {len(a)}字 / 実物 "
                       f"{len(b or '')}字）。**当て直さないこと** —— "
                       "`update_trigger` は親だと承認待ちで鎖ごと止まり"
                       "（2026-08-24 実測）、子だと道具ごと弾かれます。"
                       "本文が運ぶのは識別子と『`docs/trigger_parent.md` を読め』"
                       "だけなので、**古くても壊れません**"
                       "（`docs/trigger_parent.md`「トリガー本文の正本」）。"
                       "**識別子（`trigger_id` / `persistent_session_id` / "
                       "`environment_id`）がズレている行が上に無いかだけ見ること**")
        else:
            out.append(f"{key}: 正本 `{a}` ↔ 実物 `{b}`")
    return out


def stale(spec: dict, seen: dict | None) -> float | None:
    """観測が古ければ経過時間（時間）を返す。新しければ None。"""
    if seen is None:
        return None
    age = _age_hours(seen)
    limit = float(spec.get("stale_hours", 24))
    return age if age is not None and age > limit else None


def render(spec: dict, seen: dict | None, root: Path = ROOT) -> tuple[str, bool]:
    """`status.py` から呼ぶ表示。（本文, ズレているか）を返す。"""
    lines = ["\n=== 親トリガー（正本 `docs/trigger_spec.json` ↔ 実物）==="]
    gaps = diff(spec, seen, root)
    old = stale(spec, seen)
    if not gaps and old is None:
        age = _age_hours(seen or {})
        when = f"{age:.1f}時間前" if age is not None else "?"
        lines.append(f"  一致（{when}に観測）: `{spec['cron_expression']}` "
                     f"／ enabled={spec['enabled']}")
        return "\n".join(lines), False
    if seen is not None and seen.get("spec_fingerprint") not in (
            None, spec_fingerprint(spec, root)):
        lines.append(
            "  [!] **正本がこの観測より後に変わっています。** 下のズレは、"
            "実物が違うのではなく**観測が古い**だけかもしれません —— "
            "前の回が `update_trigger` を当てたのに積み直していない場合がこれです"
            "（2026-08-21 に実測。1日21回→19回を当てた回が積み直さず、"
            "次の回が「実物は21回のまま」と読んだ）。"
            "\n      **まず `list_triggers` を保存して `--ingest` を打つこと。**")
    for gap in gaps:
        lines.append(f"  [!] {gap}")
    if old is not None:
        lines.append(f"  [!] **観測が {old:.0f}時間前です**（上限 "
                     f"{spec.get('stale_hours', 24)}時間）。**合っている証拠が古い** ——"
                     "「見ていない」と「合っている」は別です")
    lines.append("  直す: `python scripts/trigger_sync.py --plan`"
                 "（cron/name/enabled は**子から通ります**。**本文は親しか当てられません** ——"
                 "2026-08-20 に撃って実測）")
    return "\n".join(lines), True


def plan(spec: dict, seen: dict | None, root: Path = ROOT) -> str:
    """**誰が撃てるかで分けて出す。**

    分けない版を作りかけて捨てました —— 全部まとめて `update_trigger` の引数に
    すると、**`prompt` が混ざった瞬間に呼び全体が弾かれます**（2026-08-20 実測）。
    cron だけ直せた回まで「直せなかった」になります。
    """
    gaps = diff(spec, seen, root)
    if not gaps:
        return "ズレはありません。撃つものはありません。"
    hit = {g.split(":")[0] for g in gaps}
    out: list[str] = []

    mine = {k: spec[k] for k in CHILD_WRITABLE if k in hit}
    if mine:
        out += ["## 子が撃てるもの（いますぐ）", "",
                "mcp__bf7c680d-5fdc-5ef4-b4a0-abadb619bf0a__update_trigger:",
                json.dumps({"trigger_id": spec["trigger_id"], **mine},
                           ensure_ascii=False, indent=2), ""]

    if hit & set(PARENT_ONLY) or seen is None:
        out += ["## 本文（**子は撃てません。親も撃たないこと**）", "",
                "子がやること: `docs/trigger_body.md` を直して push する（済んでいれば何もしない）。",
                "親がやること: **何もしない。**",
                "",
                "**親に `update_trigger` を撃たせないこと**（2026-08-24 に外した）。",
                "撃つと承認待ちで親が止まり、**次の発火が届かず鎖ごと死にます**",
                "（12:10:35Z に実測。同型の死が 8/22・8/16・8/23 にも1件ずつ）。",
                "実物の本文が古くても壊れません —— 本文が持つのは識別子と",
                "「`docs/trigger_parent.md` を読め」だけで、規則は全部その文書にあります。",
                "**識別子が変わったときだけ**、`docs/FOR_OWNER.md` の窓でオーナーに1回頼むこと。",
                "当てるべき本文は `python scripts/trigger_sync.py --emit-body`。", ""]

    stuck = hit & set(RECREATE_ONLY)
    if stuck:
        out += ["## `update_trigger` では直せないもの", "",
                *[f"  - {g}" for g in gaps if g.split(':')[0] in stuck],
                "  → `create_trigger` で立て直し、古いほうを `delete_trigger` で消すこと。",
                "    **承認は要りません**（`docs/trigger_parent.md` 末尾）。", ""]
    return "\n".join(out).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--emit-body", action="store_true", help="当てるべき本文を出す")
    ap.add_argument("--write-rendered", action="store_true",
                    help="親が byte 比較する写し（docs/trigger_body.rendered.md）を書き直す")
    ap.add_argument("--ingest", metavar="FILE", help="list_triggers の返りを積む")
    ap.add_argument("--check", action="store_true", help="正本と実物を比べる（既定）")
    ap.add_argument("--plan", action="store_true", help="直すための MCP 呼び出しを出す")
    args = ap.parse_args(argv)

    spec = load_spec()
    if args.emit_body:
        print(render_body(spec))
        return 0
    if args.write_rendered:
        RENDERED.write_text(render_body(spec) + "\n", encoding="utf-8")
        print(f"書きました: {RENDERED.relative_to(ROOT)}")
        return 0
    seen = ingest(Path(args.ingest), spec) if args.ingest else load_seen()
    if args.plan:
        print(plan(spec, seen))
        return 0
    text, drifted = render(spec, seen)
    print(text)
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
