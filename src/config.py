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


class _StrictLoader(yaml.SafeLoader):
    """**同じ鍵を2回書いたら止める。**

    YAML は既定で**あとの値が黙って勝つ。** 2026-08-09、`tenshoku-nenshu` に
    `calc_sections` が2か所あり、上に書いたほうが捨てられた。
    エラーも警告も出ないので、**渡す表を絞ったつもりで絞れていなかった。**
    気づいたのは、出力を見て「指定した節が1つも通っていない」と分かったから。

    このリポジトリで一番高い間違いは、いつも**静かに通るもの**です。
    """


def _no_duplicates(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None,
                f"鍵 `{key}` が同じ場所に2回あります。**あとの値が黙って勝つので、"
                "先に書いたほうは無かったことになります。** 片方を消してください",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates
)


def load_channel() -> dict:
    return yaml.load((CONFIG_DIR / "channel.yaml").read_text(encoding="utf-8"), _StrictLoader)


def load_topics() -> dict:
    return yaml.load((CONFIG_DIR / "topics.yaml").read_text(encoding="utf-8"), _StrictLoader)


def save_topics(data: dict) -> None:
    (CONFIG_DIR / "topics.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def dry_run() -> bool:
    return env("DRY_RUN", required=False, default="false").lower() in ("1", "true", "yes")
