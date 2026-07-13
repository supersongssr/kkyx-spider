# 配置系统迁移指南

## 从 config.test.json 迁移

如果你之前使用 `config.test.json`，请按以下步骤迁移：

### 1. 备份旧配置

```bash
cp config.test.json config.test.json.backup
```

### 2. 创建 .config.py

参考你的旧 `config.test.json`，创建 `.config.py`：

**旧方式 (config.test.json)**:
```json
{
  "safety": {
    "index_scan_page_limit": 10,
    "max_posts_per_run": 20
  }
}
```

**新方式 (.config.py)**:
```python
config_overrides = {
    "safety": {
        "index_scan_page_limit": 10,
        "max_posts_per_run": 20
    }
}
```

### 3. 更新 .env

确保敏感参数在 `.env` 中：

```bash
# 删除这行（不再需要）
# CONFIG_PATH=config.test.json

# 确保 WordPress 密钥环境变量名称正确
# 旧: TEST_KKYX_WP_APP_PASSWORD
# 新: WP_APP_PASSWORD
```

### 4. 删除旧配置文件

```bash
rm config.test.json
rm config.json  # 如果存在
```

---

## 从环境变量 CONFIG_PATH 迁移

如果你之前使用 `CONFIG_PATH` 环境变量：

### 1. 更新 .env

删除或注释掉：
```bash
# CONFIG_PATH=config.test.json
```

### 2. 创建 .config.py

将 JSON 配置转换为 Python 字典：

```python
config_overrides = {
    # 在这里添加你的配置覆盖
}
```

---

## 配置对照表

| 配置项 | 旧方式 | 新方式 |
|--------|--------|--------|
| 主配置文件 | config.json / config.test.json | config.py |
| 本地覆盖 | JSON 文件 | .config.py (Python) |
| 配置路径 | CONFIG_PATH 环境变量 | 不需要 |
| WP 密钥变量 | TEST_KKYX_WP_APP_PASSWORD | WP_APP_PASSWORD |
| 配置格式 | JSON | Python 字典 |

---

## 验证迁移

运行以下命令验证配置正确加载：

```bash
# 验证 .config.py 是否被加载
python3 -c "
import config
print(f'✅ 配置加载成功')
print(f'MAX_POSTS_PER_RUN: {config.MAX_POSTS_PER_RUN}')
print(f'WP_BASE_URL: {config.WP_BASE_URL}')
"
```

如果看到 `.config.py` 已被加载的消息，说明迁移成功。

---

## 相关文档

- [配置说明](CONFIGURATION.md) - 详细配置说明
- [快速参考](CONFIG_QUICK_REFERENCE.txt) - 配置快速参考卡片
- [完成总结](REFACTORING_COMPLETE.txt) - 重构完成总结

### 问题：配置没有被覆盖

**解决方案**: 检查 `.config.py` 中的字典结构是否正确：
```python
# 正确 ✅
config_overrides = {
    "safety": {
        "max_posts_per_run": 20
    }
}

# 错误 ❌
config_overrides = {
    "max_posts_per_run": 20  # 缺少顶层键
}
```

### 问题：找不到模块

**解决方案**: 确保在项目根目录运行：
```bash
cd /opt/git/kkyx-spider
python3 -c "import config"
```

### 问题：环境变量未生效

**解决方案**: 检查 `.env` 文件是否存在且格式正确：
```bash
# 正确 ✅
WP_APP_PASSWORD="abcd efgh ijkl mnop"

# 错误 ❌
WP_APP_PASSWORD=abcd efgh ijkl mnop  # 缺少引号
```