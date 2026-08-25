#!/usr/bin/env bash
# レンダリングに要るものを入れる。
#
# 常駐セッションのコンテナは作り直されることがあり、そのとき ffmpeg も
# 音声合成も消えている。ブラウザだけは最初から入っている
# （PLAYWRIGHT_BROWSERS_PATH が設定済み）。
#
# 何度実行しても安全。入っているものは飛ばす。
set -euo pipefail
cd "$(dirname "$0")/.."

need() { ! command -v "$1" >/dev/null 2>&1; }

if need ffmpeg || need open_jtalk; then
  echo "システム側の依存を入れています ..."
  apt-get update -qq
  # ffmpeg: 同梱のものは VP8 しか出せず音声コーデックが無い。apt のものが要る。
  # open-jtalk 一式: 日本語ナレーション。APIキーも課金設定も要らない。
  # fonts-noto-cjk: 字幕・図解・サムネの日本語。無いと豆腐になる。
  apt-get install -y -qq ffmpeg open-jtalk open-jtalk-mecab-naist-jdic \
    hts-voice-nitech-jp-atr503-m001 fonts-noto-cjk fonts-noto-cjk-extra
fi

command -v ffmpeg     >/dev/null || { echo "ffmpeg が入りませんでした"; exit 1; }
command -v open_jtalk >/dev/null || { echo "open_jtalk が入りませんでした"; exit 1; }

# ディストリの cryptography が壊れていて google-auth の import が panic することがある。
# cffi を入れ直すと直る。先に入れておく。
python3 -c "import _cffi_backend" 2>/dev/null || pip install -q --upgrade cffi

# ディストリが入れたパッケージは pip から消せない（RECORD が無い）ので、
# 上書きが要るときは --ignore-installed で新しいほうを上に置く。
pip install -q -r requirements.txt \
  || pip install -q --ignore-installed -r requirements.txt

# **入ったかどうかは、実際に import して見ること**（2026-08-21 に踏んだ）。
# 上の `pip install -r requirements.txt` は**成功しても**、ディストリの
# `python3-cryptography 41.0.7` が /usr/lib/python3/dist-packages に残っていると
# `from google.oauth2.credentials import Credentials` が pyo3 の panic で落ちます
# （`ModuleNotFoundError: No module named '_cffi_backend'` → `PanicException`）。
# 成功しているので上の `||` 側には落ちず、**回の最初の eta.py で初めて分かります。**
# `--upgrade` は `Cannot uninstall cryptography 41.0.7, RECORD file not found` で止まるので、
# **剥がさずに上へ置く `--ignore-installed` でないと直りません。**
_import_ok='from google.oauth2.credentials import Credentials
import googleapiclient.discovery, yaml, pydantic, numpy, pytest'
python3 -c "$_import_ok" 2>/dev/null \
  || pip install -q --ignore-installed cffi cryptography
python3 -c "$_import_ok" 2>/dev/null \
  || { echo "Python 側が揃いませんでした（google-auth の import が通りません）"; exit 1; }

# 同梱の Chromium は playwright の期待するビルド番号と一致しないことがある。
# その場合は実体を直接指す。src/visuals.py が PLAYWRIGHT_CHROMIUM_PATH を見る。
if ! python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p: p.chromium.launch().close()
" 2>/dev/null; then
  found="$(find "${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}" -maxdepth 3 \
            -name chrome -type f 2>/dev/null | head -1)"
  if [ -n "$found" ]; then
    export PLAYWRIGHT_CHROMIUM_PATH="$found"
    echo "PLAYWRIGHT_CHROMIUM_PATH=$found"
    echo "export PLAYWRIGHT_CHROMIUM_PATH=$found" >> ~/.bashrc
  else
    python3 -m playwright install chromium
  fi
fi

echo "準備完了: $(ffmpeg -version | head -1 | cut -d' ' -f1-3), open_jtalk, playwright"
