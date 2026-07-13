# KKYX Spider

KKYX 网络爬虫 - Python 实现的生产级 Web 爬虫与 WordPress 内容同步引擎

## 📚 文档

- [配置说明](docs/CONFIGURATION.md) - 详细配置说明和使用指南
- [迁移指南](docs/MIGRATION.md) - 从旧版本迁移的步骤
- [重构报告](docs/REFACTORING_REPORT.md) - 配置系统重构报告
- [快速参考](docs/CONFIG_QUICK_REFERENCE.txt) - 配置快速参考卡片
- [完成总结](docs/REFACTORING_COMPLETE.txt) - 重构完成总结
- [Git 提交指南](docs/GIT_COMMIT_GUIDE.md) - Git 提交建议

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置环境

```bash
# 1. 配置敏感信息（编辑 .env 文件）
# KKYX_USER=your_username
# KKYX_PWD=your_password

# 2. 可选：创建本地配置覆盖（编辑 .config.py 文件）
# config_overrides = {
#     "safety": {
#         "index_scan_page_limit": 10,
#     }
# }
```

### 3. 首次运行

```bash
# 1. 首次登录（生成 state.json）
python3 .auth/auto_login.py

# 2. 运行爬虫
uv run main.py
```

### 4. 验证配置

```bash
# 运行配置验证脚本
./verify_config.sh
```

## 📁 项目结构

```
kkyx-spider/
├── config.py              # 默认配置文件
├── .config.py            # 本地配置覆盖（可选）
├── .env                  # 敏感凭据（不提交到 Git）
├── main.py               # 程序入口
├── core/                 # 核心模块
├── web/                  # Web 查看器
├── docs/                 # 项目文档
└── .data/                # 私有数据（不提交到 Git）
```

## 🔧 配置说明

详细配置说明请参考 [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

配置层次（优先级从高到低）：
1. `.config.py` - 本地配置覆盖（可选）
2. `config.py` - 默认配置
3. `.env` - 敏感凭据

## 📄 许可证

MIT License
