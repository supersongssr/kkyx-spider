# 图片处理与存储 — Single Source of Truth

> 所有图片的来源只有一个：HTML 正文 (description 字段)。绝不从 DOM 单独扫描图片。

---

## 1. 核心原则

```
Single Source of Truth:
  所有图片 MUST come from description HTML string
  
Graceful Degradation:
  任何单张图片处理失败，保留原始 URL + referrerpolicy，永不删除 <img> 标签
```

## 2. 扁平化存储架构

```
data/storage/
├── a1b2c3d4e5f6g7h8.jpg    # {md5_hash}.{ext}
├── f9e8d7c6b5a4g3h2.png
└── ...
```

- 文件名 = 内容 MD5 + 原始扩展名
- 全局去重：同一张图片无论出现在哪个游戏页面，只存储一次
- 数据库记录关联: `game_assets` 表通过 `game_id` + `md5_hash` 管理所有权

## 3. 双层去重策略

```
图片 URL
  │
  ├─→ Layer 1: URL Precheck (最快路径)
  │   查询: SELECT * FROM game_assets WHERE original_url = ?
  │   命中 → 直接创建数据库关联，不下载
  │
  └─→ Layer 2: MD5 Physical Dedup (下载后)
      下载图片 → 计算 MD5
      查询: SELECT * FROM game_assets WHERE md5_hash = ?
      命中 → 丢弃下载数据，创建关联
      未命中 → 保存到 data/storage/{md5}.ext
```

## 4. 处理流水线

```python
def process_html_images(page, html_content, game_id):
    """
    处理 HTML 中所有图片的完整流水线
    """
    # Step 1: BeautifulSoup 提取所有 <img> 标签
    img_list = extract_img_urls_from_html(html_content)
    # 处理懒加载: data-src > data-original > data-lazy-src > src
    
    for img in img_list:
        # Step 2: URL 标准化 (去 query、fragment)
        url = normalize_url(img['real_url'])
        
        # Step 3: Layer 1 - URL 预检
        if get_asset_by_url(url):
            # 已存在 → 只建关联
            continue
        
        # Step 4: 下载图片 (带重试)
        data = download_image_with_retry(page, url)
        
        # Step 5: Layer 2 - MD5 去重
        md5 = calculate_md5(data)
        if get_asset_by_md5(md5):
            # 文件已存在 → 建关联
            continue
        
        # Step 6: 保存新文件
        save(f"data/storage/{md5}.{ext}", data)
        save_game_asset(game_id, 'content', path, url, md5)
        
        # Step 7: 更新 HTML 中的 src
        update_html_img_src(html, old_src, new_src)
    
    # Step 8: 给所有 <img> 加 referrerpolicy="no-referrer"
    html = add_referrerpolicy_to_html(html)
    
    return updated_html, assets_list
```

## 5. 下载反盗链

```python
DOWNLOAD_HEADERS = {
    'Referer': 'https://www.kkyx.net/',
    'User-Agent': 'Mozilla/5.0 ...',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}
```

使用 Playwright 的 `page.request.get()` 下载（复用浏览器会话的 cookies）。

## 6. 懒加载处理优先级

```python
# 按优先级检查多个属性
real_url = (
    img.get('data-src')       or   # 常见懒加载
    img.get('data-original')  or   # jQuery LazyLoad
    img.get('data-lazy-src')  or   # WP 主题常见
    img.get('src')                  # 普通图片
)
```

处理完成后，移除所有懒加载属性，将真实 URL 写入 `src`。

## 7. CDN 分发映射

```
原始 URL: https://www.kkyx.net/uploads/abc123.jpg
    ↓ (MD5: a1b2c3d4e5f6)
本地存储: data/storage/a1b2c3d4e5f6.jpg
    ↓ (同步到 CDN)
CDN URL:  https://test-img-cdn.freessr.bid:8443/kkyx/a1b2c3d4e5f6.jpg
```

WordPress 发布时，将 HTML 中的原始图片 URL 替换为 CDN URL。
