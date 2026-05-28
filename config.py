# ── Vibe Coding 工具关键词（用于识别是否属于 Vibe Coding 范畴）──────────────
VIBE_CODING_KEYWORDS = [
    "cursor", "claude code", "copilot", "windsurf", "bolt.new", "v0.dev", " v0 ",
    "cline", "aider", "continue dev", "devin", "replit", "github copilot",
    "lovable", "tempo labs", "stackblitz", "pearai", "void editor",
    "tabnine", "codewhisperer", "supermaven", "zed editor", "claude dev",
    "opendevin", "swe-agent", "gpt-engineer", "codium", "cody",
]

# ── AI 关键词（至少一个命中才纳入）────────────────────────────────────────────
AI_KEYWORDS = [
    "ai", " llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "machine learning", "deep learning", "neural network", "transformer",
    "diffusion", "stable diffusion", "midjourney", "langchain", " rag",
    "embedding", "fine-tun", "inference", "pytorch", "tensorflow", "huggingface",
    "agent", "chatbot", "generative", "multimodal", "language model",
    "computer vision", " nlp", "llama", "mistral", "copilot", "code gen",
    "text-to-", "speech recognition", "prompt engineering", "vector db",
    "gguf", "ollama", "lora", "quantiz", "vllm", "tgi ", "triton",
]

# ── 「专业工具」关键词（面向开发者/研究/生产）──────────────────────────────────
PROFESSIONAL_KEYWORDS = [
    "framework", " sdk", " api", "library", "module", " package",
    "inference", "serving", "fine-tun", "fine tuning", " training",
    " rag", "vector", "embedding", "agent framework", "mlops",
    "benchmark", " eval", "deploy", "pipeline", "dataset",
    "quantiz", "gguf", "lora", "vllm", "triton", "cuda",
    "tokenizer", "pytorch", "tensorflow", "diffusers", "huggingface",
    "endpoint", "orchestrat", "open source model", "foundation model",
    "base model", "cli tool", "command-line", "devtool",
]

# ── 「实用工具」关键词（面向日常使用）──────────────────────────────────────────
CONSUMER_KEYWORDS = [
    " app", "chatbot", "assistant", "writing", "copywriting",
    "image gen", "video gen", "audio gen", "music gen",
    "design tool", "productivity", "extension", "plugin",
    "summariz", "transcrib", "translat", "no-code", "nocode",
    "browser ext", "chrome ext", "mobile", "ios app", "android",
    "saas", "web app", "dashboard", "automation tool",
    "content creat", "social media", "seo tool",
    "presentation", "slide deck", "diagram", "whiteboard",
]

# ── Vibe Coding「作品」识别关键词（用这些工具做出来的东西）─────────────────────
VIBE_WORK_KEYWORDS = [
    "show hn: i built", "show hn: i made", "show hn: i created", "show hn: i wrote",
    "built with cursor", "built with claude", "built with copilot", "built with bolt",
    "built with v0", "built with lovable", "built using cursor", "built using claude",
    "made with cursor", "made with claude", "vibe cod", "vibecod",
    "i built this", "i made this", "weekend project", "side project built",
    "one-shot", "claude generated", "cursor generated", "ai-generated app",
    "built in one day", "built in a day", "built in an evening",
]

# ── Vibe Coding 工具本身的名称（用于区分「工具」vs「作品」）──────────────────
VIBE_TOOL_NAMES = [
    "cursor", "claude code", "github copilot", "copilot", "windsurf",
    "bolt.new", "bolt new", "v0", "v0.dev", "cline", "aider",
    "lovable", "devin", "replit", "pearai", "void", "tabnine",
    "codewhisperer", "supermaven", "continue", "codium", "cody",
    "gpt-engineer", "opendevin", "swe-agent",
]

# ── 每源每次抓取条数（单次新鲜抓取）──────────────────────────────────────────
GITHUB_LIMIT = 25            # 每个 trending 周期（daily / weekly / monthly）
HACKERNEWS_LIMIT = 25        # 每次 HN 查询
PRODUCTHUNT_LIMIT = 25
RSS_LIMIT_PER_FEED = 20
GITHUB_SEARCH_LIMIT = 30     # GitHub Search API 每次查询

# ── 跨天累积设置 ──────────────────────────────────────────────────────────────
ACCUMULATE_DAYS = 14         # 合并近 N 天数据形成「近期热门池」

# 每源合并后最多保留的条目数
MAX_ITEMS_PER_SOURCE = 80

# ── 图片设置 ──────────────────────────────────────────────────────────────────
MAX_IMAGES_PER_ITEM = 5
IMAGE_DOWNLOAD_TIMEOUT = 12
MIN_IMAGE_SIZE_BYTES = 3000

# ── RSS 订阅源 ────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # 机器之心 公开 RSS 已下线；如有新地址可在此恢复
    # {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss"},
    {"name": "量子位", "url": "https://www.qbitai.com/feed"},
    {"name": "掘金",   "url": "https://juejin.cn/rss"},          # 官方 RSS，无需 RSSHub
    # 可继续添加，例如：
    # {"name": "AIbase",  "url": "https://www.aibase.com/rss.xml"},
]

# ── RSSHub 配置（第二、三档中文圈来源，可换成自建实例）──────────────────────
RSSHUB_BASE = "https://rsshub.app"   # 公共实例；自建时改为 http://localhost:1200

# ── Reddit 专用 User-Agent（必须自定义，否则被限流返回 429）──────────────────
REDDIT_USER_AGENT = "AI-Trending-Bot/1.0 (github.com/ai-trending; aggregator)"

# ── 各 Vibe Coding 来源每次抓取条数 ──────────────────────────────────────────
REDDIT_LIMIT      = 30    # 每个 subreddit
DEVTO_LIMIT       = 20    # 每个 tag
VIBE_RSSHUB_LIMIT = 20    # 每个 RSSHub / V2EX 源

# ── Vibe Coding 来源配置（三档，可逐个 enabled 开关）──────────────────────────
VIBE_SOURCES = [
    # ── 第一档：稳定主力源（免密钥，优先做扎实）──────────────────────────────
    {"id": "reddit_vibecoding",    "name": "Reddit r/vibecoding",    "tier": 1, "enabled": True,  "stable": True},
    {"id": "reddit_sideproject",   "name": "Reddit r/SideProject",   "tier": 1, "enabled": True,  "stable": True},
    {"id": "reddit_cursor",        "name": "Reddit r/cursor",        "tier": 1, "enabled": True,  "stable": True},
    {"id": "reddit_chatgptcoding", "name": "Reddit r/ChatGPTCoding", "tier": 1, "enabled": True,  "stable": True},
    {"id": "devto_ai",             "name": "Dev.to",                 "tier": 1, "enabled": True,  "stable": True},
    {"id": "hn_show_vibe",         "name": "HN Show Vibe",           "tier": 1, "enabled": True,  "stable": True},
    {"id": "showcase_v0",          "name": "v0.dev",                 "tier": 1, "enabled": False, "stable": False},   # 纯 JS 渲染，无法静态抓取
    {"id": "showcase_bolt",        "name": "bolt.new",               "tier": 1, "enabled": False, "stable": False},   # showcase URL 已 404
    {"id": "showcase_lovable",     "name": "Lovable",                "tier": 1, "enabled": False, "stable": False},   # showcase URL 已 404
    {"id": "showcase_replit",      "name": "Replit",                 "tier": 1, "enabled": False, "stable": False},   # showcase URL 已 404
    # ── 第二档：中文圈补充（经 RSSHub，质量不错但公共实例可能限流）────────────
    {"id": "rsshub_bilibili",      "name": "B站",                    "tier": 2, "enabled": True,  "stable": False},
    {"id": "rsshub_juejin",        "name": "掘金",                   "tier": 2, "enabled": True,  "stable": False},
    {"id": "rsshub_jike",          "name": "即刻",                   "tier": 2, "enabled": True,  "stable": False},
    {"id": "v2ex",                 "name": "V2EX",                   "tier": 2, "enabled": True,  "stable": True},
    # ── 第三档：可选不稳定源（默认关闭）──────────────────────────────────────
    # 注意：X/小红书/抖音路由在公共 RSSHub 实例通常不稳定；
    # X 官方 API 需付费；小红书/抖音反爬强，且内容多图文/短视频，格式不一定契合。
    # 如需启用，建议自建 RSSHub 实例并配置相应 cookie。
    # 抓不到属预期行为，绝不因此报错或用假图凑数。
    {"id": "rsshub_twitter",       "name": "X(Twitter)",             "tier": 3, "enabled": False, "stable": False},
    {"id": "rsshub_xiaohongshu",   "name": "小红书",                 "tier": 3, "enabled": False, "stable": False},
    {"id": "rsshub_douyin",        "name": "抖音",                   "tier": 3, "enabled": False, "stable": False},
]

# ── 精选功能权重（可在此调节，无需改代码）────────────────────────────────────────
FEATURE_WEIGHTS = {
    # 分类：实用工具大幅占主导；纯代码库/框架/SDK 给负分压低排名
    "category_实用":        40,
    "category_专业":       -10,
    # 来源：Product Hunt 是大众产品主场，大幅提权；GitHub 不再因"是代码托管"而加分
    "source_Product Hunt":  25,
    "source_HN_show":       10,
    "source_GitHub":         2,   # 大幅降低，不因托管在 GitHub 就自动占位
    "source_Dev.to":         5,
    "source_Reddit":         6,
    "source_V2EX":           3,
    # Stars / HN 热度：适度参考，不让高星仓库霸榜
    "stars_factor":         0.5,  # 旧值 3 → 0.5，大幅降低
    "hn_pts_factor":         1,
    # 内容质量
    "intro_complete":       10,
    "intro_partial":         4,
    "has_image":             5,
    "kind_作品":             6,
}
FEATURED_COUNT = 10            # 今日精选数量
FEATURED_MAX_PER_SOURCE = 3   # 同一来源最多占几席（保证多样性）

# ── DeepSeek AI 配置（从环境变量读 DEEPSEEK_API_KEY，不硬编码）──────────────────
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL    = "deepseek-chat"

# ── HTTP 请求公共配置 ──────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 15
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
