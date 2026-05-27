"""
Smoke test: generates synthetic JSON with placeholder images so you can
verify both tabs, gallery, search, filter and date-picker without
needing network access.

Usage:
    python test_smoke.py
    cd web && python -m http.server 8000
    # open http://localhost:8000
"""

import json
import os
import struct
import zlib
from datetime import datetime
from pathlib import Path

WEB_DIR    = Path(__file__).parent / "web"
DATA_DIR   = WEB_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
INDEX_FILE = DATA_DIR / "index.json"

DATE = datetime.now().strftime("%Y-%m-%d")


# ── PNG factory (no dependencies) ────────────────────────────────────────────

def _make_png(width: int, height: int, r: int, g: int, b: int) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw  = b"".join(b"\x00" + bytes([r, g, b] * width) for _ in range(height))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def _save_png(path: str, r: int, g: int, b: int, w=400, h=225):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(_make_png(w, h, r, g, b))


# ── Build synthetic items ─────────────────────────────────────────────────────

def make_images(slug: str, colors: list[tuple]) -> list[str]:
    paths = []
    for i, (r, g, b) in enumerate(colors, 1):
        fname = f"{slug}-{i}.png"
        full  = str(IMAGES_DIR / DATE / fname)
        _save_png(full, r, g, b)
        paths.append(f"data/images/{DATE}/{fname}")
    return paths


def build_smoke_data():
    gh_items = [
        {
            "tool_name": "awesome-llm-apps",
            "title": "Shubhamsaboo / awesome-llm-apps",
            "url": "https://github.com/Shubhamsaboo/awesome-llm-apps",
            "source": "GitHub", "category": "专业",
            "extra": "Python · 47 stars today",
            "summary": "A curated collection of awesome LLM apps built with RAG and AI agents.",
            "images": make_images("awesome-llm-apps", [(30, 100, 210), (20, 160, 100), (180, 60, 200)]),
            "reason": "精选的 LLM 应用合集，含 RAG 与 AI Agent 示例，今日新增 47 GitHub stars。",
            "kind": "",
        },
        {
            "tool_name": "open-interpreter",
            "title": "OpenInterpreter / open-interpreter",
            "url": "https://github.com/OpenInterpreter/open-interpreter",
            "source": "GitHub", "category": "实用",
            "extra": "Python · 32 stars today",
            "summary": "A natural language interface for computers — lets LLMs run code on your machine.",
            "images": make_images("open-interpreter", [(220, 80, 50), (50, 180, 220)]),
            "reason": "允许 LLM 在本地运行代码的自然语言接口，今日新增 32 stars。",
            "kind": "",
        },
    ]

    hn_items = [
        {
            "tool_name": "Show HN: LocalAI v2.0",
            "title": "Show HN: LocalAI v2.0 – run any LLM locally, no GPU needed",
            "url": "https://news.ycombinator.com/item?id=1234567",
            "source": "Hacker News", "category": "专业",
            "extra": "312 points · 87 comments",
            "summary": "LocalAI is a free, open-source alternative to OpenAI. It runs LLMs, generates images and audio locally.",
            "images": make_images("localai", [(40, 160, 255), (255, 140, 30), (100, 220, 140)]),
            "reason": "无需 GPU 即可本地运行任意 LLM，获得 312 HN 分，注重隐私的理想选择。",
            "kind": "",
        },
    ]

    ph_items = [
        {
            "tool_name": "Cursor Tab Pro",
            "title": "Cursor Tab Pro – AI-powered IDE for serious coders",
            "url": "https://www.producthunt.com/posts/cursor-tab-pro",
            "source": "Product Hunt", "category": "实用",
            "extra": "今日上榜",
            "summary": "Cursor Tab Pro brings next-level autocomplete and multi-file editing to your workflow with Claude and GPT-4.",
            "images": make_images("cursor-tab-pro", [(130, 80, 250), (80, 200, 180), (240, 90, 130), (60, 140, 255)]),
            "reason": "集成 Claude 与 GPT-4 的 AI IDE，登上 Product Hunt 今日榜单，Vibe Coding 玩家必试。",
            "kind": "",
        },
    ]

    rss_items = [
        {
            "tool_name": "GPT-4o 多模态新突破",
            "title": "GPT-4o 实现实时语音+视觉多模态新突破，延迟降至 232ms",
            "url": "https://www.jiqizhixin.com/articles/example",
            "source": "机器之心", "category": "实用",
            "extra": "机器之心 · 2026-05-26",
            "summary": "OpenAI 发布 GPT-4o 最新版本，在实时语音识别和视觉理解上取得重大突破，端到端延迟降至 232ms。",
            "images": make_images("gpt4o-jiqizhixin", [(0, 180, 160), (255, 100, 50)]),
            "reason": "机器之心报道：GPT-4o 新版实时延迟降至 232ms，多模态能力显著提升。",
            "kind": "",
        },
    ]

    rss_feed = [{"name": "机器之心", "error": None, "items": rss_items}]

    # Vibe Coding cross-cut（加 kind 字段）
    vibe_coding = [
        {**ph_items[0], "kind": "工具"},   # Cursor Tab Pro 是工具本身
        {**gh_items[1], "kind": "作品"},   # open-interpreter 更像作品
    ]

    return {
        "date": DATE,
        "generated_at": datetime.now().isoformat(),
        "ai_tools": {
            "github":      {"items": gh_items,  "error": None},
            "hackernews":  {"items": hn_items,  "error": None},
            "producthunt": {"items": ph_items,  "error": None},
            "rss":         rss_feed,
        },
        "vibe_coding": vibe_coding,
    }


def update_index(date_str: str):
    if INDEX_FILE.exists():
        index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    else:
        index = {"dates": []}
    dates = index.get("dates", [])
    if date_str in dates:
        dates.remove(date_str)
    dates.insert(0, date_str)
    index["dates"] = dates
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print(f"Generating smoke-test data for {DATE} …")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (IMAGES_DIR / DATE).mkdir(parents=True, exist_ok=True)

    data = build_smoke_data()

    out = DATA_DIR / f"{DATE}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Written → {out}")

    update_index(DATE)
    print(f"  index.json updated")

    ai_count   = sum(
        len(data["ai_tools"][s]["items"]) if isinstance(data["ai_tools"][s], dict)
        else sum(len(f["items"]) for f in data["ai_tools"][s])
        for s in data["ai_tools"]
    )
    vibe_count = len(data["vibe_coding"])
    print(f"\n  AI Tools items : {ai_count}")
    print(f"  Vibe Coding    : {vibe_count}")
    print(f"\nPreview:")
    print(f"  cd web && python -m http.server 8000")
    print(f"  Then open → http://localhost:8000")


if __name__ == "__main__":
    main()
