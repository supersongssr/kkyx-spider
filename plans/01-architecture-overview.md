# KKYX Spider — 系统架构总览

> **项目类型**: 生产级 Web 爬虫 + WordPress 内容同步引擎
> **目标站点**: kkyx.net（游戏资源分享网站）
> **核心架构**: 双阶段生产者-消费者 + 黄金三角状态机 + Fail-Fast 鉴权

---

## 1. 系统全景

```
┌─────────────────────────────────────────────────────────────┐
│                    Serial Scheduler (调度器)                   │
│                  core/parallel_scheduler.py                   │
└──────────────┬────────────────────────────────┬───────────────┘
               │                                │
       ┌───────▼────────┐              ┌───────▼────────┐
       │ Index Producer │              │ Post Consumer  │
       │   (索引发现)     │              │   (详情采集)     │
       └───────┬────────┘              └───────┬────────┘
               │                                │
       ┌───────▼────────┐              ┌───────▼────────┐
       │  无限额发现     │              │  配额受限处理    │
       │  (Unlimited)   │              │  (Quota Guard) │
       └───────┬────────┘              └───────┬────────┘
               │                                │
               └──────────────┬─────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   SQLite Database  │
                    │  + 黄金三角状态机    │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  WP Publisher      │
                    │  (WordPress 同步)   │
                    └───────────────────┘
```

## 2. 双阶段分离架构

| 阶段 | 职责 | 限制 | 登录要求 |
|------|------|------|----------|
| **Index Producer** | 扫描列表页，发现游戏 URL + 标题 + 日期 | 无限制 | ❌ 不需要 |
| **Post Consumer** | 进入详情页提取：正文、图片、下载链接、密码 | 配额受限 | ✅ 需要 |

**关键设计决策**: Producer 阶段"应收尽收"，不做任何人工限制。真正的配额控制发生在 Consumer 阶段。

## 3. 核心数据流

```
列表页 (HTML) ─→ [JavaScript 注入提取标题/URL/日期]
       │
       ├─→ [标题黑名单过滤] → 过滤 "查看"、"更多"、"详情" 等无效标题
       ├─→ [水印检查] → 增量模式下跳过旧内容
       └─→ [双层更新检测]
             ├─ Name Check: 标题变化？
             └─ Date Check: 发布日期变化？
                    │
                SQLite (upsert)
                    │
              ┌─────┴─────┐
              │ crawl_status │
              │ 0=待处理     │
              │ 1=已完成     │
              │ 2=需更新     │
              │ 3=永久放弃   │
              └─────┬─────┘
                    │
          Consumer 读取 (random_weight 排序)
                    │
         ┌──────────┴──────────┐
         │  详情提取 + 图片处理   │
         │  + 下载链接物理点击    │
         └──────────┬──────────┘
                    │
              Database 更新
                    │
         ┌──────────┴──────────┐
         │  WP Publisher 同步   │
         │  (CDN图片 + Erphpdown)│
         └─────────────────────┘
```

## 4. 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.10+ | 主语言 |
| 浏览器自动化 | Playwright (sync API) | 页面渲染 + 交互 |
| 反检测 | playwright-stealth | 隐藏自动化指纹 |
| 数据库 | SQLite3 | 状态机 + 游戏数据持久化 |
| HTML 解析 | BeautifulSoup4 | 正文图片处理 |
| HTTP 客户端 | requests / httpx | WP API 交互 |
| 依赖管理 | uv | 包管理 |
| 可选 | Pillow | 图片尺寸检测 |

## 5. 配置驱动设计

**核心原则**: 零 CLI 参数，完全配置文件驱动。

```
.env              → 敏感凭据 (账号密码、WP密钥、CDN地址)
config.py         → 业务逻辑 (URL、延迟、限额、数据库路径)
```

修改行为只需编辑 `config.py`，运行命令始终是 `uv run main.py`。

## 6. 项目目录结构 (理想目标)

```
kkyx-spider/
├── main.py                    # 入口点
├── config.py                  # 配置中心 (Single Source of Truth)
├── .env                       # 敏感凭据
├── .gitignore
├── pyproject.toml
├── auth/
│   └── auto_login.py          # 自动登录 + 会话刷新
├── core/
│   ├── parallel_scheduler.py  # 串行调度器 (Producer → Consumer)
│   ├── producer_consumer.py   # 生产者(索引扫描) + 消费者(详情提取)
│   ├── enhanced_scraper.py    # 增强型数据提取器
│   ├── db_manager.py          # 数据库管理 + 状态机
│   ├── auth.py                # 鉴权验证 (三态探针)
│   ├── browser_handler.py     # 浏览器指纹硬化
│   ├── html_image_processor.py # HTML图片处理 (Single Source of Truth)
│   ├── wp_publisher.py        # WordPress 同步引擎
│   └── log_formatter.py       # 彩色日志
├── utils/
│   └── media_handler.py       # 扁平化图片存储 + 双层去重
├── data/
│   ├── db/kkyx_spider.db      # SQLite 数据库
│   └── storage/               # 图片存储 ({md5}.ext)
├── auth/
│   └── state.json             # Playwright 会话持久化
├── plans/                     # 架构文档
└── debug/                     # 调试截图/HTML
```
