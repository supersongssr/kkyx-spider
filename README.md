# KKYX Spider

KKYX 网络爬虫 - Python 实现的生产级 Web 爬虫与 WordPress 内容同步引擎

## 📚 文档

- [配置说明](docs/CONFIGURATION.md) - 详细配置说明和使用指南

## 🚀 快速开始

### 1. 安装依赖

```bash
# 一键初始化（安装 uv、Python 依赖、Playwright 浏览器，并交互式填写凭据）
./init.sh

# 或手动安装
uv sync
uv run playwright install chromium
```

### 2. 配置凭据

所有配置都在 TOML 文件中（不再使用 `.env`）：

- `config.default.toml` — 默认值（提交到 Git，凭据留空）
- `.config.toml` — 本地覆盖（**不提交到 Git**，在此填写真实凭据）

```bash
# 编辑根目录 .config.toml，至少填写：
# [kkyx]
# username = "your_username"
# password = "your_password"
```

也可通过管理菜单交互式填写：

```bash
./run      # TUI 管理菜单 → 选择 1：初始化环境 (含交互式凭据配置)
```

### 3. 运行

```bash
uv run python3 main.py      # 直接运行全流程
./run                       # 或通过 TUI 管理菜单
```

### 4. 验证配置

```bash
./scripts/verify_config.sh
```

## 🖥️ 管理菜单与统一 CLI

`./run` 是整个项目的总入口（TUI 菜单）：↑/↓ 移动高亮，Enter 执行，数字键 1-9 快速执行，q 退出；
非交互环境自动回退为数字编号模式，也支持 `./run <序号>` 直达（如 `./run 2` 直接跑全流程）。

菜单的每一项都对应一个独立且唯一的 CLI 命令，可脱离菜单单独执行：

| 菜单项 | 独立 CLI 命令 | 说明 |
|--------|----------------|------|
| 初始化环境 | `bash init.sh` | 安装 uv / 依赖 / Playwright / 交互式凭据 |
| 自动化运行全流程 | `uv run python3 cli.py run` | 登录 + 索引 + 详情 + WP 同步 |
| 索引采集 (单进程) | `uv run python3 cli.py index` | 仅运行 Stage 1 (IndexProducer) |
| 详情采集 (单进程) | `uv run python3 cli.py post` | 仅运行 Stage 2 (PostConsumer，需有效会话) |
| Markdown 输出 (单操作) | `uv run python3 cli.py md` | 将已完成游戏导出为 Hugo 兼容 .md |
| WordPress 输出 (单操作) | `uv run python3 cli.py wp` | 仅运行 Stage 3 (WPPublisher) |
| 查看自动运行历史 | `uv run python3 cli.py history` | run/index/post/md/wp 的执行记录 |
| 数据库状态 | `uv run python3 cli.py status` | 表记录统计 + 采集状态分布 |
| Web 控制台 | `uv run python3 cli.py web` | Flask 数据库监控 |
| 清理缓存 | `uv run python3 cli.py clean` | 清理调试 HTML / 截图，不动数据库 |

`run/index/post/md/wp` 五个核心命令的每次执行都会写入 `run_history` 表
（状态：成功/失败/中断 + 耗时 + 摘要），可通过 `cli.py history` 随时回溯。

## 📁 项目结构

```
kkyx-spider/
├── .gitignore
├── README.md
├── pyproject.toml          # Python 项目配置
├── uv.lock                 # 依赖锁定
├── main.py                 # 全流程程序入口 (等价于 cli.py run)
├── cli.py                  # 统一 CLI 入口 (run/index/post/md/wp/history/...)
├── run                     # TUI 管理菜单总入口 (POSIX /bin/sh)
├── init.sh                 # 环境初始化 (uv/依赖/Playwright/凭据)
├── .config.toml            # 本地配置覆盖（含凭据，不提交到 Git）
├── config.default.toml     # 默认配置（凭据留空）
├── config/                 # 配置加载器包（import config）
│   └── __init__.py         #   读取 TOML 并暴露常量（代码，用户不编辑）
├── scripts/                # 辅助脚本
│   └── verify_config.sh    #   配置验证
├── core/                   # 核心模块
│   ├── parallel_scheduler.py  # 三阶段流水线调度器
│   ├── producer_consumer.py   # 索引生产者 + 详情消费者
│   ├── wp_publisher.py        # WordPress 同步发布
│   └── md_exporter.py         # Markdown (Hugo) 输出引擎
├── web/                    # Web 查看器
├── docs/                   # 项目文档
└── plans/                  # 架构设计
```

## 🔧 配置说明

配置层次（优先级从高到低）：
1. `.config.toml` - 本地覆盖（含凭据，不提交到 Git）
2. `config.default.toml` - 默认配置
3. （已移除 `.env`，所有配置统一到 TOML）

> `config` 包是加载器：读取上述 TOML 文件并深度合并，再暴露为 Python 常量，
> 业务代码通过 `config.XXX` 访问。详见 [docs/CONFIGURATION.md](docs/CONFIGURATION.md)。

## 📄 许可证

MIT License
