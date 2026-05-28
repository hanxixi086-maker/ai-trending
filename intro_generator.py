"""Structured intro generator: rule-based fallback + optional DeepSeek.

Quality rules (both rule-based and DeepSeek versions must follow):
  what       -- must be fluent Chinese, or empty. Never output full English sentences.
  highlights -- only real data-backed highlights; no boilerplate badges;
                fewer is fine, empty list is fine.
  why_featured -- must be differentiated; leave empty if no real basis.
"""

import json
import os
import re
import time


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


# -- Generic-comparison filter -------------------------------------------------
# why_featured 不允许引用"同类工具/竞品/大多数产品/市面上多数/业内主流"等抽象对比对象，
# 除非源描述里明确出现了对比标记。

_GENERIC_COMPARE = re.compile(
    r'(同类|类似产品|类似工具|类似方案|竞品|大多数|普遍(?:依赖|采用|使用|存在|需要)'
    r'|多数(?:同类|闭源|开源|产品|工具|方案)|市面上|业内(?:主流|通常)?'
    r'|主流(?:的)?(?:工具|产品|方案)|大部分(?:同类|产品|工具|方案))'
)

_EXPLICIT_COMPARE_EN = re.compile(
    r'\b(?:unlike|versus|vs\.?|compared\s+to|different\s+from|alternative\s+to'
    r'|replaces?|instead\s+of|rather\s+than|better\s+than|in\s+contrast)\b',
    re.IGNORECASE,
)
_EXPLICIT_COMPARE_CN = re.compile(r'(?:区别于|不同于|相比|替代|而非|有别于|对标|与众不同)')


def _source_has_explicit_compare(item):
    """Source description explicitly names a comparison target."""
    src_text = ((item.get('summary') or '') + ' '
                + (item.get('tool_name') or '') + ' '
                + (item.get('extra') or ''))
    return bool(_EXPLICIT_COMPARE_EN.search(src_text)
                or _EXPLICIT_COMPARE_CN.search(src_text))


def _strip_generic_compare(why, item):
    """If why_featured has generic-comparison phrases but source has no explicit
    comparison marker, drop why_featured entirely (no fabricated rivalry)."""
    if not why:
        return ''
    if _GENERIC_COMPARE.search(why) and not _source_has_explicit_compare(item):
        return ''
    return why


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


# -- DeepSeek enhanced generator -----------------------------------------------

def _deepseek_intro(item, api_key, retries=2):
    """Call DeepSeek via OpenAI-compatible SDK. Falls back to rule-based on any error."""
    try:
        from openai import OpenAI
        from config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

        client   = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
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
            '3. why_featured 严格规则（重要）：\n'
            '   - 只能基于本条目自身的描述说明它为什么值得推荐；\n'
            '   - 严禁引入"同类工具/竞品/大多数产品/市面上多数/业内主流/传统方案"等抽象对比对象；\n'
            '   - 只有源描述里"明确"出现了对比对象（如 unlike X / vs Y / 区别于 Z / 替代 W），\n'
            '     才可以使用比较句式；否则禁止写"区别于…""相比…""不同于…""更…"等比较句；\n'
            '   - 无差异化依据时直接输出空字符串。\n'
            '4. 严禁编造信息，包括"业内通常如何""市面主流怎样"等想当然的常识陈述。\n\n'
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

        last_exc = None
        for attempt in range(retries + 1):
            try:
                if attempt > 0:
                    time.sleep(1.0 * attempt)   # 重试前等待，避免限流
                resp = client.chat.completions.create(
                    model=DEEPSEEK_MODEL,
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=400,
                )
                text = resp.choices[0].message.content.strip()
                break
            except Exception as e:
                last_exc = e
                continue
        else:
            raise last_exc

        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$',          '', text)
        data = json.loads(text)

        what = str(data.get('what', '')).strip()
        # If DeepSeek still outputs English, discard
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
        # 后置过滤：去除未经源描述支撑的对比套话
        why = _strip_generic_compare(why, item)

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
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if api_key:
        time.sleep(0.3)   # 简单间隔，避免触发限流
        return _deepseek_intro(item, api_key)
    return _default_intro(item)
