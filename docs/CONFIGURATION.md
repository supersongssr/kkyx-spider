# KKYX Spider 配置系统

## 配置层次结构（优先级从高到低）

```
1. .config.toml              本地覆盖配置（含凭据，可选，不提交到 Git）
2. config.default.toml      默认配置（TOML，提交到 Git）
```

> 已移除 `.env`。所有配置（包括账号密码等敏感凭据）统一在 TOML 文件中管理。
> `config` 包（`config/__init__.py`）是**加载器**：读取上述 TOML 文件并深度合并，
> 再把结果暴露为 Python 模块常量（如 `config.BASE_URL`），业务代码通过 `config.XXX` 访问。

---

## 配置文件说明

### 1. `config.default.toml` - 默认配置
- **用途**: 定义所有配置项的默认值，带行内注释说明字段含义
- **凭据**: 账号 / 密码 / 密钥一律**留空**（`username = ""`）
- **版本控制**: ✅ 提交到 Git
- **修改场景**: 需要团队协作的默认值变更

### 2. `.config.toml` - 本地覆盖配置
- **用途**: 覆盖默认值，并填写真实凭据
- **位置**: 项目根目录
- **包含**: 至少填写 `[kkyx]` 的 `username` / `password`；其余按需覆盖（深度合并）
- **版本控制**: ❌ 在 `.gitignore` 中，不提交

---

## 必填配置（写在 `.config.toml`）

```toml
[kkyx]
username = "your_username"   # KKYX 网站用户名（必需）
password = "your_password"   # KKYX 网站密码（必需）
```

## 可选配置（写在 `.config.toml`）

```toml
# WordPress 同步（不用 WP 同步可留空）
[wordpress]
base_url = "https://your-wordpress-site.com"
username = "your_wp_username"
app_password = "your application password"

# CDN
[cdn]
base_url = "https://your-cdn-domain.com/kkyx"
```

---

## 完整 `.config.toml` 示例

```toml
# 凭据
[kkyx]
username = "your_username"
password = "your_password"

[wordpress]
base_url = "https://your-wordpress-site.com"
username = "your_wp_username"
app_password = "your application password"

[cdn]
base_url = "https://your-cdn-domain.com/kkyx"

# 覆盖安全限制
[safety]
index_scan_page_limit = 50    # 每次运行扫描更多页面
max_posts_per_run = 20         # 每次运行处理更多帖子

# 覆盖调试设置
[debug]
debug_mode = false             # 生产环境关闭调试
log_level = "INFO"
```

---

## 深度合并示例

`.config.toml` 与 `config.default.toml` 是**深度合并**：只覆盖你写的键，其余保留默认。

**config.default.toml（默认）**:
```toml
[safety]
index_scan_page_limit = 2
max_posts_per_run = 5
```

**.config.toml（覆盖）**:
```toml
[safety]
index_scan_page_limit = 50
```

**最终生效**:
```toml
[safety]
index_scan_page_limit = 50    # 来自 .config.toml
max_posts_per_run = 5         # 来自 config.default.toml（保留）
```

嵌套子表同样按键合并。例如 `[wordpress.category_map]` 在 `.config.toml`
中只写一个分类，会与默认映射合并，而**不会**整体替换。

---

## 类型说明

| TOML 写法 | 加载后的 Python 类型 | 示例 |
|---|---|---|
| `key = 5` | `int` | `POST_CRAWL_BATCH_LIMIT = 5` |
| `key = true` | `bool` | `DEBUG_MODE = True` |
| `key = "5.00"` | `str` | `WP_ICE_PRICE = "5.00"` |
| `key = ["a", "b"]` | `list`（标签/关键词） | `WP_FIXED_TAGS = ["KKYX"]` |
| `key = [3, 7]`（延迟范围） | `tuple`（加载器自动转换） | `INDEX_PAGE_DELAY = (3, 7)` |
| `[table]` 子表 | `dict` | `WP_CATEGORY_MAP = {...}` |

> 注：`[delays]` 下的延迟范围数组（如 `index_page_delay`）会被加载器
> 转成 `tuple`，以便直接传给 `random.uniform(*INDEX_PAGE_DELAY)`。

---

## 新建环境配置步骤

1. **初始化（推荐）**:
   ```bash
   ./init.sh    # 安装依赖 + 交互式填写凭据
   ```

2. **或手动配置**:
   在项目根目录创建 `.config.toml`，至少填写 `[kkyx]` 的 `username` / `password`。

3. **运行**:
   ```bash
   uv run main.py
   ```

---

## 配置验证

```bash
# 1. 运行验证脚本（可从任意目录调用）
./scripts/verify_config.sh

# 2. 快速检查关键常量
uv run python -c "import config; print(f'BASE_URL: {config.BASE_URL}'); print(f'USERNAME: {config.USERNAME}')"
```

---

## Web 查看器凭据

`web/app.py` 的登录凭据优先级：
1. 真实环境变量 `WEB_VIEWER_USER` / `WEB_VIEWER_PASSWORD`（可选，用于给 Web 控制台单独设密码）
2. `.config.toml` 中的 `[kkyx]` 凭据（默认）
3. `admin` / `admin_kkyx`（兜底）

---

## 已弃用的配置方式

以下配置方式已移除，不再支持：
- ❌ `.env` 环境变量文件（凭据已迁移到 `.config.toml`）
- ❌ `config.json` / `config.test.json` - 旧 JSON 配置
- ❌ `CONFIG_PATH` 环境变量
- ❌ `.config.py` / `config_overrides` 字典 - 旧 Python 覆盖机制

---

## 安全注意事项

1. **永远不要提交** `.config.toml` 到 Git（已在 `.gitignore`）
2. **定期更换** WordPress Application Password
3. **使用强密码** 保护 KKYX 账号
