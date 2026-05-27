# AI 热点 & Vibe Coding 日报

每日从 GitHub Trending、Hacker News、Product Hunt、Dev.to、Reddit、V2EX 等来源抓取 AI 热点，展示为可浏览的杂志感画廊网站。

---

## ⚡ 立即打开网站

**双击 `启动网站.bat`** → 浏览器自动打开 **http://localhost:8000**

> 关闭方式：直接关掉弹出的命令行窗口即可。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 立即看网站（已有数据）

直接双击项目根目录的 **`启动网站.bat`**，浏览器会自动打开。

端口占用时自动依次尝试 8000 → 8001 → 8080。

### 3. 更新今日数据

```bash
python build.py
```

抓取完成后刷新浏览器即可看到最新内容。

### 4. 冒烟测试（无需网络，验证页面正常）

```bash
python test_smoke.py
```

然后双击 `启动网站.bat`，验证两个 Tab、画廊、搜索、筛选均正常。

### 5.（可选）Claude 增强推荐理由

```bash
set ANTHROPIC_API_KEY=sk-ant-...    # Windows
python build.py
```

---

## 功能

- **🔥 热点 AI 工具** — GitHub / HN / Product Hunt / 量子位 / 掘金，含按来源筛选、专业/实用子分类
- **⚡ Vibe Coding 分享** — Reddit / Dev.to / HN Show HN / V2EX，含工具/作品子分类
- 每张卡片含真实产品图（最多 5 张轮播，可点击放大）+ 中文推荐理由
- 日期选择器查看历史存档；实时搜索；亮/暗色主题
- Alpine.js **本地内置**，无需外网 CDN，离线可用

---

## 目录结构

```
ai-trending/
├── 启动网站.bat         ← 双击打开网站
├── build.py             # 主构建脚本（每日运行）
├── config.py            # 所有来源、数量、关键词配置
├── sources.py           # AI Tools 数据抓取
├── vibe_sources.py      # Vibe Coding 专属来源
├── image_fetcher.py     # 图片抓取与本地缓存
├── reason_generator.py  # 推荐理由生成
├── test_smoke.py        # 冒烟测试（合成数据）
├── requirements.txt
└── web/
    ├── index.html       # 主页面
    ├── app.js           # Alpine.js 逻辑
    ├── style.css        # 样式
    ├── alpine.min.js    # Alpine.js 本地版（离线可用）
    └── data/
        ├── index.json           # 日期索引（自动维护）
        ├── YYYY-MM-DD.json      # 每日数据存档
        └── images/YYYY-MM-DD/  # 下载的产品图片
```

---

## Vibe Coding 来源配置（config.py）

`VIBE_SOURCES` 列表里每个来源有 `enabled` 字段，可单独开关：

| 档位 | 来源 | 默认 | 说明 |
|------|------|------|------|
| 第一档 | Reddit（4 个子版块） | ✅ | 需 OAuth；403 时自动跳过 |
| 第一档 | Dev.to | ✅ | 免密钥，稳定 |
| 第一档 | HN Show Vibe | ✅ | 免密钥，稳定 |
| 第一档 | Showcase（v0/bolt/Lovable/Replit） | ❌ | 纯 JS 渲染，已关闭 |
| 第二档 | B站 / 掘金 / 即刻（RSSHub） | ✅ | 公共实例不稳，失败自动跳过 |
| 第二档 | V2EX | ✅ | 官方 RSS，稳定 |
| 第三档 | X / 小红书 / 抖音 | ❌ | 默认关闭，需自建 RSSHub |

---

## 自动定时构建

### Windows 任务计划程序（每天 08:00）

```powershell
$action  = New-ScheduledTaskAction -Execute "python" -Argument "D:\Projects\ai-trending\build.py" -WorkingDirectory "D:\Projects\ai-trending"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "AI-Trending-Daily" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
```

### Mac / Linux cron（每天 08:00）

```bash
crontab -e
# 添加：
0 8 * * * cd /path/to/ai-trending && python build.py >> /tmp/ai-trending.log 2>&1
```

---

## GitHub Pages 部署

1. 推送项目到 GitHub 仓库
2. Settings → Pages → Source 选 `main` 分支，目录选 `/web`
3. 每次 `python build.py` 后将 `web/data/` 变更 commit & push
4. 访问 `https://<你的用户名>.github.io/<仓库名>/`

---

## 常见问题

**Q: 双击 bat 后浏览器没打开？**
A: 手动访问 http://localhost:8000，或 http://localhost:8001

**Q: 页面空白？**
A: 确认先运行过 `python build.py` 生成了 `web/data/YYYY-MM-DD.json`；或先跑 `python test_smoke.py` 生成测试数据。

**Q: 想更换 RSSHub 为自建实例？**
A: 修改 `config.py` 中的 `RSSHUB_BASE = "http://你的实例地址:1200"`
