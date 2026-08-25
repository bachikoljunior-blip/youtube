"""Claude Code CLI をヘッドレスで叩いて JSON を受け取る。

Anthropic API（従量課金）は使わない。サブスクリプションの OAuth トークンで
`claude -p` を実行し、思考はそのセッション内で完結させる。

CLI の JSON 出力は「スキーマで保証された構造化出力」ではないので、
取り出し・検証・失敗時の差し戻しをこちらで持つ。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

CLI = "claude"
DEFAULT_TIMEOUT = 1800  # 秒。opus で長文を書かせると数分かかることがある


class ClaudeCliError(RuntimeError):
    pass


def _binary() -> str:
    path = shutil.which(CLI)
    if not path:
        raise ClaudeCliError(
            "claude コマンドが見つかりません。`npm install -g @anthropic-ai/claude-code` を実行してください。"
        )
    return path


_CLI_CWD: Path | None = None


def _cli_cwd() -> Path:
    """`claude -p` を、**このプロセス専用の作業ディレクトリ**で走らせる。

    ## なぜ要るか（2026-08-15 20:0x に実測で見つけた。**混線していました**）

    `--jobs 5` で10本まとめて作ったら **3本しか通りませんでした**（`--jobs 3` では
    6本中5本）。落ちた本のログを読んだら、落ちていたのは並列の負荷ではなく
    **中身の取り違え**でした。

        テーマ s-shitsugyo-60dai-kaiko-1nen-60nichi（失業給付・60代）
        → 出てきた題は「**同居特別障害者控除** 5年で179万6500円」

    その題は、**同時に走っていた** `s-kojo-zeiritsu40-dokyo` の出力です
    （向こうの題は「同居特別障害者控除は5年で179万6500円」で、助詞1つしか違わない）。
    4本を同時に走らせて再現し、落ちた2本のうち1本がこれでした。

    `claude` の CLI はセッションを **作業ディレクトリごと**に持ちます。
    `ask()` は形式が崩れると `--resume <session>` で同じ会話を続けるので、
    **同じディレクトリで並走すると、やり直しが隣の会話に着くことがあります。**
    実際、混ざったのは**やり直しに入った本**でした（ログに「2回目」「3回目」）。

    **これは「落ちた」より悪い種類の欠陥です。** 今回は `verify.py` の主語検査が
    たまたま止めましたが（画面に「失業」が無い）、**取り違えた中身が検査を
    すり抜ければ、題と中身の合わない動画がそのまま公開されます。**
    誤情報であり、収益化の条件そのものに当たります。

    直し方は `scripts/critique_run.py` が独立性のために既にやっていることと同じで、
    **cwd を分ける**こと。プロセスごとに1つ作って使い回します
    （やり直しは同じプロセスなので、`--resume` は同じ場所を見ます）。
    リポジトリの外に出るので、`CLAUDE.md` が台本のプロンプトに混ざらない
    という効き目もあります（台本を書く側に目的も合格基準も要りません）。
    """
    global _CLI_CWD
    if _CLI_CWD is None or not _CLI_CWD.exists():
        _CLI_CWD = Path(tempfile.mkdtemp(prefix=f"claude-cli-{os.getpid()}-"))
    return _CLI_CWD


def _child_env() -> dict[str, str]:
    """サブスク認証を確実に使わせる。"""
    env = dict(os.environ)
    # ANTHROPIC_API_KEY が残っていると CLI がそちらを優先し、従量課金になる
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    if not env.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        # ローカルでは ~/.claude の資格情報が使われるので、CI でだけ必須
        if env.get("CI"):
            raise ClaudeCliError(
                "CLAUDE_CODE_OAUTH_TOKEN が未設定です。"
                "手元で `claude setup-token` を実行し、GitHub の secrets に登録してください。"
            )
    env["CLAUDE_CODE_NONINTERACTIVE"] = "1"
    # **フックを子プロセスに効かせない。**
    # 2026-08-07、`goal_reminder.sh`（UserPromptSubmit フック）の注入が
    # 台本生成の子プロセスにも入り、**台本ではなく「確認項目への回答」を
    # 返してきた**（JSON が含まれず生成失敗）。
    # 恒久指示を思い出すのは判断する側の話で、台本を書く側には要らない。
    # `scripts/goal_reminder.sh` がこの変数を見て黙る。
    env["YOUTUBE_PIPELINE_CHILD"] = "1"
    return env


def _parse_envelope(stdout: str) -> tuple[str, str]:
    """CLI の --output-format json を (本文, session_id) に分解する。"""
    try:
        payload: Any = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeCliError(f"CLI の出力を JSON として読めません: {stdout[:400]}") from exc

    # 版によって単一オブジェクトだったりメッセージ配列だったりする
    if isinstance(payload, list):
        results = [m for m in payload if isinstance(m, dict) and m.get("type") == "result"]
        if not results:
            raise ClaudeCliError(f"result メッセージがありません: {stdout[:400]}")
        payload = results[-1]

    if payload.get("is_error"):
        raise ClaudeCliError(f"CLI がエラーを返しました: {payload.get('result', '')[:400]}")

    body = payload.get("result")
    if not isinstance(body, str):
        raise ClaudeCliError(f"result が文字列ではありません: {str(payload)[:400]}")
    return body, str(payload.get("session_id", ""))


def _extract_json(text: str) -> str:
    """本文から JSON 部分だけを取り出す。前置きやコードフェンスがあっても拾う。"""
    fence = text.find("```")
    if fence != -1:
        start = text.find("\n", fence)
        end = text.find("```", start + 1)
        if start != -1 and end != -1:
            inner = text[start + 1 : end].strip()
            if inner.startswith("{"):
                return inner

    start = text.find("{")
    if start == -1:
        raise ClaudeCliError(f"JSON が含まれていません: {text[:400]}")

    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ClaudeCliError(f"JSON が閉じていません: {text[start:start + 400]}")


def _invoke(prompt: str, model: str, resume: str | None, timeout: int) -> tuple[str, str]:
    args = [_binary(), "-p", prompt, "--output-format", "json", "--model", model]
    if resume:
        args += ["--resume", resume]

    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            env=_child_env(), cwd=str(_cli_cwd()),
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCliError(f"claude が {timeout} 秒で応答しませんでした") from exc

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip()[-800:]
        raise ClaudeCliError(f"claude が異常終了しました (exit {proc.returncode})\n{tail}")

    return _parse_envelope(proc.stdout)


JSON_RULES = """
出力の決まり:
- ツールは一切使わないでください。ファイルも読まないでください。
- 説明・前置き・後書きを書かず、JSON オブジェクトだけを出力してください。
- 下のスキーマのキーを過不足なく含めてください。
"""


def ask(
    model_cls: type[T],
    prompt: str,
    *,
    model: str,
    max_attempts: int = 3,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[T, str]:
    """プロンプトを投げて、pydantic モデルとして検証済みの結果と session_id を返す。

    形式が崩れたら、同じセッションを resume して直させる。
    """
    schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False, indent=2)
    full = f"{prompt}\n{JSON_RULES}\nJSON スキーマ:\n{schema}\n"

    session: str | None = None
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        body, session_id = _invoke(
            full if attempt == 1 else last_error, model, session, timeout
        )
        session = session_id or session
        try:
            return model_cls.model_validate(json.loads(_extract_json(body))), session or ""
        except (ClaudeCliError, json.JSONDecodeError, ValidationError) as exc:
            print(f"[claude] 試行{attempt}: 出力の形式が不正 — {str(exc)[:200]}")
            last_error = (
                "直前の出力がスキーマに合っていませんでした。次のエラーを直して、"
                f"JSON オブジェクトだけをもう一度出力してください。\nエラー: {str(exc)[:600]}"
            )
            if attempt == max_attempts:
                raise ClaudeCliError(f"{max_attempts}回試しても正しい JSON が得られませんでした") from exc

    raise ClaudeCliError("unreachable")


def follow_up(model_cls: type[T], session_id: str, prompt: str, *, model: str,
              max_attempts: int = 2, timeout: int = DEFAULT_TIMEOUT) -> tuple[T, str]:
    """同じセッションを続けて、もう一度 JSON を出させる。"""
    session = session_id
    last = prompt
    for attempt in range(1, max_attempts + 1):
        body, new_session = _invoke(last, model, session, timeout)
        session = new_session or session
        try:
            return model_cls.model_validate(json.loads(_extract_json(body))), session
        except (ClaudeCliError, json.JSONDecodeError, ValidationError) as exc:
            print(f"[claude] 追記試行{attempt}: 形式が不正 — {str(exc)[:200]}")
            last = (
                "出力がスキーマに合っていません。次のエラーを直して JSON だけ出し直してください。\n"
                f"エラー: {str(exc)[:600]}"
            )
            if attempt == max_attempts:
                raise
    raise ClaudeCliError("unreachable")
