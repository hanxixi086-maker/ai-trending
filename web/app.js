/* Alpine.js 主组件 —— 加载顺序：app.js 先于 Alpine（Alpine 带 defer） */

const PLACEHOLDER_SVG = (() => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="225" viewBox="0 0 400 225">
    <rect width="400" height="225" fill="#1e1e2e"/>
    <text x="200" y="118" text-anchor="middle" fill="#555577" font-family="system-ui,sans-serif" font-size="13">图片加载失败</text>
  </svg>`;
  return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`;
})();

function srcClass(source) {
  if (!source) return '';
  const s = source.toLowerCase().replace(/\s+/g, '-');
  if (s.includes('github'))                          return 'src-GitHub';
  if (s.includes('hacker'))                          return 'src-HN';
  if (s.includes('product'))                         return 'src-PH';
  if (source.includes('机器之心'))                    return 'src-机器之心';
  if (source.includes('量子位'))                      return 'src-量子位';
  if (s.includes('reddit'))                          return 'src-Reddit';
  if (s.includes('dev.to'))                          return 'src-Devto';
  if (s.includes('v2ex'))                            return 'src-V2EX';
  if (source.includes('掘金'))                        return 'src-掘金';
  if (source.includes('b站') || s.includes('bili'))  return 'src-B站';
  if (source.includes('即刻'))                        return 'src-即刻';
  if (s.includes('v0.dev'))                          return 'src-v0dev';
  if (s.includes('bolt'))                            return 'src-boltNew';
  if (s.includes('lovable'))                         return 'src-Lovable';
  if (s.includes('replit'))                          return 'src-Replit';
  return 'src-RSS';
}

document.addEventListener('alpine:init', () => {
  Alpine.data('app', () => ({
    // ── 状态 ──────────────────────────────────────────────────────────────
    dark:        localStorage.getItem('darkMode') !== 'false',
    loading:     true,
    globalErr:   '',
    dates:       [],
    selDate:     '',
    tab:         'ai',
    q:           '',
    srcFilter:   '全部',
    catFilter:   '全部',
    kindFilter:  '全部',
    genAt:       '',
    aiItems:     [],
    vibeItems:   [],
    featured:    [],
    srcErrors:   [],
    // 灯箱（单图放大）
    lb:          { open: false, img: '' },
    // 复制反馈（key: item.url → true/false）
    copyTexts:   {},
    // 小红书文案复制反馈
    xhsCopyTexts: {},
    placeholderSvg: PLACEHOLDER_SVG,

    // ── 生命周期 ──────────────────────────────────────────────────────────
    async init() {
      try {
        const idx = await fetch('data/index.json').then(r => r.json());
        this.dates = idx.dates || [];
        if (this.dates.length) {
          this.selDate = this.dates[0];
          await this.loadDate(this.selDate);
        } else {
          this.globalErr = '尚无数据，请先运行 python build.py';
          this.loading = false;
        }
      } catch (e) {
        this.globalErr = '无法加载 data/index.json — 请用 python -m http.server 访问，或先运行 python build.py';
        this.loading = false;
      }
    },

    // ── 数据加载 ──────────────────────────────────────────────────────────
    async loadDate(date) {
      this.loading    = true;
      this.globalErr  = '';
      this.srcErrors  = [];
      this.aiItems    = [];
      this.vibeItems  = [];
      this.featured   = [];
      this.srcFilter  = '全部';
      this.catFilter  = '全部';
      this.kindFilter = '全部';
      this.q = '';
      this.copyTexts    = {};
      this.xhsCopyTexts = {};
      try {
        const data = await fetch(`data/${date}.json`).then(r => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        });
        this.genAt = data.generated_at
          ? new Date(data.generated_at).toLocaleString('zh-CN', { hour12: false })
          : '';
        this.featured = data.featured || [];
        const tools = data.ai_tools || {};
        if (tools.github?.error)      this.srcErrors.push(`GitHub 源异常：${tools.github.error}`);
        this.aiItems.push(...(tools.github?.items     || []));
        if (tools.hackernews?.error)  this.srcErrors.push(`Hacker News 源异常：${tools.hackernews.error}`);
        this.aiItems.push(...(tools.hackernews?.items || []));
        if (tools.producthunt?.error) this.srcErrors.push(`Product Hunt 源异常：${tools.producthunt.error}`);
        this.aiItems.push(...(tools.producthunt?.items || []));
        for (const feed of (tools.rss || [])) {
          if (feed.error) this.srcErrors.push(`RSS「${feed.name}」源异常：${feed.error}`);
          this.aiItems.push(...(feed.items || []));
        }
        this.vibeItems = data.vibe_coding || [];
      } catch (e) {
        this.globalErr = `加载 ${date} 数据失败：${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    // ── 计算属性 ──────────────────────────────────────────────────────────
    get sourceTabs() {
      const srcs = new Set(this.aiItems.map(i => i.source).filter(Boolean));
      return ['全部', ...srcs];
    },

    get filteredAi() {
      let items = this.aiItems;
      if (this.srcFilter !== '全部')
        items = items.filter(i => i.source === this.srcFilter);
      if (this.catFilter !== '全部')
        items = items.filter(i => i.category === this.catFilter);
      if (this.q.trim()) {
        const q = this.q.trim().toLowerCase();
        items = items.filter(i =>
          (i.title     || '').toLowerCase().includes(q) ||
          (i.tool_name || '').toLowerCase().includes(q) ||
          (i.summary   || '').toLowerCase().includes(q) ||
          (i.intro?.what || '').toLowerCase().includes(q)
        );
      }
      return items;
    },

    get filteredVibe() {
      let items = this.vibeItems;
      if (this.kindFilter !== '全部')
        items = items.filter(i => i.kind === this.kindFilter);
      if (this.q.trim()) {
        const q = this.q.trim().toLowerCase();
        items = items.filter(i =>
          (i.title     || '').toLowerCase().includes(q) ||
          (i.tool_name || '').toLowerCase().includes(q) ||
          (i.summary   || '').toLowerCase().includes(q) ||
          (i.intro?.what || '').toLowerCase().includes(q)
        );
      }
      return items;
    },

    get vibeToolCount() { return this.vibeItems.filter(i => i.kind === '工具').length; },
    get vibeWorkCount()  { return this.vibeItems.filter(i => i.kind === '作品').length; },

    // ── 操作 ──────────────────────────────────────────────────────────────
    toggleTheme() {
      this.dark = !this.dark;
      localStorage.setItem('darkMode', this.dark);
    },

    openLb(imgUrl) {
      if (!imgUrl) return;
      this.lb = { open: true, img: imgUrl };
    },

    async copyItem(item) {
      const intro = item.intro || {};
      const name  = item.tool_name || item.title || '';

      // 过滤掉空值和"信息有限"，避免中英混杂的半成品文案
      const isUsable  = v => v && v !== '信息有限';
      // 含中文字符才算可用中文内容（避免把英文 summary 当 what 输出）
      const isChinese = s => s && /[一-鿿]/.test(s);

      // what：只用中文内容；intro.what 为空且 summary 是英文时，整行跳过
      const what = (isUsable(intro.what) && isChinese(intro.what)) ? intro.what
                 : (isUsable(item.summary) && isChinese(item.summary) ? item.summary : '');

      // highlights：只保留有效条目
      const hlLines = (intro.highlights || [])
        .filter(h => isUsable(h))
        .map(h => `· ${h}`);

      const useCase  = isUsable(intro.use_case)     ? intro.use_case     : '';
      const whyFeat  = isUsable(intro.why_featured)  ? intro.why_featured : '';

      // 只拼接有内容的行，不留空行
      const lines = [`【${name}】`];
      if (what)              lines.push(`是什么：${what}`);
      if (hlLines.length)    { lines.push('亮点：'); lines.push(...hlLines); }
      if (useCase)           lines.push(`适合：${useCase}`);
      if (whyFeat)           lines.push(`推荐理由：${whyFeat}`);
      lines.push(`链接：${item.url}`);
      const text = lines.join('\n');

      const key = item.url;
      try {
        await navigator.clipboard.writeText(text);
      } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      this.copyTexts = { ...this.copyTexts, [key]: true };
      setTimeout(() => {
        this.copyTexts = { ...this.copyTexts, [key]: false };
      }, 2000);
    },

    async copyXhs(item) {
      const xhs = item.xiaohongshu_post;
      if (!xhs || !xhs.title || !xhs.body) return;
      const tagLine = (xhs.tags || []).map(t => `#${t}`).join(' ');
      const text    = `${xhs.title}\n\n${xhs.body}\n\n${tagLine}`.trim();
      const key     = item.url;
      try {
        await navigator.clipboard.writeText(text);
      } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      this.xhsCopyTexts = { ...this.xhsCopyTexts, [key]: true };
      setTimeout(() => {
        this.xhsCopyTexts = { ...this.xhsCopyTexts, [key]: false };
      }, 2000);
    },

    srcClass,

    catBtnClass(val) {
      if (this.catFilter !== val) return 'sub-btn';
      if (val === '专业') return 'sub-btn active-pro';
      if (val === '实用') return 'sub-btn active-cons';
      return 'sub-btn active-all';
    },

    kindBtnClass(val) {
      if (this.kindFilter !== val) return 'sub-btn';
      if (val === '工具') return 'sub-btn active-tool';
      if (val === '作品') return 'sub-btn active-work';
      return 'sub-btn active-all';
    },
  }));
});
