"""小红书发布稿生成器。

只给精选池条目调用，失败时返回 None（前端按钮自动隐藏）。

版本机制：
  - XIAOHONGSHU_PROMPT_VERSION 是缓存 key 的一部分。
  - 修改 prompt 时把版本号 bump：V1 → V2，build.py 用 "url||version" 做 key，
    旧 version 的缓存 key 不匹配，自动重新生成。
"""

import json
import os
import re
import time

# ── 提示词版本（改 prompt 时同步 bump，旧缓存自动失效）─────────────────────────
XIAOHONGSHU_PROMPT_VERSION = "V1"

XIAOHONGSHU_PROMPT_V1 = """\
你是小红书内容创作者。请基于以下真实信息写一篇小红书发布稿。

【严格规则】
1. 只能使用下方提供的真实信息，严禁编造功能、数据、价格或任何未提及的特性。
2. 严禁写"同类产品怎样""大多数工具如何"等依赖外部知识的对比内容。
3. 信息不足时正文可短于 200 字，宁短勿假。

【调性要求】
1. 第一人称（"我最近发现""最近在用"），开头用真实痛点或使用背景，不要"超级震惊""太绝了"式夸张开头。
2. 中段必须包含 1 个具体使用场景，从 use_case 字段提炼，结合 what 写实际操作感。
3. 结尾 1 句开放式互动问句（问读者的体验或看法）。
4. 每段最多 1 个 emoji，全文 emoji 总数不超过 4 个，不堆砌。
5. 禁用词：绝绝子、yyds、家人们、姐妹们、神器、逆天、封神、爆款、宝藏。

【已知信息】
工具名：{tool}
来源：{src}
功能描述（what）：{what}
亮点：{highlights}
适合人群（use_case）：{use_case}

【输出格式】只输出 JSON，不加任何前缀、后缀或注释：
{{
  "title": "18-22 字，带 1-2 个 emoji，钩子化但不标题党",
  "body": "200-400 字纯文本，段落间用换行分隔，分 3-4 段",
  "tags": ["不带#的关键词", "共 3-5 个"]
}}"""


def _build_prompt(item: dict) -> str:
    intro = item.get("intro") or {}
    tool  = (item.get("tool_name") or item.get("title") or "")[:80]
    src   = (item.get("source") or "")[:40]
    what  = (intro.get("what") or "")[:200]
    hl    = intro.get("highlights") or []
    uc    = (intro.get("use_case") or "")[:60]
    return XIAOHONGSHU_PROMPT_V1.format(
        tool       = tool       or "（未知）",
        src        = src        or "（未知）",
        what       = what       or "（无描述）",
        highlights = "、".join(hl[:3]) if hl else "（无）",
        use_case   = uc         or "（未知）",
    )


def generate_xiaohongshu_post(item: dict):
    """
    生成小红书发布稿。
    返回 {"title": str, "body": str, "tags": list[str]} 或 None。
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
        from config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

        client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        prompt = _build_prompt(item)

        last_exc = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(1.0 * attempt)
                resp = client.chat.completions.create(
                    model    = DEEPSEEK_MODEL,
                    messages = [{"role": "user", "content": prompt}],
                    max_tokens = 700,
                )
                text = resp.choices[0].message.content.strip()
                break
            except Exception as exc:
                last_exc = exc
                continue
        else:
            raise last_exc  # type: ignore[misc]

        # 清理 markdown 代码块包裹
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$",          "", text)
        data = json.loads(text)

        title = str(data.get("title", "")).strip()
        body  = str(data.get("body",  "")).strip()
        tags  = [str(t).strip().lstrip("#") for t in (data.get("tags") or []) if t]

        # 基本合法性校验
        if not title or not body:
            return None
        if len(title) < 5 or len(title) > 60:
            return None

        return {
            "title": title[:60],
            "body":  body[:900],
            "tags":  [t for t in tags if t][:5],
        }

    except Exception:
        return None
