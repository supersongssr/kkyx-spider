# 黄金三角状态机 — 断点续爬与增量同步

> 这是整个爬虫系统的核心灵魂设计。三变量状态机实现了"不重不漏"的增量采集。

---

## 1. 状态机三变量

| 变量 | 类型 | 作用 | 存储位置 |
|------|------|------|----------|
| `index_scan_start_time` | ISO 时间戳 | 当前扫描周期的锚点时间 | `system_config` 表 |
| `index_scan_end_time` | ISO 时间戳 | 上一个成功完成周期的边界时间 | `system_config` 表 |
| `index_scan_last_url` | URL 字符串 | 实时进度（最后扫描的页面） | `system_config` 表 |

## 2. 两种运行模式

### 新周期模式 (New Cycle)
```
触发条件: index_scan_last_url 为空
行为:
  1. 设置 index_scan_start_time = now()
  2. 从 INDEX_SCAN_START_URL 开始扫描
  3. 每页更新 index_scan_last_url = 当前URL
  4. 成功完成: index_scan_end_time = index_scan_start_time, 清空 last_url
```

### 续爬模式 (Resume)
```
触发条件: index_scan_last_url 有值
行为:
  1. 不更新 index_scan_start_time (保持原锚点)
  2. 从 index_scan_last_url 继续扫描
  3. 每页更新 index_scan_last_url = 当前URL
```

## 3. "不重不漏" 保证机制

| 场景 | 保证机制 |
|------|----------|
| **不重** | 增量扫描时使用 `cutoff_time` 过滤已处理内容 |
| **不漏** | 首次运行 `cutoff_time = None`，全量扫描所有历史数据 |
| **可恢复** | 每扫描一页更新 `index_scan_last_url`，崩溃后可续爬 |
| **幂等性** | `upsert_game_producer()` 基于 `source_url` 唯一键更新 |

## 4. 增量同步截止时间计算

```python
def get_scan_cutoff_time(buffer_hours=24):
    end_time = get_index_scan_end_time()
    
    if not end_time:
        return None  # 首次运行：不过滤，获取全部历史数据
    
    return end_time - timedelta(hours=buffer_hours)
```

**安全缓冲 (`TIME_BUFFER_HOURS = 24`)**: 从上周期结束时间往前推 N 小时，确保边界处的内容不会被遗漏。

## 5. 周期完成条件

只有以下停止原因会触发周期完成 (finalize)：
- `end_url`: 到达配置的物理终点 URL
- `watermark`: 全部内容超过水印截止时间

以下原因**不会**完成周期（保留进度，等待续爬）：
- `error_404`: 404 错误（非终点处）
- `error`: 其他异常
- `manual`: 用户中断
- `empty_content`: 连续空页面
- `page_limit`: 达到单次页数限制

## 6. Producer 扫描终止条件 (优先级从高到低)

1. **物理终点**: 到达 `INDEX_SCAN_END_URL`
2. **页数限制**: 达到 `INDEX_SCAN_PAGE_LIMIT` (每次运行)
3. **水印截止**: 增量模式下，所有内容都超过 `cutoff_time`
4. **空内容熔断**: 连续 2 页无任何游戏链接
5. **404 错误**: 在非终点 URL 遇到 404
6. **URL 构造失败**: 无法构造下一页 URL

## 7. Consumer 处理终止条件

1. **有效配额耗尽**: `min(official_remaining, MAX_POSTS_PER_RUN)` 用完
2. **安全阈值触发**: 剩余配额 ≤ `SAFE_THRESHOLD` (默认 9)
3. **无待处理任务**: 数据库中没有 `crawl_status IN (0, 2)` 的记录
4. **三振出局**: 同一资源连续失败 `MAX_RETRY_COUNT` (默认 3) 次后标记为死信 (status=3)

## 8. 数据库 Schema (核心表)

### games 表
```sql
CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    pan_url TEXT,                    -- 网盘分享链接
    access_password TEXT,            -- 访问码
    extract_password TEXT,           -- 解压密码
    source_url TEXT UNIQUE,          -- 原始页面URL (唯一键)
    description TEXT,                -- HTML正文 (含图片)
    publish_date TEXT,               -- 发布日期
    download_links TEXT,             -- JSON: 所有下载链接
    crawl_status INTEGER DEFAULT 0,  -- 0=待处理 1=已完成 2=需更新 3=死信
    random_weight INTEGER,           -- 随机权重排序 (反模式检测)
    retry_count INTEGER DEFAULT 0,   -- 失败重试计数
    last_index_seen_time TEXT,       -- 最后被Producer发现的时间
    -- ... 其他字段
);
```

### system_config 表
```sql
CREATE TABLE system_config (
    key TEXT PRIMARY KEY,            -- 配置键名
    value TEXT NOT NULL,             -- 配置值
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- 关键键值:
-- index_scan_start_time, index_scan_end_time, index_scan_last_url
```

### game_assets 表 (图片资产)
```sql
CREATE TABLE game_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,        -- 'cover' or 'content'
    local_path TEXT NOT NULL,        -- data/storage/{md5}.ext
    original_url TEXT NOT NULL,      -- 原始图片URL
    md5_hash TEXT NOT NULL,          -- MD5全局去重键
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);
```
