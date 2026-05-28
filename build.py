"""主构建脚本：抓取 → 跨天累积 → 丰富(单图+intro) → 分类 → 名称去重 → 精选评分 → 写 JSON → 更新索引。"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Windows GBK 终端下强制 UTF-8 输出，避免 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import (
    ACCUMULATE_DAYS, MAX_ITEMS_PER_SOURCE,
    FEATURE_WEIGHTS, FEATURED_COUNT, FEATURED_MAX_PER_SOURCE,
)
from image_fetcher import fetch_image_for_item
from intro_generator import generate_intro
from sources import (
    classify_category, classify_vibe_kind,
    fetch_github_search, fetch_github_trending,
    fetch_hackernews, fetch_producthunt, fetch_rss,
    matches_vibe_coding,
)
from vibe_sources import fetch_all_vibe_sources

WEB_DIR    = Path(__file__).parent / "web"
DATA_DIR   = WEB_DIR / "data"
INDEX_FILE = DATA_DIR / "index.json"

# ── 来源优先级（名称去重时选最优版本）────────────────────────────────────────────
_SOURCE_RANK = {
    "product hunt": 6, "producthunt": 6,
    "github": 5,
    "hacker news": 4, "hn show vibe": 4,
    "dev.to": 3,
    "reddit": 2,
    "v2ex": 1,
}


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def _dedup(items: list) -> list:
    seen, out = set(), []
    for it in items:
        u = it.get("url", "")
        if u and u not in seen:
            seen.add(u)
            out.append(it)
    return out


def _merge(fresh: list, historical: list, limit: int) -> list:
    """
    fresh 优先合并：同 URL 时从 historical 继承 image / intro，避免重复丰富。
    """
    hist_by_url = {it.get("url", ""): it for it in historical if it.get("url")}
    seen, merged = set(), []

    for it in fresh:
        u = it.get("url", "")
        if not u or u in seen:
            continue
        seen.add(u)
        if u in hist_by_url:
            h = hist_by_url[u]
            if not it.get("image") and h.get("image"):
                it["image"] = h["image"]
            if not it.get("intro") and h.get("intro"):
                it["intro"] = h["intro"]
        merged.append(it)
        if len(merged) >= limit:
            return merged

    for it in historical:
        u = it.get("url", "")
        if u and u not in seen:
            seen.add(u)
            merged.append(it)
            if len(merged) >= limit:
                break

    return merged


def _url_set(items: list) -> set:
    return {it.get("url", "") for it in items if it.get("url")}


_SLOGAN_FUNC_WORDS = [
    'tool', 'tools', 'library', 'framework', 'app', 'application', 'platform',
    'system', 'service', 'api', 'sdk', 'cli', 'plugin', 'extension', 'browser',
    'interface', 'client', 'helps', 'allows', 'enables', 'provides', 'lets you',
    'built for', 'designed for', 'build', 'create', 'generate', 'analyze',
    'manage', 'automate', 'deploy', 'run', 'connect', 'convert', 'transform',
    'search', 'translate', 'monitor', 'track', 'schedule', 'integrate',
    'open source', 'open-source', 'local', 'self-hosted', 'for your', 'for the',
    'that lets', 'that helps', 'turns', 'gives', 'makes it',
]
# 预编译正则：单词边界，防止 "app" 误匹配 "apple"、"api" 误匹配 "capability" 等
_SLOGAN_FUNC_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(w) for w in _SLOGAN_FUNC_WORDS) + r')\b',
    re.IGNORECASE,
)


def _is_english_slogan(text: str) -> bool:
    if not text or len(text) < 5 or len(text) >= 120:
        return False
    if sum(1 for c in text if ord(c) < 128) / len(text) < 0.85:
        return False
    return not bool(_SLOGAN_FUNC_RE.search(text))


def _is_english_text(text: str) -> bool:
    """文本是否以英文为主（非 ASCII 占比 < 15%）。"""
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) >= 128)
    return non_ascii / len(text) < 0.15


# 套话黑名单（这些出现在历史 JSON 里，4b 步骤会触发重新生成）
_BOILERPLATE_HL  = {"登上 Product Hunt 今日榜单", "GitHub Trending 广泛关注",
                    "Hacker News 社区热议", "近期 AI 社区热点", "信息有限"}
_BOILERPLATE_WHY = {"Product Hunt 今日精选产品", "近期 AI 社区热点",
                    "GitHub Trending 广泛关注", "Hacker News 社区热议",
                    "开发者社区热点话题", "V2EX 技术社区热议"}


def _intro_needs_regen(item: dict) -> bool:
    """
    True = intro 需要用新版生成器重新生成（步骤 3 丰富阶段触发）。
    检测条件：
      1. what 是英文（口号或功能描述均不可留）
      2. why_featured 含有对比套话但源描述没有明确的对比标记
         （"同类工具/竞品/大多数…"系列，需用新 prompt + 后置过滤清理）
    """
    from intro_generator import (_is_english_slogan, _is_english_text,
                                  _GENERIC_COMPARE, _source_has_explicit_compare)
    intro = item.get("intro")
    if not intro or not isinstance(intro, dict):
        return True
    what = intro.get("what", "")
    if what and (_is_english_slogan(what) or _is_english_text(what)):
        return True
    # why_featured 含对比套话且源描述无明确对比标记 → 用新 prompt 重生成
    why = intro.get("why_featured", "")
    if why and _GENERIC_COMPARE.search(why) and not _source_has_explicit_compare(item):
        return True
    return False


def _need_enrich(items: list, known_urls: set) -> list:
    """
    新 URL 或缺少 image / intro 字段，
    或 intro.what 是英文口号（质量升级触发再生成）的条目需要丰富。
    """
    return [
        it for it in items
        if it.get("url", "") not in known_urls
        or not it.get("image")
        or not it.get("intro")
        or _intro_needs_regen(it)
    ]


def _normalize_name(name: str) -> str:
    """标准化工具名称，用于跨源名称去重。"""
    if not name:
        return ""
    n = name.lower().strip()
    for sep in (" - ", " – ", " | ", ": ", " : "):
        if sep in n:
            n = n.split(sep)[0].strip()
    n = re.sub(r"\bv?\d+[\.\d]*\b", "", n)                          # 去版本号
    n = re.sub(r"\.(com|io|ai|dev|app|co|net|org|xyz|gg|so)\b", "", n)  # 去 TLD
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _intro_completeness(item: dict) -> int:
    intro = item.get("intro")
    if not intro or not isinstance(intro, dict):
        return 0
    score = 0
    if intro.get("what") and intro["what"] != "信息有限":
        score += 3
    hl = intro.get("highlights", [])
    if hl and hl[0] != "信息有限":
        score += len(hl)
    if intro.get("use_case") and intro["use_case"] != "信息有限":
        score += 1
    if intro.get("why_featured") and intro["why_featured"] != "信息有限":
        score += 1
    return score


def _source_rank(item: dict) -> int:
    src = item.get("source", "").lower()
    for key, rank in _SOURCE_RANK.items():
        if key in src:
            return rank
    return 0


def _name_dedup(items: list) -> list:
    """跨源名称去重：同名工具保留 intro 最完整 + 来源优先级最高的版本。"""
    groups: dict = {}
    ungrouped: list = []
    for item in items:
        name = _normalize_name(item.get("tool_name", "") or item.get("title", ""))
        if len(name) < 2:
            ungrouped.append(item)
        else:
            groups.setdefault(name, []).append(item)

    result = ungrouped[:]
    for group in groups.values():
        if len(group) == 1:
            result.append(group[0])
        else:
            best = max(group, key=lambda it: (_intro_completeness(it), _source_rank(it)))
            result.append(best)
    return result


def _score_feature(item: dict) -> float:
    """计算精选分数，权重可在 config.py FEATURE_WEIGHTS 里调节。"""
    w = FEATURE_WEIGHTS
    score = 0.0

    # 分类加分
    cat = item.get("category", "")
    if cat == "实用":
        score += w.get("category_实用", 20)
    elif cat == "专业":
        score += w.get("category_专业", 5)

    # 来源加分
    src = item.get("source", "").lower()
    if "product" in src:
        score += w.get("source_Product Hunt", 18)
    elif ("show" in src and "hn" in src) or "hn show" in src:
        score += w.get("source_HN_show", 12)
    elif "hacker" in src:
        score += w.get("source_HN_show", 12) * 0.6   # 普通 HN，打六折
    elif "github" in src:
        score += w.get("source_GitHub", 8)
    elif "dev.to" in src:
        score += w.get("source_Dev.to", 5)
    elif "reddit" in src:
        score += w.get("source_Reddit", 6)
    elif "v2ex" in src:
        score += w.get("source_V2EX", 3)

    # Stars / HN 分数加分
    extra = item.get("extra", "")
    sm = re.search(r"([\d,]+)\s*stars?\s*today", extra, re.IGNORECASE)
    if sm:
        stars = int(sm.group(1).replace(",", ""))
        score += (stars / 100) * w.get("stars_factor", 3)
    pm = re.search(r"([\d,]+)\s*points?", extra, re.IGNORECASE)
    if pm:
        pts = int(pm.group(1).replace(",", ""))
        score += (pts / 10) * w.get("hn_pts_factor", 1)

    # Intro 完整度加分
    comp = _intro_completeness(item)
    if comp >= 6:
        score += w.get("intro_complete", 10)
    elif comp >= 2:
        score += w.get("intro_partial", 4)

    # 有图加分
    if item.get("image"):
        score += w.get("has_image", 5)

    # Vibe 作品加分
    if item.get("kind") == "作品":
        score += w.get("kind_作品", 6)

    return round(score, 2)


# ── 跨天历史加载 ───────────────────────────────────────────────────────────────

def _load_historical(date_str: str, days: int) -> dict:
    today = datetime.strptime(date_str, "%Y-%m-%d")
    pools = {
        "github": [], "hackernews": [], "producthunt": [],
        "rss": {},
        "vibe_sources": {},
    }
    for i in range(1, days):
        past   = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        f_path = DATA_DIR / f"{past}.json"
        if not f_path.exists():
            continue
        try:
            data  = json.loads(f_path.read_text(encoding="utf-8"))
            tools = data.get("ai_tools", {})
            for src in ("github", "hackernews", "producthunt"):
                pools[src].extend(tools.get(src, {}).get("items", []))
            for feed in tools.get("rss", []):
                pools["rss"].setdefault(feed["name"], []).extend(feed.get("items", []))
            for feed in data.get("vibe_sources", []):
                pools["vibe_sources"].setdefault(feed["name"], []).extend(
                    feed.get("items", [])
                )
        except Exception:
            continue
    return pools


# ── 丰富（单图 URL + intro）──────────────────────────────────────────────────

def _enrich(items: list, label: str = ""):
    """
    图片：只在没有 image 时才抓取（避免重复请求）。
    Intro：每次都重新生成（_intro_needs_regen 已过滤，只对需要的条目调用）。
    """
    total = len(items)
    for i, item in enumerate(items):
        print(f"  [{i+1}/{total}] {label}{item.get('tool_name','')[:36]}", end="", flush=True)
        if not item.get("image"):
            # 尚无图片，抓取
            try:
                item["image"] = fetch_image_for_item(item)
            except Exception as exc:
                item.pop("_pre_images", None)
                item["image"] = ""
                print(f" [img:{exc}]", end="")
        else:
            # 已有图片，只清理临时字段
            item.pop("_pre_images", None)
        try:
            item["intro"] = generate_intro(item)
        except Exception:
            item["intro"] = {
                "what": "",
                "highlights": ["信息有限"],
                "use_case": "信息有限",
                "why_featured": "信息有限",
            }
        print("  ok")


# ── 主流程 ─────────────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    t0 = datetime.now()
    print(f"\n{'='*56}")
    print(f"  AI Trending Build  {date_str}  (累积 {ACCUMULATE_DAYS} 天)")
    print(f"{'='*56}\n")

    # 1. 抓取今日新鲜数据 ───────────────────────────────────────────────────────
    print("[ 1/6 ] 抓取 AI Tools 数据源 …")

    print("  GitHub Trending (daily/weekly/monthly) …", end="", flush=True)
    gh_trend = fetch_github_trending()
    print(f"  {len(gh_trend['items'])} 条" + (f"  ERR:{gh_trend['error']}" if gh_trend["error"] else ""))

    print("  GitHub Search API …", end="", flush=True)
    gh_search = fetch_github_search()
    print(f"  {len(gh_search['items'])} 条" + (f"  ERR:{gh_search['error']}" if gh_search["error"] else ""))

    github_fresh = {
        "items": _dedup(gh_trend["items"] + gh_search["items"]),
        "error": gh_trend["error"] or gh_search["error"],
    }
    print(f"  GitHub 合计（去重）: {len(github_fresh['items'])} 条")

    print("  Hacker News …", end="", flush=True)
    hackernews_fresh = fetch_hackernews()
    print(f"  {len(hackernews_fresh['items'])} 条" + (f"  ERR:{hackernews_fresh['error']}" if hackernews_fresh["error"] else ""))

    print("  Product Hunt …", end="", flush=True)
    producthunt_fresh = fetch_producthunt()
    print(f"  {len(producthunt_fresh['items'])} 条" + (f"  ERR:{producthunt_fresh['error']}" if producthunt_fresh["error"] else ""))

    print("  RSS 订阅源 …")
    rss_fresh = fetch_rss()
    for feed in rss_fresh:
        print(f"    {feed['name']}: {len(feed['items'])} 条" + (f"  ERR:{feed['error']}" if feed["error"] else ""))

    print("\n[ 1b/6 ] 抓取 Vibe Coding 专属来源 …")
    vibe_fresh_list = fetch_all_vibe_sources()
    for feed in vibe_fresh_list:
        status = f"  ERR:{feed['error']}" if feed["error"] else ""
        print(f"  {feed['name']}: {len(feed['items'])} 条{status}")

    # 2. 加载历史数据、合并 ────────────────────────────────────────────────────
    print(f"\n[ 2/6 ] 加载历史 ({ACCUMULATE_DAYS} 天) 并合并 …")
    hist = _load_historical(date_str, ACCUMULATE_DAYS)

    github      = {"items": _merge(github_fresh["items"],      hist["github"],      MAX_ITEMS_PER_SOURCE), "error": github_fresh["error"]}
    hackernews  = {"items": _merge(hackernews_fresh["items"],  hist["hackernews"],  MAX_ITEMS_PER_SOURCE), "error": hackernews_fresh["error"]}
    producthunt = {"items": _merge(producthunt_fresh["items"], hist["producthunt"], MAX_ITEMS_PER_SOURCE), "error": producthunt_fresh["error"]}

    rss = []
    for feed_fresh in rss_fresh:
        hist_items   = hist["rss"].get(feed_fresh["name"], [])
        merged_items = _merge(feed_fresh["items"], hist_items, MAX_ITEMS_PER_SOURCE)
        rss.append({"name": feed_fresh["name"], "error": feed_fresh["error"], "items": merged_items})

    print(f"  GitHub: {len(github['items'])} | HN: {len(hackernews['items'])} | PH: {len(producthunt['items'])} | RSS: {sum(len(f['items']) for f in rss)}")

    vibe_sources = []
    for feed_fresh in vibe_fresh_list:
        hist_vs      = hist["vibe_sources"].get(feed_fresh["name"], [])
        merged_items = _merge(feed_fresh["items"], hist_vs, MAX_ITEMS_PER_SOURCE)
        vibe_sources.append({
            "name":  feed_fresh["name"],
            "error": feed_fresh["error"],
            "items": merged_items,
        })
    total_vibe_src = sum(len(f["items"]) for f in vibe_sources)
    print(f"  Vibe Sources 合计: {total_vibe_src} 条（{len(vibe_sources)} 个来源）")

    # 3. 只对缺少 image/intro 的条目做丰富 ────────────────────────────────────
    print("\n[ 3/6 ] 补充图片 & intro（新条目 + 格式迁移）…")

    hist_urls = (
        _url_set(hist["github"]) |
        _url_set(hist["hackernews"]) |
        _url_set(hist["producthunt"]) |
        {u for items in hist["rss"].values()          for u in _url_set(items)} |
        {u for items in hist["vibe_sources"].values() for u in _url_set(items)}
    )

    t_enrich = datetime.now()
    enrich_count = 0
    for src_items, label in [
        (github["items"],      "GitHub  "),
        (hackernews["items"],  "HN      "),
        (producthunt["items"], "PH      "),
    ]:
        new_items = _need_enrich(src_items, hist_urls)
        if new_items:
            enrich_count += len(new_items)
            _enrich(new_items, label)

    for feed in rss:
        new_items = _need_enrich(feed["items"], hist_urls)
        if new_items:
            enrich_count += len(new_items)
            _enrich(new_items, f"RSS {feed['name']} ")

    for feed in vibe_sources:
        new_items = _need_enrich(feed["items"], hist_urls)
        if new_items:
            enrich_count += len(new_items)
            _enrich(new_items, f"Vibe {feed['name'][:12]} ")

    enrich_secs = (datetime.now() - t_enrich).total_seconds()
    print(f"  丰富完成: {enrich_count} 条，耗时 {enrich_secs:.1f}s")

    # 4. 分类 + Vibe Coding 汇总 ───────────────────────────────────────────────
    print("\n[ 4/6 ] 分类（专业/实用、工具/作品）…")
    all_ai_items = (
        github["items"] + hackernews["items"] +
        producthunt["items"] + [it for f in rss for it in f["items"]]
    )

    for it in all_ai_items:
        it["category"] = classify_category(it)

    vibe_raw       = [it for it in all_ai_items if matches_vibe_coding(f"{it.get('title','')} {it.get('summary','')}")]
    vibe_from_ai   = _dedup(vibe_raw)
    for it in vibe_from_ai:
        if not it.get("kind"):
            it["kind"] = classify_vibe_kind(it)

    vibe_from_sources = [it for feed in vibe_sources for it in feed["items"]]
    vibe_coding = _dedup(vibe_from_ai + vibe_from_sources)
    for it in vibe_coding:
        if not it.get("kind"):
            it["kind"] = classify_vibe_kind(it)

    # 名称去重（跨源）
    before_ai   = len(all_ai_items)
    before_vibe = len(vibe_coding)
    vibe_coding  = _name_dedup(vibe_coding)
    after_vibe   = len(vibe_coding)
    print(f"  Vibe 名称去重: {before_vibe} → {after_vibe}（去除 {before_vibe - after_vibe} 个重复）")

    tool_cnt = sum(1 for it in vibe_coding if it.get("kind") == "工具")
    work_cnt = sum(1 for it in vibe_coding if it.get("kind") == "作品")
    print(f"  Vibe Coding: {len(vibe_coding)} 条（工具 {tool_cnt} / 作品 {work_cnt}）")
    pro_cnt  = sum(1 for it in all_ai_items if it.get("category") == "专业")
    cons_cnt = sum(1 for it in all_ai_items if it.get("category") == "实用")
    print(f"  AI Tools 分类: 专业 {pro_cnt} / 实用 {cons_cnt}")

    # 4b. 分类后修正 intro（category 未赋值时生成的 intro 可能有多种问题）
    # 触发重新生成的条件（任一即可）：
    #   1. use_case 仍是通用兜底（未按 category 细化）
    #   2. what 是英文（规则层无法翻译，新规则会置空）
    #   3. highlights / why_featured 含套话（新规则禁止）
    from intro_generator import _default_intro as _rule_intro
    _GENERIC_UC = {"AI 爱好者", "软件开发者", ""}
    fixed_cnt = 0
    for it in all_ai_items + vibe_coding:
        cat   = it.get("category", "")
        if not cat:
            continue   # 未分类条目跳过
        intro = it.get("intro") or {}
        uc    = intro.get("use_case", "")
        what  = intro.get("what", "")
        hl    = intro.get("highlights", [])
        why   = intro.get("why_featured", "")

        # 检测低分 HN 高亮（阈值 < 50 分 → 应清空）
        def _has_low_hn(highlights):
            for h in highlights:
                m = re.search(r'Hacker News (\d+) 分', h)
                if m and int(m.group(1)) < 50:
                    return True
            return False

        needs = (
            uc in _GENERIC_UC
            or (what and (_is_english_slogan(what) or _is_english_text(what)))
            or any(h in _BOILERPLATE_HL  for h in hl)
            or why in _BOILERPLATE_WHY
            or _has_low_hn(hl)
        )
        if needs:
            new_intro = _rule_intro(it)
            intro.update(new_intro)
            it["intro"] = intro
            fixed_cnt += 1
    if fixed_cnt:
        print(f"  修正 intro（英文/套话/use_case）: {fixed_cnt} 条")

    # 5. 精选评分 + 选出 TOP N ─────────────────────────────────────────────────
    print(f"\n[ 5/6 ] 精选评分（Top {FEATURED_COUNT}）…")

    # 对所有输出条目评分
    all_output_items = all_ai_items + [it for feed in vibe_sources for it in feed["items"]]
    for it in all_output_items:
        it.pop("_pre_images", None)
        it.pop("images", None)    # 清理旧格式字段
        it.pop("reason", None)    # 清理旧格式字段

    for it in vibe_coding:
        it.pop("_pre_images", None)
        it.pop("images", None)
        it.pop("reason", None)

    # feature_score 每次都重新计算（权重可能已调整，不能继承历史值）
    for it in all_ai_items + vibe_coding:
        it["feature_score"] = _score_feature(it)

    # ── 精选池准入：双重门槛 ─────────────────────────────────────────────────────
    # 门槛一：来源白名单（只有产品平台，讨论/文章/社区帖子一律不进）
    def _featured_src_ok(src: str) -> bool:
        sl = src.lower()
        return (
            "product hunt" in sl
            or "github" in sl
            or "hacker" in sl     # Hacker News / HN Show Vibe
        )

    # 门槛二：信息够做内容（有中文 what 或至少 1 条真实 highlight）
    #         + HN 来源额外要求：分数 >= 50 才能进精选
    def _featured_content_ok(it: dict) -> bool:
        intro = it.get("intro") or {}
        what  = intro.get("what", "")
        has_cn_what = bool(what and any(0x4E00 <= ord(c) <= 0x9FFF for c in what))
        has_hl      = bool(intro.get("highlights"))   # 非空列表即可
        if not (has_cn_what or has_hl):
            return False
        # HN 来源：历史缓存同样受阈值约束，<50 分一律拦截
        src   = it.get("source", "").lower()
        extra = it.get("extra", "")
        if "hacker" in src:
            m = re.search(r'(\d[\d,]*)\s*points?', extra, re.IGNORECASE)
            pts = int(m.group(1).replace(',', '')) if m else 0
            if pts < 50:
                return False
        return True

    seen_feat: set = set()
    pool_for_featured: list = []
    for it in all_ai_items + vibe_coding:
        u   = it.get("url", "")
        src = it.get("source", "")
        if u and u not in seen_feat and _featured_src_ok(src) and _featured_content_ok(it):
            seen_feat.add(u)
            pool_for_featured.append(it)

    pool_for_featured.sort(key=lambda x: x.get("feature_score", 0), reverse=True)

    # 来源多样性约束；不足 FEATURED_COUNT 就如实放几条，不用空壳补位
    source_counts: dict = {}
    featured: list = []
    for it in pool_for_featured:
        src = it.get("source", "unknown")
        cnt = source_counts.get(src, 0)
        if cnt < FEATURED_MAX_PER_SOURCE:
            source_counts[src] = cnt + 1
            featured.append(it)
        if len(featured) >= FEATURED_COUNT:
            break

    # 打印精选榜单
    intro_complete = sum(1 for it in all_output_items if _intro_completeness(it) >= 6)
    intro_partial  = sum(1 for it in all_output_items if 2 <= _intro_completeness(it) < 6)
    intro_limited  = sum(1 for it in all_output_items if _intro_completeness(it) < 2)
    print(f"  Intro 填充率: 齐全 {intro_complete} / 部分 {intro_partial} / 信息有限 {intro_limited}")
    print(f"  今日精选 Top {len(featured)}:")
    for rank, it in enumerate(featured, 1):
        name  = (it.get("tool_name") or it.get("title") or "")[:28]
        score = it.get("feature_score", 0)
        src   = it.get("source", "")[:12]
        print(f"    #{rank:2d}  {score:5.1f}分  [{src}]  {name}")

    # 6. 写 JSON + 更新索引 ──────────────────────────────────────────────────────
    print("\n[ 6/6 ] 写入 JSON …")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "date":           date_str,
        "generated_at":   datetime.now().isoformat(),
        "featured":       featured,
        "ai_tools": {
            "github":      github,
            "hackernews":  hackernews,
            "producthunt": producthunt,
            "rss":         rss,
        },
        "vibe_sources":   vibe_sources,
        "vibe_coding":    vibe_coding,
    }

    out_file = DATA_DIR / f"{date_str}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  已保存 → {out_file}")

    print("\n更新索引 …")
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
    print(f"  index.json 已更新（共 {len(dates)} 天记录）")

    elapsed = (datetime.now() - t0).total_seconds()
    total_ai = len(all_ai_items)
    print(f"\n{'='*56}")
    print(f"  构建完成！AI Tools: {total_ai} 条 | Vibe Coding: {len(vibe_coding)} 条")
    print(f"  精选: {len(featured)} 条 | 总耗时: {elapsed:.1f}s（丰富 {enrich_secs:.1f}s）")
    print(f"  预览: cd web && python -m http.server 8000")
    print(f"{'='*56}\n")


if __name__ == "__main__":
    main()
