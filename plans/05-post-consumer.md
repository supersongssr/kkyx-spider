# 详情采集 (Post Consumer) 核心设计

> Consumer 负责进入游戏详情页提取所有有价值的数据。这是配额受限的核心阶段。

---

## 1. 提取数据清单

每条游戏详情页需要提取：

| 数据 | 提取方式 | 说明 |
|------|----------|------|
| 标题 | `page.title()` | 基础元数据 |
| HTML正文 | JS: `.content-text` / `.article-content` | 含图片的完整正文 |
| 发布日期 | 正则匹配 `YYYY-MM-DD` 等格式 | 用于增量同步 |
| 解压密码 | CSS选择器 + 正则: `解压密码[:：]\s*([a-zA-Z0-9]+)` | 关键业务数据 |
| 下载链接 | UI 物理点击 → 捕获弹窗 | 核心价值数据 |
| 访问密码 | 从弹窗 URL/内容中解析 | 随下载链接 |
| 权限状态 | VIP免费 / 已购买 / 需购买 | 决定提取策略 |
| 图片资产 | 从 HTML 正文提取所有 `<img>` | CDN分发用 |

## 2. 下载链接提取 — UI 物理点击策略

### 为什么不用 AJAX？
网站的 AJAX 接口存在鉴权问题，直接调用 API 经常返回错误。改为模拟真实用户点击。

### 三层提取策略

```python
def extract_ui_download_links(page, context):
    """通过物理点击下载按钮提取网盘链接"""
    
    # Step 0: DOM 探针预检 (Tripwire)
    if detect_session_drop(page):
        # 通过 User Center 交叉验证
        auth = verify_session_via_user_center(context)
        if auth == AUTH_DEAD:
            os._exit(1)  # Fail-Fast
    
    # Step 1: 发现所有下载按钮
    buttons = page.evaluate('''() => {
        return document.querySelectorAll('.action-buttons a.btn-download');
    }''')
    
    for btn in buttons:
        # Strategy A: JS 强制点击 + expect_popup
        with page.expect_popup() as popup_info:
            page.evaluate('buttons[i].click()')  # 绕过 Playwright 可见性检查
        popup = popup_info.value
        
        # 弹窗重定向到首页 = 掉线
        if popup.url == BASE_URL:
            auth = verify_session_via_user_center(context)
            if auth == AUTH_DEAD:
                os._exit(1)
            continue
        
        # Strategy B: 检查当前页面 Modal
        link_info = _extract_from_modal(page, platform, file_id)
        
        # Strategy C: 检查页面是否跳转到网盘 URL
        link_info = _parse_pan_link_from_url(page.url)
```

## 3. 网盘链接解析

支持多种网盘平台：

| 平台 | URL 模式 | 密码提取 |
|------|----------|----------|
| 百度网盘 | `pan.baidu.com/s/...` 或 `share/init?surl=...` | `?pwd=xxx` 或正文提取 |
| 天翼云盘 | `cloud.189.cn/web/share?code=...` | `（访问码：xxx）` 从 URL 解码 |
| 迅雷云盘 | `pan.xunlei.com/s/...` | `?pwd=xxx` |
| 夸克网盘 | `pan.quark.cn/s/...` | 正文提取 |
| 阿里云盘 | `alipan.com/s/...` | 通常无密码 |

## 4. 配额管理

### 双重配额天花板 (Dual Ceiling)

```python
effective_quota = min(official_remaining, MAX_POSTS_PER_RUN)
```

- `official_remaining`: 从网站 VIP 中心实时查询的剩余配额
- `MAX_POSTS_PER_RUN`: 配置文件限制的每次运行最大处理数

### 配额查询 (从 VIP 中心页面)

```python
def check_daily_quota(page):
    """从 /user/Level/level_centre.html 读取配额"""
    page.goto(f"{BASE_URL}/user/Level/level_centre.html")
    page.wait_for_selector('#dailyLimit', timeout=10000)
    
    return {
        'daily_limit': int(page.evaluate('document.querySelector("#dailyLimit").textContent')),
        'today_remaining': int(page.evaluate('document.querySelector("#todayRemaining").textContent')),
    }
```

### 熔断保护

```python
if remaining <= SAFE_THRESHOLD:  # 默认 9
    logger.warning("配额接近安全阈值，停止 Consumer")
    break
```

## 5. 三振出局 (Dead Letter)

```python
def _handle_failure(game_id, retry_count, max_retries=3):
    new_count = retry_count + 1
    if new_count >= max_retries:
        update_crawl_status(game_id, 3)  # 永久放弃
    else:
        update_crawl_status(game_id, 2)  # 标记为需重试
```

## 6. Consumer 处理流程 (单条游戏)

```
1. 从数据库取任务 (random_weight 排序)
2. 导航到详情页
3. 提取元数据 (标题、权限状态、资源类型)
4. 提取 HTML 正文
5. 提取发布日期
6. 提取解压密码
7. UI 物理点击提取下载链接
8. 处理正文中的图片 (下载 + 去重 + 更新 HTML)
9. 更新数据库
10. 随机延迟 10-20 秒
11. 检查浏览器重启间隔
```

## 7. 结构化收据 (Receipt)

每条处理完成的游戏打印结构化收据：

```
[Consumer] 进度 3/45 | ID: 127 | 标题: 《游戏名称》
┣━ 1. 页面获取: ✅ 成功
┣━ 2. 游戏正文: ✅ 成功 (1234字)
┣━ 3. 解压密码: ✅ 成功 (pwd: www.kkyx.net)
┣━ 4. 图片资产: ✅ 发现 5 张，成功落地 5 张
┣━ 5. 下载地址: ✅ 成功提取 2 条
┃  👉 百度云盘: https://pan.baidu.com/s/...
┃  👉 天翼云盘: https://cloud.189.cn/...
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
