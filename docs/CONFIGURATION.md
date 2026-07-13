# KKYX Spider 配置系统

## 配置层次结构（优先级从高到低）

```
1. .config.py (本地覆盖配置，可选)
2. config.py (默认配置，本文件)
3. .env (敏感凭据，环境变量)
```

---

## 配置文件说明

### 1. `config.py` - 默认配置
- **用途**: 定义所有默认配置项
- **包含**: 目标站点、管道设置、安全限制、调试选项、数据库路径等
- **版本控制**: ✅ 提交到 Git
- **修改**: 需要团队协作的配置修改

### 2. `.config.py` - 本地覆盖配置
- **用途**: 覆盖默认配置，适应本地环境
- **包含**: 环境特定的设置（如页面限制、调试级别等）
- **版本控制**: ❌ 在 `.gitignore` 中，不提交
- **修改**: 个人开发环境定制

### 3. `.env` - 敏感凭据
- **用途**: 存储敏感信息和账号密码
- **包含**: KKYX账号、WordPress API密钥、CDN地址等
- **版本控制**: ❌ 在 `.gitignore` 中，不提交
- **修改**: 个人环境设置

---

## 必需的 .env 参数

```bash
# KKYX 网站登录凭据（必需）
KKYX_USER=your_username
KKYX_PWD=your_password
```

---

## 可选的 .env 参数

```bash
# WordPress 配置
WP_BASE_URL=https://your-wordpress-site.com
WP_USERNAME=your_wp_username
WP_APP_PASSWORD="your_application_password"

# CDN 配置
CDN_BASE_URL=https://your-cdn-domain.com/kkyx
```

---

## .config.py 示例

创建 `.config.py` 文件来覆盖默认配置：

```python
config_overrides = {
    # 覆盖安全限制
    "safety": {
        "index_scan_page_limit": 50,  # 每次运行扫描更多页面
        "max_posts_per_run": 20,       # 每次运行处理更多帖子
    },

    # 覆盖调试设置
    "debug": {
        "debug_mode": False,          # 生产环境关闭调试
        "log_level": "INFO",
    },

    # 覆盖 WordPress 同步设置
    "wordpress": {
        "sync_batch_limit": 10,
        "sync_min_delay": 2,
        "sync_max_delay": 5,
    },
}
```

---

## 配置加载优先级示例

假设有以下配置：

**config.py (默认)**:
```python
"safety": {
    "index_scan_page_limit": 2,
    "max_posts_per_run": 5,
}
```

**.config.py (覆盖)**:
```python
"safety": {
    "index_scan_page_limit": 50,
}
```

**最终生效的配置**:
```python
"safety": {
    "index_scan_page_limit": 50,  # 从 .config.py 覆盖
    "max_posts_per_run": 5,       # 从 config.py 保留
}
```

---

## 已删除的配置方式

以下配置方式已弃用并移除：
- ❌ `config.test.json` - JSON 配置文件
- ❌ `config.json` - JSON 配置文件
- ❌ `CONFIG_PATH` 环境变量

---

## 新建环境配置步骤

1. **创建本地配置覆盖**:
   在项目根目录创建 `.config.py` 文件，参考以下格式：
   
   ```python
   config_overrides = {
       "safety": {
           "index_scan_page_limit": 50,
       },
   }
   ```

2. **配置 .env**:
   ```bash
   # 添加敏感凭据
   KKYX_USER=your_username
   KKYX_PWD=your_password
   ```

3. **运行爬虫**:
   ```bash
   uv run main.py
   ```

---

## 配置验证

运行以下命令验证配置加载：

```bash
python3 -c "import config; print(f'BASE_URL: {config.BASE_URL}'); print(f'MAX_POSTS_PER_RUN: {config.MAX_POSTS_PER_RUN}')"
```

---

## 安全注意事项

1. **永远不要提交** `.env` 和 `.config.py` 到 Git
2. **定期更换** WordPress Application Password
3. **使用强密码** 保护 KKYX 账号
4. **限制访问** .env 文件权限:
   ```bash
   chmod 600 .env
   ```