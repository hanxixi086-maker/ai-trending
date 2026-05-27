"""数据抓取层：GitHub Trending + Search、Hacker News、Product Hunt、RSS；含分类函数。"""

import re
import time
import urllib.parse
from datetime import datetime, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup

from config import (
    AI_KEYWORDS, CONSUMER_KEYWORDS, GITHUB_LIMIT, GITHUB_SEARCH_LIMIT,
    HACKERNEWS_LIMIT, PRODUCTHUNT_LIMIT, PROFESSIONAL_KEYWORDS,
    REQUEST_HEADERS, REQUEST_TIMEOUT, RSS_FEEDS, RSS_LIMIT_PER_FEED,
    VIBE_CODING_KEYWORDS, VIBE_TOOL_NAMES, VIBE_WORK_KEYWORDS,
)


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _low(text):
    return (text or "").lower()


def matches_ai(text):
    t = _low(text)
    return any(kw in t for kw in AI_KEYWORDS)


def matches_vibe_coding(text):
    t = _low(text)
    return any(kw in t for kw in VIBE_CODING_KEYWORDS)


def _clean_html(html_text):
    if not html_text:
        return ""
    return BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)


def _get(url, extra_headers=None, **kwargs):
    headers = {**REQUEST_HEADERS, **(extra_headers or {})}
    return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)


def _item(tool_name, title, url, source, extra, summary):
    return {
        "tool_name": tool_name,
        "title": title,
        "url": url,
        "source": source,
        "extra": extra,
        "summary": summary,
        "images": [],
        "reason": "",
        "category": "",   # 专业 / 实用（由 build.py 填充）
        "kind": "",        # 工具 / 作品（Vibe Coding 专用，由 build.py 填充）
    }


# ── 分类函数 ──────────────────────────────────────────────────────────────────

def classify_category(item: dict) -> str:
    """判断「专业工具」vs「实用工具」。"""
    text = _low(f"{item.get('title','')} {item.get('tool_name','')} {item.get('summary','')}")

    # 专业优先（更严谨的技术信号）
    if any(kw in text for kw in PROFESSIONAL_KEYWORDS):
        return "专业"
    if any(kw in text for kw in CONSUMER_KEYWORDS):
        return "实用"
    # GitHub 仓库默认偏专业；其他来源默认实用
    return "专业" if item.get("source") == "GitHub" else "实用"


def classify_vibe_kind(item: dict) -> str:
    """判断 Vibe Coding 条目是「工具」本身还是用工具做出的「作品」。"""
    title   = _low(item.get("title", ""))
    tname   = _low(item.get("tool_name", ""))
    summary = _low(item.get("summary", ""))
    combined = f"{title} {summary}"

    # 判断是否就是工具本身（名称直接命中）
    for tool in VIBE_TOOL_NAMES:
        if tname == tool or title == tool or title.startswith(tool + " ") or title.startswith(tool + ":"):
            return "工具"
    # Product Hunt 列出工具本身
    if item.get("source") == "Product Hunt":
        for tool in VIBE_TOOL_NAMES[:10]:
            if tool in title:
                return "工具"

    # 作品识别关键词
    if any(kw in combined for kw in VIBE_WORK_KEYWORDS):
        return "作品"
    # "Show HN:" 开头几乎都是展示作品
    if "show hn:" in title:
        return "作品"
    # GitHub 仓库里描述里提到是用这些工具做的
    if item.get("source") == "GitHub":
        if any(kw in combined for kw in ["built with", "made with", "using cursor", "using claude", "built using"]):
            return "作品"

    return "工具"


# ── GitHub Trending ───────────────────────────────────────────────────────────

def _github_trending_period(period: str) -> list:
    """抓取一个 GitHub Trending 周期（daily / weekly / monthly）。"""
    url = "https://github.com/trending" + (f"?since={period}" if period != "daily" else "")
    try:
        resp = _get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for box in soup.select("article.Box-row"):
            try:
                name_tag = box.select_one("h2 a")
                if not name_tag:
                    continue
                repo_path = name_tag.get("href", "").strip("/")
                if "/" not in repo_path:
                    continue

                desc_tag = box.select_one("p")
                summary  = desc_tag.get_text(strip=True) if desc_tag else ""

                if not matches_ai(f"{repo_path} {summary}"):
                    continue

                lang_tag   = box.select_one("[itemprop='programmingLanguage']")
                lang       = lang_tag.get_text(strip=True) if lang_tag else ""
                stars_tag  = box.select_one(".float-sm-right")
                stars_info = ""
                if stars_tag:
                    raw = re.sub(r"\s+", " ", stars_tag.get_text(strip=True))
                    period_map = {"weekly": "本周 stars", "monthly": "本月 stars"}
                    stars_info = re.sub(r"stars today", period_map.get(period, "stars today"), raw, flags=re.IGNORECASE)

                owner, repo = repo_path.split("/", 1)
                items.append(_item(
                    tool_name=repo,
                    title=f"{owner} / {repo}",
                    url=f"https://github.com/{repo_path}",
                    source="GitHub",
                    extra=" · ".join(p for p in [lang, stars_info] if p),
                    summary=summary,
                ))
                if len(items) >= GITHUB_LIMIT:
                    break
            except Exception:
                continue
        return items
    except Exception:
        return []


def fetch_github_trending() -> dict:
    """抓取 GitHub daily + weekly + monthly trending，三期合并去重。"""
    all_items, seen = [], set()
    for period in ["daily", "weekly", "monthly"]:
        for it in _github_trending_period(period):
            if it["url"] not in seen:
                seen.add(it["url"])
                all_items.append(it)
    return {"items": all_items, "error": None if all_items else "No items scraped"}


# ── GitHub Search API ─────────────────────────────────────────────────────────

def fetch_github_search() -> dict:
    """用 GitHub Search API 补充近 30 天高星 AI 仓库（免登录，60 req/h）。"""
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    queries = [
        f"topic:ai+pushed:>{since}",
        f"topic:llm+pushed:>{since}",
        f"topic:machine-learning+pushed:>{since}",
    ]
    all_items, seen = [], set()
    errors = []
    for q in queries:
        try:
            url = (
                "https://api.github.com/search/repositories"
                f"?q={q}&sort=stars&order=desc&per_page=30"
            )
            resp = _get(url, extra_headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 403:
                errors.append("GitHub API rate limit hit")
                break
            if resp.status_code != 200:
                continue
            for repo in resp.json().get("items", []):
                repo_url = repo.get("html_url", "")
                if not repo_url or repo_url in seen:
                    continue
                desc  = repo.get("description", "") or ""
                name  = repo.get("name", "")
                fname = repo.get("full_name", "")
                stars = repo.get("stargazers_count", 0)
                lang  = repo.get("language", "") or ""
                if not matches_ai(f"{name} {desc}"):
                    continue
                seen.add(repo_url)
                all_items.append(_item(
                    tool_name=name,
                    title=fname,
                    url=repo_url,
                    source="GitHub",
                    extra=f"{lang} · {stars:,} stars" if lang else f"{stars:,} stars",
                    summary=desc,
                ))
            time.sleep(2)   # 尊重 GitHub API 速率限制
        except Exception as exc:
            errors.append(str(exc))
            continue
    error = "; ".join(errors) if errors and not all_items else None
    return {"items": all_items[:GITHUB_SEARCH_LIMIT], "error": error}


# ── Hacker News ──────────────────────────────────────────────────────────────

def fetch_hackernews() -> dict:
    """抓取 HN 近 7 天 AI 热帖（多查询合并，按 points 排序）。"""
    since_ts = (datetime.now() - timedelta(days=7)).timestamp()
    queries = [
        "AI LLM language model",
        "machine learning deep learning",
        "Claude GPT ChatGPT",
        "Show HN AI",
    ]
    all_hits, seen = [], set()
    errors = []
    for q in queries:
        try:
            url = (
                "https://hn.algolia.com/api/v1/search_by_date"
                f"?tags=story"
                f"&query={urllib.parse.quote(q)}"
                "&hitsPerPage=50"
            )
            data = _get(url).json()
            for hit in data.get("hits", []):
                oid       = hit.get("objectID", "")
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                if story_url in seen:
                    continue
                # 只要近 7 天
                if hit.get("created_at_i", 0) < since_ts:
                    continue
                title = hit.get("title", "")
                if not title or not matches_ai(title):
                    continue
                seen.add(story_url)
                all_hits.append(hit)
        except Exception as exc:
            errors.append(str(exc))
            continue

    # 按 points 降序
    all_hits.sort(key=lambda h: (h.get("points") or 0), reverse=True)

    items = []
    for hit in all_hits[:HACKERNEWS_LIMIT * 2]:
        title    = hit.get("title", "")
        oid      = hit.get("objectID", "")
        surl     = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
        points   = hit.get("points", 0) or 0
        comments = hit.get("num_comments", 0) or 0
        items.append(_item(
            tool_name=title[:60],
            title=title,
            url=surl,
            source="Hacker News",
            extra=f"{points} points · {comments} comments",
            summary=_clean_html(hit.get("story_text") or title)[:300],
        ))
        if len(items) >= HACKERNEWS_LIMIT:
            break

    error = "; ".join(errors) if errors and not items else None
    return {"items": items, "error": error}


# ── Product Hunt ─────────────────────────────────────────────────────────────

def fetch_producthunt() -> dict:
    """通过 RSS 抓取 Product Hunt 条目（依赖跨天累积补充历史榜单）。"""
    try:
        feed = feedparser.parse("https://www.producthunt.com/feed")
        if feed.bozo and not feed.entries:
            raise ValueError("PH RSS parse failed")
        items = []
        for entry in feed.entries:
            title   = entry.get("title", "")
            url     = entry.get("link", "")
            summary = _clean_html(entry.get("summary", ""))
            if not title or not url:
                continue
            if not matches_ai(f"{title} {summary}"):
                continue
            items.append(_item(
                tool_name=title,
                title=title,
                url=url,
                source="Product Hunt",
                extra="今日上榜",
                summary=summary[:300],
            ))
            if len(items) >= PRODUCTHUNT_LIMIT:
                break
        return {"items": items, "error": None}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


# ── RSS 订阅源 ─────────────────────────────────────────────────────────────────

def fetch_rss() -> list:
    """抓取所有配置的 RSS 源。"""
    results = []
    for cfg in RSS_FEEDS:
        result = {"name": cfg["name"], "error": None, "items": []}
        try:
            feed = feedparser.parse(cfg["url"])
            if feed.bozo and not feed.entries:
                raise ValueError(f"Failed to parse {cfg['url']}")
            items = []
            for entry in feed.entries:
                title   = entry.get("title", "")
                url     = entry.get("link", "")
                summary = _clean_html(entry.get("summary") or entry.get("description", ""))
                if not title or not url:
                    continue
                if not matches_ai(f"{title} {summary}"):
                    continue
                pub = ""
                if getattr(entry, "published_parsed", None):
                    pub = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
                items.append(_item(
                    tool_name=title[:60],
                    title=title,
                    url=url,
                    source=cfg["name"],
                    extra=f"{cfg['name']} · {pub}" if pub else cfg["name"],
                    summary=summary[:300],
                ))
                if len(items) >= RSS_LIMIT_PER_FEED:
                    break
            result["items"] = items
        except Exception as exc:
            result["error"] = str(exc)
        results.append(result)
    return results
