"""
临时验证脚本：对 AVTR-1、Kept、Agent Launch 三条
绕过缓存直接调用新版 _deepseek_intro，检查 why_featured 是否干净。
"""
import json
import os
import sys

DATA = r"D:\Projects\ai-trending\web\data\2026-05-27.json"

TARGET_URLS = {
    "https://www.producthunt.com/products/avaturn-live-2":           "AVTR-1",
    "https://www.producthunt.com/products/kept-ai-on-your-local-conversations": "Kept",
    "https://news.ycombinator.com/item?id=48278148":                 "Agent Launch",
}

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("请先设置 DEEPSEEK_API_KEY 环境变量")

    sys.path.insert(0, r"D:\Projects\ai-trending")
    from intro_generator import _deepseek_intro

    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    # 收集所有条目
    items = []
    for section in data.get("ai_tools", {}).values():
        items.extend(section.get("items", []))
    items.extend(data.get("vibe_coding", {}).get("items", []))

    found = {url: None for url in TARGET_URLS}
    for it in items:
        u = it.get("url", "")
        if u in found:
            found[u] = it

    for url, label in TARGET_URLS.items():
        it = found[url]
        if it is None:
            print(f"\n[!] 未找到: {label} ({url})")
            continue

        print(f"\n{'='*60}")
        print(f"  {label}  [{it.get('source','')}]")
        print(f"  summary: {it.get('summary','')[:100]}")
        print(f"  extra  : {it.get('extra','')}")
        print(f"  -- 重新调用 DeepSeek --")

        new_intro = _deepseek_intro(it, api_key)
        print(f"  what       : {new_intro.get('what','')}")
        print(f"  highlights : {new_intro.get('highlights','')}")
        print(f"  use_case   : {new_intro.get('use_case','')}")
        print(f"  why_featured: {new_intro.get('why_featured','')}")

        # 额外验证：_featured_content_ok 对 Agent Launch 是否拦截
        if label == "Agent Launch":
            import re
            extra = it.get("extra", "")
            m = re.search(r'(\d[\d,]*)\s*points?', extra, re.IGNORECASE)
            pts = int(m.group(1).replace(',', '')) if m else 0
            print(f"\n  [HN 阈值检查] 分数={pts}  →  "
                  f"{'⛔ 被精选池拦截 ✓' if pts < 50 else '✅ 通过（≥50分）'}")

if __name__ == "__main__":
    main()
