# 索引扫描 (Index Producer) 核心设计

> Producer 负责"应收尽收"——发现所有游戏 URL，不受任何配额限制。

---

## 1. URL 构造翻页 (非 DOM 依赖)

**核心设计**: 翻页不依赖页面上的"下一页"按钮，而是通过 URL 模式识别直接构造。

```python
def construct_next_page_url(current_url, base_url, start_url):
    """
    URL 模式:
      第一页: https://www.kkyx.net/update/
      第二页: https://www.kkyx.net/update/list_15_2/
      第N页:  https://www.kkyx.net/update/list_15_N/
    """
    current_page = get_page_num_from_url(current_url, start_url)
    next_page = current_page + 1
    
    # 从当前 URL 提取 list_15_ 模式，递增页码
    if '/list_' in current_url:
        return re.sub(r'/list_\d+_(\d+)', f'/list_15_{next_page}', current_url)
    
    # 从起始页构造: /update/ → /update/list_15_2/
    if current_url.rstrip('/') == start_url.rstrip('/'):
        return f"{base_url}/update/list_15_{next_page}/"
```

**优势**:
- 不受页面 DOM 变化影响
- 不需要等待"下一页"按钮渲染
- 即使页面部分加载失败也能继续

**风险**:
- 如果网站改变 URL 结构，翻页将失败
- 需要手动更新 `INDEX_SCAN_END_URL`

## 2. JavaScript 注入提取

```javascript
// 在列表页执行，直接提取结构化数据
page.evaluate('''() => {
    // 标题黑名单 - 过滤无效文本
    const titleBlacklist = ['查看', '更多', '详情', '点击', '下载', '进入'];
    
    // 策略1: 结构化容器提取 (优先)
    document.querySelectorAll('li, .item, .game-item').forEach(container => {
        const link = container.querySelector('a[href*="/qbyx/"]');
        // 提取: href, title (从 .title/.name/h2/h3), date (从 .time/.date)
    });
    
    // 策略2: 回退到直接链接提取
    if (results.length === 0) {
        document.querySelectorAll('a[href*="/qbyx/"]').forEach(item => {
            // 直接从链接文本提取
        });
    }
}''')
```

## 3. 双层更新检测

```python
def upsert_game_producer(game_data):
    """基于 source_url 唯一键的幂等更新"""
    
    existing = db.find_by_source_url(game_data['source_url'])
    
    if existing:
        name_check = old_title != new_title      # 名称变更
        date_check = old_publish_date != new_date # 日期变更
        
        if name_check or date_check:
            crawl_status = 2  # 标记为"需更新"
        elif crawl_status == 0:
            pass  # 从未处理，保持待处理
        else:
            return 'unchanged'
    else:
        # 新发现 → 插入，random_weight 随机化
        crawl_status = 0
        random_weight = random.randint(1, 99)
```

## 4. Soft-404 处理

某些页面返回 200 但内容为空（反爬策略）。处理逻辑：

```python
for retry in range(SOFT_404_MAX_RETRIES + 1):
    check = page.evaluate('''() => {
        const hasGameLinks = document.querySelectorAll('a[href*="/qbyx/"]').length > 0;
        return {
            is_404: title.includes('404') || !hasGameLinks,
            is_hard: title.includes('404')
        };
    }''')
    
    if not check['is_404']:
        break  # 页面正常
    
    if check['is_hard']:
        break  # 真实 404，不重试
    
    # Soft 404: 等待后重试
    time.sleep(SOFT_404_RETRY_WAIT)  # 默认 60 秒
```

## 5. 反检测延迟策略

```python
# 索引页之间的延迟
INDEX_PAGE_DELAY = (3, 7)           # 每页随机 3-7 秒
INDEX_PAGE_LONG_SLEEP_INTERVAL = 20  # 每 20 页触发一次长休眠
INDEX_PAGE_LONG_SLEEP = (30, 60)     # 长休眠 30-60 秒
```

## 6. 水印过滤 (增量模式)

```python
def is_past_watermark(publish_date, cutoff_time):
    """
    关键逻辑: cutoff_time 为 None 时永远返回 False (不过滤)
    这确保首次运行获取全部历史数据
    """
    if not cutoff_time:
        return False  # 首次运行：全量模式
    
    return parse(publish_date) < parse(cutoff_time)
```
