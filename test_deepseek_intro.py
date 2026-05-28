"""小范围测试：从今日 JSON 挑 3 条英文条目，对比规则引擎 vs DeepSeek 效果。"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from intro_generator import _default_intro, _deepseek_intro, _is_english_text

DATA_DIR = Path(__file__).parent / "web" / "data"
date_str = datetime.now().strftime("%Y-%m-%d")
today_json = DATA_DIR / f"{date_str}.json"

if not today_json.exists():
    print(f"找不到今日 JSON: {today_json}")
    print("请先运行 build.py 生成数据，或指定日期：python test_deepseek_intro.py 2026-05-27")
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        today_json = DATA_DIR / f"{date_str}.json"
    else:
        sys.exit(1)

api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    print("未检测到 DEEPSEEK_API_KEY 环境变量，请先设置：")
    print("  $env:DEEPSEEK_API_KEY = 'sk-...'")
    sys.exit(1)

data = json.loads(today_json.read_text(encoding="utf-8"))

# 收集所有条目，找英文 summary 的那些
all_items = []
tools = data.get("ai_tools", {})
for src in ("github", "hackernews", "producthunt"):
    all_items.extend(tools.get(src, {}).get("items", []))

# 优先挑 Product Hunt 的英文条目（最有代表性）
candidates = [
    it for it in all_items
    if _is_english_text(it.get("summary", ""))
    and it.get("summary", "").strip()
]
candidates.sort(key=lambda x: x.get("source", ""))

# 取 3 条：优先 PH，其次其他
ph = [it for it in candidates if "product" in it.get("source", "").lower()]
others = [it for it in candidates if "product" not in it.get("source", "").lower()]
sample = (ph[:2] + others[:1]) if len(ph) >= 2 else candidates[:3]

if not sample:
    print("没有找到英文 summary 的条目，可能今日数据已全部有中文描述。")
    sys.exit(0)

print(f"\n{'='*60}")
print(f"  DeepSeek Intro 小范围测试  ({date_str})")
print(f"  测试条目: {len(sample)} 条")
print(f"{'='*60}\n")

for i, item in enumerate(sample, 1):
    name    = item.get("tool_name") or item.get("title") or "(无名)"
    source  = item.get("source", "")
    summary = item.get("summary", "")[:120]
    extra   = item.get("extra", "")

    print(f"── 条目 {i}: {name}  [{source}]")
    print(f"   原始描述: {summary}")
    if extra:
        print(f"   热度数据: {extra[:80]}")

    print("\n   [规则引擎]")
    rule = _default_intro(item)
    print(f"   what:         {rule['what'] or '(空)'}")
    print(f"   highlights:   {rule['highlights'] or '[]'}")
    print(f"   use_case:     {rule['use_case']}")
    print(f"   why_featured: {rule['why_featured'] or '(空)'}")

    print("\n   [DeepSeek]")
    ds = _deepseek_intro(item, api_key)
    print(f"   what:         {ds['what'] or '(空)'}")
    print(f"   highlights:   {ds['highlights'] or '[]'}")
    print(f"   use_case:     {ds['use_case']}")
    print(f"   why_featured: {ds['why_featured'] or '(空)'}")
    print()
