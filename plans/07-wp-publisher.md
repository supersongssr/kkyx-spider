# WordPress 同步引擎 — WP Publisher

> 将采集到的游戏数据同步到 WordPress 站点，支持 Erphpdown 付费下载主题。

---

## 1. 同步流程

```
SQLite (crawl_status=1 的已完成游戏)
    │
    ├─→ 查询 wp_sync_log (本地幂等性检查)
    │   已同步 → 跳过
    │   未同步 → 继续
    │
    ├─→ 连接 WordPress REST API
    │   自动检测 API Root: /wp-json/ 或 ?rest_route=/
    │   Application Password 认证
    │
    ├─→ 缓存预热
    │   加载全部分类 (slug → id)
    │   加载全部标签 (slug → id)
    │   探测 Erphpdown meta keys
    │
    ├─→ 构建 Post
    │   ├─ 标题 + 正文 (CDN图片URL替换)
    │   ├─ 分类 (默认: 68)
    │   ├─ 标签 (固定标签 + 标题关键词动态提取)
    │   └─ Meta (价格、下载链接、密码)
    │
    ├─→ 创建/更新 Post
    │   POST /wp/v2/posts (新建)
    │   PUT  /wp/v2/posts/{id} (更新)
    │
    └─→ 记录同步日志 (wp_sync_log)
```

## 2. Erphpdown Meta 字段

```python
payload['meta'] = {
    'ice_price': '5.00',                    # 固定价格
    'down_url': game_data['pan_url'],       # 网盘分享链接
    'down_pswd': game_data['access_password'],  # 访问密码
    'source_game_id': game_data['source_url'],  # 幂等性键
}
```

Meta keys 通过探测已有 Post 自动发现，避免硬编码错误。

## 3. CDN 图片替换

发布到 WordPress 时，将正文中的原始图片 URL 替换为 CDN URL：

```python
def _replace_image_urls(html_content, url_mapping):
    """
    优雅降级策略:
    - 映射表中有 → 替换为 CDN URL + referrerpolicy
    - 映射表中无 → 保留原始 URL + referrerpolicy
    - 所有 <img> 必须有 referrerpolicy="no-referrer"
    """
    for img_tag in re.finditer(r'<img[^>]*src="([^"]*)"', html):
        normalized_url = get_clean_url(img_src)
        cdn_url = url_mapping.get(normalized_url)
        
        if cdn_url:
            # 替换 src + 添加 referrerpolicy
        else:
            # 保留原始 src + 添加 referrerpolicy
```

## 4. 标签动态提取

```python
WP_TAG_KEYWORDS = ["RPG", "动作", "模拟", "汉化", "策略", 
                    "冒险", "射击", "独立游戏", "PC", "Steam", "中文"]

def _extract_tags_from_title(title):
    """从标题中匹配关键词生成标签"""
    return [kw for kw in WP_TAG_KEYWORDS if kw.lower() in title.lower()]
```

## 5. 重试策略

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _request(method, endpoint, **kwargs):
    """
    429 (Too Many Requests): 指数退避重试
    5xx (Server Error): 指数退避重试
    其他: 直接返回
    """
```

## 6. 幂等性保证

- **本地检查**: `wp_sync_log` 表记录每条游戏的同步状态
- **云端检查**: 通过 `meta_key=source_game_id` 查询已有 Post
- **更新逻辑**: 如果已有 Post，使用 PUT 更新而非重复创建

## 7. 配置要点

```python
# WordPress 连接
WP_BASE_URL = os.getenv("WP_BASE_URL", "http://localhost:8080")
WP_USERNAME = os.getenv("WP_USERNAME", "test-kkyx")
WP_APP_PASSWORD = os.getenv("TEST_KKYX_WP_APP_PASSWORD", "")

# 分类映射
WP_CATEGORY_MAP = {"默认": 68, "动作": 70, "独立游戏": 75}

# 价格
WP_ICE_PRICE = "5.00"

# CDN
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://test-img-cdn.freessr.bid:8443/kkyx")
```
