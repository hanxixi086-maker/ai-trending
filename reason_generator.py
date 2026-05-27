"""Recommendation reason generation (no-key default + optional Claude enhancement)."""

import os
import re


def _default_reason(item: dict) -> str:
    tool = item.get("tool_name", "")
    source = item.get("source", "")
    extra = item.get("extra", "")
    summary = item.get("summary", "")

    parts = []

    # What it does — first meaningful sentence from summary
    if summary:
        first = re.split(r"[。！？.!?]", summary.strip())[0].strip()
        if len(first) > 10:
            parts.append(first)

    # Signal from extra field
    sm = re.search(r"([\d,]+)\s*stars?\s*today", extra, re.IGNORECASE)
    pm = re.search(r"([\d,]+)\s*points?", extra, re.IGNORECASE)
    cm = re.search(r"([\d,]+)\s*comments?", extra, re.IGNORECASE)

    if sm:
        parts.append(f"今日在 GitHub 新增 {sm.group(1)} stars")
    elif pm:
        sig = f"在 Hacker News 获得 {pm.group(1)} 分"
        if cm:
            sig += f"、{cm.group(1)} 条评论"
        parts.append(sig)
    elif source in ("机器之心", "量子位", "InfoQ"):
        parts.append(f"由 {source} 报道")
    elif source == "Product Hunt":
        parts.append("登上 Product Hunt 今日榜单")

    if not parts:
        return f"{tool} 是一款值得关注的 AI 工具。"

    return "，".join(parts) + "。"


def _claude_reason(item: dict, api_key: str) -> str:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        tool   = item.get("tool_name", "")
        src    = item.get("source", "")
        extra  = item.get("extra", "")
        summary = item.get("summary", "")

        prompt = (
            "你是 AI 工具推荐编辑。请基于以下真实信息，用 1-2 句中文写推荐理由。\n"
            "严禁编造任何未在下面出现的功能或数据。\n\n"
            f"工具名：{tool}\n"
            f"来源：{src}\n"
            f"描述：{summary[:400]}\n"
            f"信号：{extra}\n\n"
            "只输出推荐理由文本，不加前缀或引号。"
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return _default_reason(item)


def generate_reason(item: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _claude_reason(item, api_key)
    return _default_reason(item)
