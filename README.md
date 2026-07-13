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
./run.sh    # 选择 4：交互式修改凭据
```

### 3. 运行

```bash
uv run main.py              # 直接运行
./run.sh            # 或通过管理菜单
```

### 4. 验证配置

```bash
./scripts/verify_config.sh
```

## 📁 项目结构

```
kkyx-spider/
├── .gitignore
├── README.md
├── pyproject.toml          # Python 项目配置
├── uv.lock                 # 依赖锁定
├── main.py                 # 程序入口
├── .config.toml            # 本地配置覆盖（含凭据，不提交到 Git）
├── config.default.toml     # 默认配置（凭据留空）
├── config/                 # 配置加载器包（import config）
│   └── __init__.py         #   读取 TOML 并暴露常量（代码，用户不编辑）
├── scripts/                # 辅助脚本
│   └── verify_config.sh    #   配置验证
├── core/                   # 核心模块
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
