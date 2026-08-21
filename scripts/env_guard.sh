#!/usr/bin/env bash
# **コンテナが作り直された回を、回の最初に自分で直す。**
#
# 2026-08-21 11:1x の回は、いちばん最初の `python scripts/eta.py` が
# `ModuleNotFoundError: No module named 'googleapiclient'` で落ち、
# `scripts/status.py` は `_cffi_backend` が無く pyo3 が panic しました。
# **どちらも「この回は測れません」と出て、回は止まりかけています。**
#
# `scripts/setup.sh` は直せる中身を持っていましたが、**誰も呼びません** ——
# セッションの開始で走るものが1つも無く、踏んだ回が毎回、症状から辿ります。
# これは SessionStart フックとして `.claude/settings.json` から呼ばれます。
#
# **健康なら1秒未満で終わります**（import を1回するだけ）。apt は叩きません
# （フックの制限時間に入らないので、足りなければ `setup.sh` を促すだけ）。
set -uo pipefail
cd "$(dirname "$0")/.."

PY_OK='from google.oauth2.credentials import Credentials
import googleapiclient.discovery, yaml, pydantic, numpy, pytest'

if python3 -c "$PY_OK" 2>/dev/null; then
  :
else
  echo "[env_guard] Python 側が欠けています。入れ直します（1〜2分）..." >&2
  pip install -q -r requirements.txt >&2 2>&1
  # **ディストリの cryptography は pip から剥がせません**（RECORD が無い）。
  # `--upgrade` は `Cannot uninstall cryptography 41.0.7` で止まるので、
  # **`--ignore-installed` で新しいほうを上に置きます**（2026-08-21 に実測）。
  python3 -c "$PY_OK" 2>/dev/null \
    || pip install -q --ignore-installed cffi cryptography >&2 2>&1
  if python3 -c "$PY_OK" 2>/dev/null; then
    echo "[env_guard] **直りました。**この回はそのまま進めます。" >&2
  else
    echo "[env_guard] **直りませんでした。**手で: pip install -r requirements.txt && pip install --ignore-installed cffi cryptography" >&2
  fi
fi

# レンダリングの側は apt が要るので、ここでは**言うだけ**にします。
missing=""
command -v ffmpeg     >/dev/null 2>&1 || missing="$missing ffmpeg"
command -v open_jtalk >/dev/null 2>&1 || missing="$missing open_jtalk"
if [ -n "$missing" ]; then
  echo '[env_guard] **動画が作れません。** **bash scripts/setup.sh を先に走らせること**（apt で2〜3分）。足りないもの:'"\$missing" >&2
fi
exit 0
