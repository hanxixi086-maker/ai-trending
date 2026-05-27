"""Vibe Coding 专属来源：Reddit、Dev.to、HN Show Vibe、官方 Showcase、RSSHub、V2EX。

所有函数返回统一格式：{"name": ..., "error": ..., "items": [...]}
失败时优雅降级（items=[], error=<message>），绝不影响主构建流程。

来源分三档（见 config.VIBE_SOURCES）：
  第一档：Reddit、Dev.to、HN Show Vibe、官方 Showcase（stable or best-effort）
  第二档：B站、掘金、即刻（经 RSSHub）、V2EX（官方 RSS）
  第三档：X、小红书、抖音（默认关闭，公共 RSSHub 实例不稳）
"""

import html as html_lib
import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from config import (
    DEVTO_LIMIT, REDDIT_LIMIT, REDDIT_USER_AGENT,
    REQUEST_HEADERS, REQUEST_TIMEOUT, RSSHUB_BASE,
    VIBE_RSSHUB_LIMIT, VIBE_SOURCES, VIBE_TOOL_NAMES, VIBE_WORK_KEYWORDS,
)


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _low(text: str) -> str:
    return (text or "").lower()


def _clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    return BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)


def _vibe_item(tool_name, title, url, source, extra, summary, kind, pre_images=None):
    """构建统一的 Vibe Coding 条目字典（含 _pre_images 临时字段）。"""
    return {
        "tool_name":   tool_name,
        "title":       title,
        "url":         url,
        "source":      source,
        "extra":       extra,
        "summary":     summary,
        "images":      [],
        "_pre_images": list(pre_images) if pre_images else [],   # 临时，build.py 丰富后删除
        "reason":      "",
        "category":    "实用",   # Vibe Coding 项目默认归「实用」
        "kind":        kind,
    }


def _guess_kind(title: str, summary: str, default: str = "工具") -> str:
    """根据标题和摘要判断 Vibe Coding 条目是「工具」还是「作品」。"""
    combined = _low(f"{title} {summary}")
    # 工具名称直接命中 → 工具
    for tool in VIBE_TOOL_NAMES:
        t = _low(title)
        if t == tool or t.startswith(tool + " ") or t.startswith(tool + ":"):
            return "工具"
    # 作品信号词
    if any(kw in combined for kw in VIBE_WORK_KEYWORDS):
        return "作品"
    if "show hn:" in _low(title):
        return "作品"
    return default


# ── 第一档：Reddit ────────────────────────────────────────────────────────────

def fetch_reddit_subreddit(subreddit: str, kind_default: str = "工具") -> dict:
    """
    用 .json 端点抓取 Reddit 子版块本月 top 帖（免密钥）。
    请求头必须带自定义 User-Agent，否则返回 429。
    帖子里外部链接 → item.url = 外部链接；纯讨论帖 → item.url = reddit 帖子页面。
    """
    name = f"Reddit r/{subreddit}"
    url  = f"https://www.reddit.com/r/{subreddit}/top.json?t=month&limit=50"
    try:
        resp = requests.get(
            url,
            headers={**REQUEST_HEADERS, "User-Agent": REDDIT_USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 429:
            return {"name": name, "error": "Rate limited (429) — 请稍后重试", "items": []}
        if resp.status_code != 200:
            return {"name": name, "error": f"HTTP {resp.status_code}", "items": []}

        children = resp.json().get("data", {}).get("children", [])
        items = []
        for child in children:
            try:
                post = child.get("data", {})
                title = (post.get("title") or "").strip()
                if not title:
                    continue
                score = post.get("score", 0) or 0
                if score < 5:
                    continue

                # 外部链接优先；否则用 reddit 帖子页面
                ext_url   = post.get("url", "")
                permalink = "https://www.reddit.com" + (post.get("permalink") or "")
                item_url  = (
                    ext_url
                    if ext_url and not ext_url.startswith("https://www.reddit.com")
                    else permalink
                )

                selftext = (post.get("selftext") or "")[:300]
                comments = post.get("num_comments", 0) or 0

                # 预览图（reddit 将 URL 中的 & 存为 HTML 实体，需 unescape）
                pre_imgs = []
                try:
                    raw_preview = post["preview"]["images"][0]["source"]["url"]
                    pre_imgs.append(html_lib.unescape(raw_preview))
                except (KeyError, IndexError, TypeError):
                    pass
                thumb = post.get("thumbnail", "")
                if thumb and thumb.startswith("http") and thumb not in pre_imgs:
                    pre_imgs.append(thumb)

                kind = _guess_kind(title, selftext, kind_default)

                items.append(_vibe_item(
                    tool_name=title[:60],
                    title=title,
                    url=item_url,
                    source="Reddit",
                    extra=f"r/{subreddit} · {score} pts · {comments} 评论",
                    summary=selftext or title,
                    kind=kind,
                    pre_images=pre_imgs,
                ))
                if len(items) >= REDDIT_LIMIT:
                    break
            except Exception:
                continue

        return {"name": name, "error": None, "items": items}
    except Exception as exc:
        return {"name": name, "error": str(exc), "items": []}


# ── 第一档：Dev.to ────────────────────────────────────────────────────────────

def fetch_devto() -> dict:
    """抓取 Dev.to 多标签热门文章（免密钥）。封面图作为 _pre_images[0]。"""
    tags = ("ai", "cursor", "aitools")
    all_items, seen, errors = [], set(), []

    for tag in tags:
        try:
            resp = requests.get(
                f"https://dev.to/api/articles?tag={tag}&top=30",
                headers={**REQUEST_HEADERS, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                errors.append(f"tag={tag}: HTTP {resp.status_code}")
                continue
            for art in resp.json():
                art_url = art.get("url", "")
                if not art_url or art_url in seen:
                    continue
                title     = (art.get("title") or "").strip()
                desc      = (art.get("description") or "")[:300]
                cover     = art.get("cover_image") or ""
                reactions = art.get("public_reactions_count", 0) or 0
                username  = (art.get("user") or {}).get("username", "")
                pre_imgs  = [cover] if cover and cover.startswith("http") else []
                kind      = _guess_kind(title, desc, default="作品")

                seen.add(art_url)
                all_items.append(_vibe_item(
                    tool_name=title[:60],
                    title=title,
                    url=art_url,
                    source="Dev.to",
                    extra=(
                        f"Dev.to · {reactions} ❤  @{username}"
                        if username else f"Dev.to · {reactions} ❤"
                    ),
                    summary=desc,
                    kind=kind,
                    pre_images=pre_imgs,
                ))
            time.sleep(0.5)   # 礼貌限速
        except Exception as exc:
            errors.append(str(exc))

    error = "; ".join(errors) if errors and not all_items else None
    # 每 tag 上限 DEVTO_LIMIT 条
    return {"name": "Dev.to", "error": error, "items": all_items[: DEVTO_LIMIT * len(tags)]}


# ── 第一档：HN Show Vibe（扩展，专注作品展示）────────────────────────────────

def fetch_hn_show_vibe() -> dict:
    """
    Algolia 近 30 天「Show HN」+ Vibe 工具关键词的帖子，全部归 kind=作品。
    与 sources.py 的 fetch_hackernews() 互补——后者面向 AI 工具本身，
    本函数专注「用这些工具做出来的作品」。
    """
    since_ts = (datetime.now() - timedelta(days=30)).timestamp()
    queries = [
        "Show HN cursor",
        "Show HN v0",
        "Show HN bolt",
        "Show HN lovable",
        "Show HN claude code",
        "Show HN vibe coding",
    ]
    all_hits, seen, errors = [], set(), []

    for q in queries:
        try:
            url = (
                "https://hn.algolia.com/api/v1/search_by_date"
                "?tags=story"
                f"&query={urllib.parse.quote(q)}"
                "&hitsPerPage=30"
            )
            data = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT).json()
            for hit in data.get("hits", []):
                oid  = hit.get("objectID", "")
                surl = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                if surl in seen:
                    continue
                if hit.get("created_at_i", 0) < since_ts:
                    continue
                title = hit.get("title", "")
                if not title or "show hn" not in title.lower():
                    continue
                seen.add(surl)
                all_hits.append(hit)
        except Exception as exc:
            errors.append(str(exc))

    all_hits.sort(key=lambda h: h.get("points") or 0, reverse=True)

    items = []
    for hit in all_hits[:50]:
        title    = hit.get("title", "")
        oid      = hit.get("objectID", "")
        surl     = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
        points   = hit.get("points", 0) or 0
        comments = hit.get("num_comments", 0) or 0
        items.append(_vibe_item(
            tool_name=title[:60],
            title=title,
            url=surl,
            source="Hacker News",
            extra=f"{points} points · {comments} comments",
            summary=_clean_html(hit.get("story_text") or title)[:300],
            kind="作品",
        ))

    error = "; ".join(errors) if errors and not items else None
    return {"name": "HN Show Vibe", "error": error, "items": items}


# ── 第一档：官方 Showcase（best-effort）─────────────────────────────────────

_SHOWCASE_URLS = {
    "v0.dev":   "https://v0.dev/community",
    "bolt.new": "https://bolt.new/showcase",
    "Lovable":  "https://lovable.dev/showcase",
    "Replit":   "https://replit.com/showcase",
}


def _extract_nextdata_items(
    data, source: str, netloc: str,
    depth: int = 0, _seen: set = None, _out: list = None,
) -> list:
    """递归从 Next.js __NEXT_DATA__ 中找含 url+title 的对象（最多 20 个，深度 ≤ 7）。"""
    if _seen is None:
        _seen = set()
    if _out is None:
        _out = []
    if depth > 7 or len(_out) >= 20:
        return _out

    if isinstance(data, dict):
        url   = str(data.get("url") or data.get("href") or data.get("link") or "")
        title = str(data.get("title") or data.get("name") or data.get("label") or "")
        img   = str(
            data.get("image") or data.get("thumbnail") or
            data.get("coverImage") or data.get("imageUrl") or ""
        )
        if url.startswith("/"):
            url = f"https://{netloc}{url}"
        if url.startswith("http") and len(title) > 2 and url not in _seen:
            _seen.add(url)
            pre_imgs = [img] if img.startswith("http") else []
            _out.append(_vibe_item(
                tool_name=title[:60], title=title, url=url,
                source=source, extra=f"{source} showcase",
                summary=title, kind="作品", pre_images=pre_imgs,
            ))
        for v in data.values():
            if isinstance(v, (dict, list)) and len(_out) < 20:
                _extract_nextdata_items(v, source, netloc, depth + 1, _seen, _out)
    elif isinstance(data, list) and len(data) <= 500:
        for elem in data:
            if isinstance(elem, (dict, list)) and len(_out) < 20:
                _extract_nextdata_items(elem, source, netloc, depth + 1, _seen, _out)
    return _out


def fetch_showcase(platform: str) -> dict:
    """
    抓取官方 showcase 页的真实项目（best-effort）。
    这些页面多为 Next.js/React SPA，JS 渲染时返回空属正常，不报严重错误。
    """
    url = _SHOWCASE_URLS.get(platform)
    if not url:
        return {"name": platform, "error": "Unknown platform", "items": []}
    netloc = urlparse(url).netloc
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return {"name": platform, "error": f"HTTP {resp.status_code}", "items": []}

        soup = BeautifulSoup(resp.text, "html.parser")

        # 优先尝试 __NEXT_DATA__（Next.js SSR 时有效）
        nd_tag = soup.find("script", id="__NEXT_DATA__")
        if nd_tag and nd_tag.string:
            try:
                nd_items = _extract_nextdata_items(
                    json.loads(nd_tag.string), platform, netloc
                )
                if nd_items:
                    return {"name": platform, "error": None, "items": nd_items}
            except Exception:
                pass

        # 回退：找含图片的 <a> 卡片
        items, seen_urls = [], set()
        for card in soup.find_all("a", href=True):
            href = (card.get("href") or "").strip()
            if not href or href == "#":
                continue
            if href.startswith("/"):
                href = f"https://{netloc}{href}"
            if not href.startswith("http") or href in seen_urls:
                continue
            imgs_in_card = [
                img.get("src", "")
                for img in card.find_all("img", src=True)
                if (img.get("src", "") or "").startswith("http")
            ]
            title_el = card.find(["h2", "h3", "h4", "strong"])
            title = (
                title_el.get_text(strip=True)
                if title_el
                else card.get_text(strip=True, separator=" ")
            )[:60].strip()
            if not title or len(title) < 3 or not imgs_in_card:
                continue
            seen_urls.add(href)
            items.append(_vibe_item(
                tool_name=title, title=title, url=href,
                source=platform, extra=f"{platform} showcase",
                summary=title, kind="作品", pre_images=imgs_in_card[:3],
            ))
            if len(items) >= 20:
                break

        err = None if items else "No items found (page likely requires JS rendering)"
        return {"name": platform, "error": err, "items": items}
    except Exception as exc:
        return {"name": platform, "error": str(exc), "items": []}


# ── 第二档：RSSHub 通用抓取 ──────────────────────────────────────────────────

# source_id → (rsshub_path, display_name, kind_default)
_RSSHUB_PATHS = {
    "rsshub_bilibili":    ("/bilibili/search/vibe%20coding/0/0/3",   "B站",        "作品"),
    "rsshub_juejin":      ("/juejin/tag/AI",                          "掘金",       "工具"),
    "rsshub_jike":        ("/jike/topic/AI%E7%BC%96%E7%A8%8B",       "即刻",       "作品"),
    # 第三档（默认关闭）——公共实例不稳，X/小红书路由可能需自建实例 + 配置 cookie
    "rsshub_twitter":     ("/twitter/keyword/vibecoding",             "X(Twitter)", "作品"),
    "rsshub_xiaohongshu": ("/xiaohongshu/keyword/vibe%20coding",      "小红书",     "作品"),
    "rsshub_douyin":      ("/douyin/keyword/vibe%20coding",           "抖音",       "作品"),
}


def fetch_rsshub(source_id: str) -> dict:
    """通过 RSSHub 抓取指定源，失败时优雅降级（返回 items=[], error=<msg>）。"""
    cfg = _RSSHUB_PATHS.get(source_id)
    if not cfg:
        return {"name": source_id, "error": "Unknown source_id", "items": []}
    path, name, kind_default = cfg
    full_url = f"{RSSHUB_BASE.rstrip('/')}{path}"
    try:
        feed = feedparser.parse(full_url)
        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS parse failed or empty: {full_url}")
        items = []
        for entry in feed.entries[:VIBE_RSSHUB_LIMIT]:
            title   = (entry.get("title") or "").strip()
            url     = entry.get("link", "")
            summary = _clean_html(
                entry.get("summary") or entry.get("description") or ""
            )[:300]
            if not title or not url:
                continue
            # 从 summary HTML 提取第一张图作为 _pre_images
            pre_imgs = []
            raw_html = entry.get("summary") or ""
            soup = BeautifulSoup(raw_html, "html.parser")
            for img in soup.find_all("img", src=True):
                src = img.get("src", "")
                if src and src.startswith("http"):
                    pre_imgs.append(src)
                    break
            kind = _guess_kind(title, summary, kind_default)
            pub = ""
            if getattr(entry, "published_parsed", None):
                try:
                    pub = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
                except Exception:
                    pass
            items.append(_vibe_item(
                tool_name=title[:60], title=title, url=url,
                source=name,
                extra=f"{name} · {pub}" if pub else name,
                summary=summary, kind=kind, pre_images=pre_imgs,
            ))
        return {"name": name, "error": None, "items": items}
    except Exception as exc:
        return {"name": name, "error": str(exc), "items": []}


# ── 第二档：V2EX（官方 RSS，无需 RSSHub）────────────────────────────────────

_V2EX_KEYWORDS = [
    "cursor", "claude", "copilot", "windsurf", "bolt", " v0 ",
    "lovable", "cline", "aider", "vibe", "ai编程", "ai 编程",
    "代码生成", "github copilot", "chatgpt coding",
]


def fetch_v2ex() -> dict:
    """V2EX 官方 RSS，过滤出与 Vibe Coding 相关的帖子。"""
    try:
        feed = feedparser.parse("https://www.v2ex.com/index.xml")
        if feed.bozo and not feed.entries:
            raise ValueError("V2EX RSS parse failed or empty")
        items = []
        for entry in feed.entries:
            title   = (entry.get("title") or "").strip()
            url     = entry.get("link", "")
            summary = _clean_html(entry.get("summary") or "")[:300]
            if not title or not url:
                continue
            if not any(kw in _low(f"{title} {summary}") for kw in _V2EX_KEYWORDS):
                continue
            kind = _guess_kind(title, summary, "工具")
            items.append(_vibe_item(
                tool_name=title[:60], title=title, url=url,
                source="V2EX", extra="V2EX",
                summary=summary, kind=kind,
            ))
            if len(items) >= VIBE_RSSHUB_LIMIT:
                break
        return {"name": "V2EX", "error": None, "items": items}
    except Exception as exc:
        return {"name": "V2EX", "error": str(exc), "items": []}


# ── 总调度 ────────────────────────────────────────────────────────────────────

def fetch_all_vibe_sources() -> list:
    """
    按 config.VIBE_SOURCES 配置调度所有 Vibe Coding 专属来源。
    返回 [{"name": ..., "error": ..., "items": [...]}] 列表，顺序与 VIBE_SOURCES 一致。
    """
    enabled = {s["id"] for s in VIBE_SOURCES if s.get("enabled", False)}
    results = []

    # Reddit（4 个 subreddit，按顺序，每个之间 sleep 1s 避免 429）
    reddit_map = [
        ("reddit_vibecoding",    "vibecoding",    "作品"),
        ("reddit_sideproject",   "SideProject",   "作品"),
        ("reddit_cursor",        "cursor",        "工具"),
        ("reddit_chatgptcoding", "ChatGPTCoding", "工具"),
    ]
    for sid, subreddit, kind_default in reddit_map:
        if sid in enabled:
            results.append(fetch_reddit_subreddit(subreddit, kind_default))
            time.sleep(1)

    # Dev.to
    if "devto_ai" in enabled:
        results.append(fetch_devto())

    # HN Show Vibe
    if "hn_show_vibe" in enabled:
        results.append(fetch_hn_show_vibe())

    # 官方 Showcase
    showcase_map = [
        ("showcase_v0",      "v0.dev"),
        ("showcase_bolt",    "bolt.new"),
        ("showcase_lovable", "Lovable"),
        ("showcase_replit",  "Replit"),
    ]
    for sid, platform in showcase_map:
        if sid in enabled:
            results.append(fetch_showcase(platform))

    # RSSHub 源（二、三档）
    rsshub_ids = [
        "rsshub_bilibili", "rsshub_juejin", "rsshub_jike",
        "rsshub_twitter", "rsshub_xiaohongshu", "rsshub_douyin",
    ]
    for sid in rsshub_ids:
        if sid in enabled:
            results.append(fetch_rsshub(sid))

    # V2EX
    if "v2ex" in enabled:
        results.append(fetch_v2ex())

    return results
