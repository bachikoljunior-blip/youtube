"""設定と環境変数のロード。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
BUILD_DIR = ROOT / "build"


def _load_dotenv() -> None:
    """.env があれば読む。GitHub Actions では secrets が既に env にあるので何もしない。"""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def env(name: str, *, required: bool = True, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        if required:
            raise RuntimeError(
                f"環境変数 {name} が未設定です。.env か GitHub の Repository secrets に登録してください。"
            )
        return default
    return value


def load_channel() -> dict:
    return yaml.safe_load((CONFIG_DIR / "channel.yaml").read_text(encoding="utf-8"))


def load_topics() -> dict:
    return yaml.safe_load((CONFIG_DIR / "topics.yaml").read_text(encoding="utf-8"))


def save_topics(data: dict) -> None:
    (CONFIG_DIR / "topics.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def dry_run() -> bool:
    return env("DRY_RUN", required=False, default="false").lower() in ("1", "true", "yes")
