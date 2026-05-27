"""Structured intro generator: rule-based fallback + optional Claude Haiku.

Quality rules (both rule-based and Haiku versions must follow):
  what       -- must be fluent Chinese, or empty. Never output full English sentences.
  highlights -- only real data-backed highlights; no boilerplate badges;
                fewer is fine, empty list is fine.
  why_featured -- must be differentiated; leave empty if no real basis.
"""

import json
import os
import re


# -- English slogan / tagline detection ----------------------------------------

_FUNCTIONAL_WORDS = [
    'tool', 'tools', 'library', 'libraries', 'framework', 'frameworks',
    'app', 'application', 'platform', 'system', 'service', 'api', 'sdk', 'cli',
    'plugin', 'extension', 'addon', 'browser', 'interface', 'client',
    'helps', 'allows', 'enables', 'provides', 'lets you', 'let you',
    'built for', 'designed for', 'build', 'create', 'generate', 'analyze',
    'manage', 'organize', 'automate', 'deploy', 'run', 'connect', 'convert',
    'transform', 'search', 'translate', 'monitor', 'track', 'schedule',
    'integrate', 'collaborate', 'extract', 'process', 'summarize',
    'open source', 'open-source', 'local', 'self-hosted', 'self hosted',
    'for your', 'for the', 'that lets', 'that helps', 'that allows',
    'turns', 'gives', 'makes it',
]

# Word-boundary regex: prevents "app" matching "apple", "api" matching "capability"
_FUNC_PATTERN = re.compile(
    r'\b(?:' + '|'.join(re.escape(w) for w in _FUNCTIONAL_WORDS) + r')\b',
    re.IGNORECASE,
)

# Strip PH / HN page navigation artifacts from summary
_NAV_JUNK = re.compile(
    r'\s*(?:Discussion\s*\|\s*Link|Upvote\s*\||\|?\s*\d+\s*Comments?'
    r'|Get\s+it\s+on|Sign\s+in|Visit\s+Website)\s*$',
    re.IGNORECASE,
)


def _is_english_slogan(text):
    """Short English text with no functional words -> tagline/slogan."""
    if not text or len(text) < 5:
        return False
    ascii_count = sum(1 for c in text if ord(c) < 128)
    if ascii_count / len(text) < 0.85:
        return False
    if len(text) >= 120:
        return False
    if _FUNC_PATTERN.search(text):
        return False
    return True


def _is_english_text(text):
    """Text is primarily English (non-ASCII chars < 15%)."""
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) >= 128)
    return non_ascii / len(text) < 0.15


def _clean_summary(summary):
    """Remove navigation artifacts, return clean summary."""
    return _NAV_JUNK.sub('', summary).strip()


# -- Rule-based generator -------------------------------------------------------

def _default_intro(item):
    source   = item.get('source', '')
    extra    = item.get('extra', '')
    summary  = item.get('summary', '')
    category = item.get('category', '')

    summary_clean = _clean_summary(summary)

    # what: must be Chinese or empty -- never English
    what = ''
    if summary_clean:
        for sent in re.split(r'[。！？.!?\n]', summary_clean):
            sent = sent.strip()
            if len(sent) > 10 and not _is_english_slogan(sent) and not _is_english_text(sent):
                what = sent
                break
    # Pure rules cannot translate English; leave empty -- frontend will degrade to summary

    # Extract metrics from extra field
    sm = re.search(r'([\d,]+)\s*stars?\s*today', extra, re.IGNORECASE)
    pm = re.search(r'([\d,]+)\s*points?',        extra, re.IGNORECASE)
    cm = re.search(r'([\d,]+)\s*comments?',      extra, re.IGNORECASE)

    # highlights: ONLY numeric/data-backed highlights
    # Summary sentences are NOT used -- they produce low-quality fragments
    # BANNED: generic badges ("登上 PH 榜单", "GitHub Trending 广泛关注", etc.)
    highlights = []

    if sm:
        highlights.append('今日 GitHub 新增 ' + sm.group(1) + ' Stars')
    # Only show HN metrics when score is meaningful (>= 50 points)
    if pm:
        pts = int(pm.group(1).replace(',', ''))
        if pts >= 50:
            h = 'Hacker News ' + pm.group(1) + ' 分'
            if cm:
                h += '，' + cm.group(1) + ' 条讨论'
            highlights.append(h)

    # Empty list is fine -- "有几条写几条，没有就空着"

    # use_case: differentiated by category
    sl = summary_clean.lower()

    if category == '实用':
        if any(k in sl for k in ['meeting', '会议', 'calendar', '日程', 'email', '邮件', 'slack']):
            use_case = '职场人士'
        elif any(k in sl for k in ['writing', '写作', 'copywriting', 'blog', 'content', '文章', '文案']):
            use_case = '内容创作者'
        elif any(k in sl for k in ['music', '音乐', 'audio', '音频', 'podcast']):
            use_case = '音频创作者'
        elif any(k in sl for k in ['video', '视频', 'film', 'movie', 'clip']):
            use_case = '视频创作者'
        elif any(k in sl for k in ['design', '设计', ' ui ', ' ux ', 'image gen', '图片生成']):
            use_case = '设计师 / 创意工作者'
        elif any(k in sl for k in ['student', '学生', 'learn', '学习', 'education', '教育', 'course']):
            use_case = '学习者'
        elif any(k in sl for k in ['browser', '浏览器', 'extension', '插件', 'chrome']):
            use_case = '日常上网用户'
        elif any(k in sl for k in ['business', '企业', 'team', '团队', 'workflow', '工作流']):
            use_case = '职场 / 企业用户'
        elif any(k in sl for k in ['developer', '开发者', 'engineer', '程序员', 'coding', 'code']):
            use_case = '开发者'
        else:
            use_case = '普通用户'
    elif category == '专业':
        if any(k in sl for k in ['researcher', 'research', '研究', 'paper', 'academic']):
            use_case = 'AI 研究者'
        elif any(k in sl for k in ['enterprise', '企业', 'team', '团队']):
            use_case = '企业技术团队'
        else:
            use_case = '技术开发者'
    else:
        if any(k in sl for k in ['developer', 'engineer', '开发者', '工程师', '程序员']):
            use_case = '软件开发者'
        elif any(k in sl for k in ['researcher', 'research', '研究']):
            use_case = 'AI 研究者'
        else:
            use_case = 'AI 爱好者'

    # why_featured: data-backed only; empty string if no real basis
    # BANNED: "Product Hunt 今日精选产品", "近期 AI 社区热点", generic source badges
    # HN threshold: only meaningful if >= 50 points
    if sm:
        why = '今日 GitHub Trending，单日新增 ' + sm.group(1) + ' Stars'
    elif pm and int(pm.group(1).replace(',', '')) >= 50:
        why = 'Hacker News 热帖，' + pm.group(1) + ' 分'
        if cm:
            why += ' / ' + cm.group(1) + ' 条讨论'
    elif source in ('量子位', '机器之心'):
        why = source + ' 重点报道'
    else:
        why = ''   # no differentiating reason -> leave empty

    return {
        'what':         what,
        'highlights':   highlights,   # may be empty list
        'use_case':     use_case,
        'why_featured': why,          # may be empty string
    }


# -- Claude Haiku enhanced generator -------------------------------------------

def _claude_intro(item, api_key):
    try:
        import anthropic

        client   = anthropic.Anthropic(api_key=api_key)
        tool     = item.get('tool_name', '')
        src      = item.get('source', '')
        extra    = item.get('extra', '')
        summary  = item.get('summary', '')
        category = item.get('category', '')

        if category == '实用':
            use_case_hint = '面向普通用户/大众（例：职场人士/内容创作者/普通用户，不要笼统写开发者）'
        else:
            use_case_hint = '面向技术开发者/研究者'

        # Extract metrics for the prompt
        sm = re.search(r'([\d,]+)\s*stars?\s*today', extra, re.IGNORECASE)
        pm = re.search(r'([\d,]+)\s*points?',        extra, re.IGNORECASE)
        cm = re.search(r'([\d,]+)\s*comments?',      extra, re.IGNORECASE)
        signal_parts = []
        if sm:
            signal_parts.append('GitHub 今日新增 ' + sm.group(1) + ' Stars')
        if pm:
            s = 'HN ' + pm.group(1) + ' 分'
            if cm:
                s += ' / ' + cm.group(1) + ' 评论'
            signal_parts.append(s)
        signal_line = ('热度信号：' + ' / '.join(signal_parts) + '\n') if signal_parts else ''

        prompt = (
            '你是中文 AI 工具推荐编辑。请基于以下已知真实信息生成结构化中文介绍。\n\n'
            '硬性规则：\n'
            '1. what 必须是 1-2 句中文功能描述；如描述是英文且无法准确翻译，输出空字符串。\n'
            '2. highlights 只写有真实依据的亮点（数字/数据/产品特性）；'
            '套话（登上榜单、社区热议、Trending 等）一律禁止；'
            '亮点不足就少写，没有就输出空数组。\n'
            '3. why_featured 必须差异化；无差异化依据时输出空字符串，不要写套话。\n'
            '4. 严禁编造信息。\n\n'
            '工具名：' + tool + '\n'
            '来源：' + src + '（分类：' + category + '）\n'
            '描述：' + _clean_summary(summary)[:400] + '\n'
            + signal_line
            + '\n请输出 JSON（只输出 JSON，不加前缀或注释）：\n'
            '{\n'
            '  "what": "中文功能描述或空字符串",\n'
            '  "highlights": [],\n'
            '  "use_case": "' + use_case_hint + '，10字以内",\n'
            '  "why_featured": "差异化理由或空字符串"\n'
            '}'
        )

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$',          '', text)
        data = json.loads(text)

        what = str(data.get('what', '')).strip()
        # If Haiku still outputs English, discard
        if _is_english_slogan(what) or _is_english_text(what):
            what = ''

        # Filter English or boilerplate highlights
        raw_hl = data.get('highlights', [])
        highlights = []
        for h in raw_hl[:4]:
            h = str(h).strip()
            if h and not _is_english_text(h):
                highlights.append(h)

        why = str(data.get('why_featured', '')).strip()
        if _is_english_text(why):
            why = ''

        return {
            'what':         what[:200],
            'highlights':   highlights[:3],
            'use_case':     str(data.get('use_case', ''))[:60],
            'why_featured': why[:200],
        }
    except Exception:
        return _default_intro(item)


# -- Public entry point ---------------------------------------------------------

def generate_intro(item):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        return _claude_intro(item, api_key)
    return _default_intro(item)
