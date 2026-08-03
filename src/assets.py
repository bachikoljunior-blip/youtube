"""Pexels から背景素材を取ってくる。

Pexels のライセンスは商用利用可・クレジット任意。任意でも説明欄に入れておく。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from . import config

VIDEO_SEARCH = "https://api.pexels.com/videos/search"
PHOTO_SEARCH = "https://api.pexels.com/v1/search"


@dataclass
class Asset:
    path: Path
    is_video: bool
    credit: str


class AssetFetcher:
    def __init__(self, out_dir: Path):
        self.key = config.env("PEXELS_API_KEY")
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.used_ids: set[int] = set()
        self.credits: list[str] = []
        self._fallback: Asset | None = None

    def _get(self, url: str, query: str, per_page: int = 12) -> list[dict]:
        response = requests.get(
            url,
            headers={"Authorization": self.key},
            params={"query": query, "per_page": per_page, "orientation": "landscape"},
            timeout=60,
        )
        if response.status_code != 200:
            print(f"[assets] 検索失敗 ({response.status_code}) query={query!r}")
            return []
        data = response.json()
        return data.get("videos") or data.get("photos") or []

    def _download(self, url: str, dest: Path) -> None:
        with requests.get(url, stream=True, timeout=180) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_content(1 << 16):
                    fh.write(chunk)

    def _pick_video_file(self, video: dict) -> str | None:
        files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"]
        if not files:
            return None
        # 1920幅以上で一番小さいもの。大きすぎるとダウンロードもエンコードも遅い。
        wide = sorted((f for f in files if (f.get("width") or 0) >= 1920), key=lambda f: f["width"])
        chosen = wide[0] if wide else max(files, key=lambda f: f.get("width") or 0)
        return chosen.get("link")

    def fetch(self, query: str, index: int) -> Asset:
        """1カットぶんの素材。取れなければ直前の素材を使い回す。"""
        for candidate in self._get(VIDEO_SEARCH, query):
            if candidate["id"] in self.used_ids:
                continue
            link = self._pick_video_file(candidate)
            if not link:
                continue
            dest = self.out_dir / f"bg_{index:03d}.mp4"
            try:
                self._download(link, dest)
            except Exception as exc:  # ネットワーク都合はスキップして次の候補へ
                print(f"[assets] ダウンロード失敗: {exc}")
                continue
            self.used_ids.add(candidate["id"])
            credit = candidate.get("user", {}).get("name", "Pexels")
            self.credits.append(credit)
            asset = Asset(dest, True, credit)
            self._fallback = asset
            return asset

        for candidate in self._get(PHOTO_SEARCH, query):
            if candidate["id"] in self.used_ids:
                continue
            link = candidate.get("src", {}).get("large2x") or candidate.get("src", {}).get("original")
            if not link:
                continue
            dest = self.out_dir / f"bg_{index:03d}.jpg"
            try:
                self._download(link, dest)
            except Exception as exc:
                print(f"[assets] ダウンロード失敗: {exc}")
                continue
            self.used_ids.add(candidate["id"])
            credit = candidate.get("photographer", "Pexels")
            self.credits.append(credit)
            asset = Asset(dest, False, credit)
            self._fallback = asset
            return asset

        if self._fallback is not None:
            print(f"[assets] query={query!r} が0件。直前の素材を再利用します。")
            return self._fallback
        raise RuntimeError(f"素材が1つも取得できませんでした（最初のクエリ: {query!r}）")

    def credit_line(self) -> str:
        unique = sorted(set(self.credits))
        if not unique:
            return ""
        return "映像素材: Pexels（" + "、".join(unique[:12]) + " ほか）"
