"""**GPT Image 2.0 の絵を、注文して・受け取って・動画の中で使う。**

    python -m src.image_orders                 # いまの注文と、届いている絵
    python -m src.image_orders --order <topic> # その本のぶんを注文する（API 0単位）

## なぜ要るか（2026-09-03 21:2x に足した）

オーナー原文（2026-09-03 19:3x / 20:0x JST）:

    「ちゃっとgpt Worksのセッションで毎時実行をさせるプロンプトを書いて。
      役割はリポジトリ経由であなたの指示を読みあなたが使う画像を
      gptimages2.0で生成して、リポジトリに送ること。」
    **「動画内で使う画像はチャットgptのimages2.0を活用して」**

受け渡しの約束は `docs/IMAGE_ORDERS.md` に書かれ、`assets/images/` と
`data/image_orders/` も切ってありました。**ところが、この回に数えたら**:

    data/image_orders/ の注文票        **0件**
    assets/images/ の絵                **0件**（`.gitkeep` だけ）
    `image_orders` を書くコード         **0か所**
    `assets/images` を読むコード        **0か所**

**＝ 約束は文書だけで、機械の側は1行もありませんでした。**
この repo でいちばん多い壊れ方（**言っている所と、している所が別**）の、
そのままの形です。外の毎時セッションは**注文が置かれない限り何も焼けない**ので、
このままでは絵は永久に1枚も来ません。

## ここが持つのは2つだけ

    place()    注文票を置く（**冪等**。同じ id なら上書きしない）
    image_for() 届いている絵を返す。**無ければ None**

**`image_for()` は待ちません。** `docs/IMAGE_ORDERS.md` の
「来ていなければ、**待たずに** `src/visuals.py` の自前の図解で焼くこと（**止めない**）」
が、そのまま `None` です。**ここに「待つ」を足さないこと** ——
絵1枚のために本を1本 落とすほうが、はるかに高くつきます（CLAUDE.md の4）。

## **字は入れさせません**

`docs/IMAGE_ORDERS.md`:「日本語の見出しは `src/thumbnail.py` が後から載せます
（生成画像の中の日本語は崩れる）」。だから `prompt` には必ず
`AVOID` を添えます（`place()` が自動で足すので、呼ぶ側は書かなくてよい）。

## 覆る条件

* オーナーが「絵は要らない」と言ったとき —— そのときは `place()` の呼び出しを外す
  （**この module は消さない**。受け取る側は残しておいてよい）
* 外の毎時セッションが止まったとき —— `image_for()` が `None` を返し続けるだけで、
  **本は今までどおり焼けます**。止まったことに気づく口は
  `python -m src.image_orders`（`pending` の齢が出ます）
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDERS = ROOT / "data" / "image_orders"
IMAGES = ROOT / "assets" / "images"
RECEIPTS = ROOT / "data" / "image_orders.jsonl"

JST = timezone(timedelta(hours=9))

#: 注文票が使ってよい id の形（`docs/IMAGE_ORDERS.md`: 英数と `-` のみ）。
ID_RE = re.compile(r"^[A-Za-z0-9-]{1,80}$")

#: **生成画像に入れさせないもの。** 呼ぶ側に書かせない（忘れると崩れた日本語が焼き付く）。
AVOID = "文字・ロゴ・実在の人物・透かし・図表・グラフ"

#: 絵が要る本の締切から、これだけ前に注文を置くこと（`docs/IMAGE_ORDERS.md`）。
#: **毎時のセッションが拾うまで最大1時間**かかるので、1時間では足りません。
LEAD = timedelta(hours=2)

#: 受け取れる拡張子。**この順で探します**（`out` の指定と食い違っても拾えるように）。
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _now() -> datetime:
    return datetime.now(JST)


def slug(text: str) -> str:
    """id に使える形へ。**日付や題材から作るので、同じ本なら同じ id になります**
    （＝ `place()` が冪等になる）。"""
    out = re.sub(r"[^A-Za-z0-9-]+", "-", str(text)).strip("-")
    return out[:80] or "x"


def order_id(topic_id: str, kind: str = "bg", day: str | None = None) -> str:
    """**同じ本・同じ用途なら、何度 呼んでも同じ id。**

    焼き直し（`scripts/ahead_sweep.py` の rebake）で id が変わると、
    **同じ絵を毎回 注文し直す**ことになり、外のセッションの1時間が溶けます。
    """
    head = day or _now().strftime("%Y-%m-%d")
    return slug(f"{head}-{topic_id}-{kind}")


def path_of(oid: str) -> Path:
    return ORDERS / f"{oid}.json"


def place(topic_id: str, prompt: str, *, kind: str = "bg",
          size: str = "1920x1080", fmt: str = "jpg",
          for_text: str = "", day: str | None = None,
          due: datetime | None = None) -> dict:
    """注文票を1枚 置く。**冪等** —— 既に在れば、そのまま返します。

    返り: 注文票の中身（`already` が真なら、この回は書いていません）。

    **`due` を渡すと、締切まで `LEAD`（2時間）を切っているかを見て
    `late` を立てます。** 止めはしません —— 判断は呼ぶ側です
    （`docs/IMAGE_ORDERS.md`「来ていなければ待たずに自前の図解で焼く」）。
    """
    oid = order_id(topic_id, kind, day)
    if not ID_RE.match(oid):                                # noqa: SIM102
        raise ValueError(f"id の形が不正です: {oid!r}")
    p = path_of(oid)
    if p.exists():
        try:
            got = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            got = {"id": oid}
        got["already"] = True
        return got

    now = _now()
    row = {
        "id": oid,
        "asked_at": now.isoformat(timespec="seconds"),
        "for": for_text or f"{topic_id} の{kind}",
        "prompt": str(prompt).strip(),
        "avoid": AVOID,
        "size": size,
        "format": fmt,
        "out": f"assets/images/{oid}.{fmt}",
        "status": "pending",
    }
    if due is not None:
        row["due"] = due.isoformat(timespec="seconds")
        row["late"] = bool(due - now < LEAD)
    ORDERS.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(row, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    row["already"] = False
    return row


def image_for(topic_id: str, *, kind: str = "bg", day: str | None = None) -> Path | None:
    """**届いている絵。無ければ `None`。**

    **ここで待たないこと**（module の docstring）。`None` は異常ではなく、
    「まだ来ていない ＝ 自前の図解で焼く」という**正常な合図**です。
    """
    return delivered(order_id(topic_id, kind, day))


def delivered(oid: str) -> Path | None:
    """id に対して、実際にファイルが在るか。**受領の行ではなく、実物を見ます** ——
    `data/image_orders.jsonl` に `done` と書いてあってもファイルが無いことは在り得ます
    （push が途中で落ちた場合）。**実物が正本です。**"""
    for ext in EXTS:
        p = IMAGES / f"{oid}{ext}"
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def data_uri(path: Path) -> str:
    """`visuals` の HTML へ差し込む形。**`set_content()` には base URL が無いので、
    `file://` や相対パスでは読めません**（読めないまま無地で焼けて、気づけない）。"""
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def pending(older_than: timedelta | None = None) -> list[dict]:
    """まだ絵の来ていない注文。`older_than` を渡すと、それより古いものだけ。

    **外の毎時セッションが止まったことに気づく口です** —— 齢が伸び続けたら、
    向こうが動いていません（`docs/IMAGE_ORDERS.md` の受け口を確認すること）。
    """
    out = []
    now = _now()
    for p in sorted(ORDERS.glob("*.json")):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        oid = str(row.get("id") or p.stem)
        if delivered(oid):
            continue
        try:
            asked = datetime.fromisoformat(str(row.get("asked_at")))
        except Exception:                                   # noqa: BLE001
            asked = now
        age = now - asked
        if older_than is not None and age < older_than:
            continue
        row["age_hours"] = round(age.total_seconds() / 3600, 1)
        out.append(row)
    return out


def report() -> str:
    orders = sorted(ORDERS.glob("*.json"))
    done = [p for p in orders if delivered(p.stem)]
    late = pending(timedelta(hours=2))
    lines = [
        "=== GPT Image 2.0 の注文（`docs/IMAGE_ORDERS.md`）===",
        f"  注文 {len(orders)}件 ／ 届いた {len(done)}件 ／ まだ {len(orders) - len(done)}件",
    ]
    if not orders:
        lines.append("  **注文が1件もありません。** 外のセッションは注文が無いと"
                     "1枚も焼けないので、**このままでは絵は永久に来ません。**")
    if late:
        lines.append(f"  [!] **2時間 以上 待っている注文が {len(late)}件**"
                     "（外の毎時セッションが動いていない可能性）:")
        for r in late[:5]:
            lines.append(f"      {r.get('id')}  {r.get('age_hours')}時間")
    lines.append("  **来ていなくても止めません** —— `image_for()` が `None` を返し、"
                 "`src/visuals.py` が自前の図解で焼きます。")
    return "\n".join(lines)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--order", metavar="TOPIC", help="その本のぶんを注文する")
    ap.add_argument("--prompt", default="", help="GPT Image 2.0 に渡す文")
    a = ap.parse_args()
    if a.order:
        row = place(a.order, a.prompt or f"{a.order} の背景。抽象的で落ち着いた図形。",
                    for_text=f"{a.order} の動画内の背景")
        print(("既に在ります: " if row.get("already") else "置きました: ")
              + str(path_of(str(row["id"]))))
    print(report())


if __name__ == "__main__":
    main()
