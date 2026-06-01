# KKYX 资源采集引擎：三大架构铁律

> 这些是从大量生产调试中提炼出的核心设计原则。违反任何一条都会导致系统不稳定。

---

## 第一律：极简隔离胜过复杂共享 (Isolation > Sharing)

### 教训
在内存受限的边缘设备（树莓派）上，**绝不使用 CDP（9222端口）或多线程去试图共享同一个浏览器上下文**。

### 对策
- 回归原生 `playwright.chromium.launch()`，严格实行"单页面独占 State"的物理级隔离
- Producer 和 Consumer 各自独立创建浏览器上下文
- 串行执行：先 Producer 全量扫描，再 Consumer 逐条处理
- 每处理 `BROWSER_RESTART_INTERVAL` 条 Consumer 任务，重启浏览器回收内存

### 设计细节
```python
# 浏览器生命周期管理
BROWSER_RESTART_INTERVAL = 10  # 每处理 10 条重启浏览器

# 重启流程
def _restart_browser(pw, browser, context):
    """完全关闭 → 等待 5 秒让 OS 回收内存 → 重新启动"""
    # 关闭所有资源
    page.close(); context.close(); browser.close(); pw.stop()
    time.sleep(5)  # 等待 OS 回收 Chromium 内存
    pw, browser = _launch_browser()  # 重新启动，失败则重试 1 次
    context = _create_context(browser)
    return pw, browser, context
```

---

## 第二律：快速失败优于无限自愈 (Fail-Fast > Self-Healing)

### 教训
编写复杂的 `_auto_heal`（自动重登、等待锁、重试）往往会导致**死锁**或陷入无穷无尽的"假掉线"逻辑循环中。

### 对策：三态鉴权探针

```python
AUTH_ALIVE   = "ALIVE"    # 会话确认有效
AUTH_DEAD    = "DEAD"     # 会话确认失效 (服务器已撤销 cookies)
AUTH_UNKNOWN = "UNKNOWN"  # 网络波动 / 页面异常，无法判定
```

### 鉴权验证层级 (User Center 为金标准)

```
Layer 1: boyong 文本检查
  └─ level_centre.html 中包含 "boyong" 文本 → ALIVE

Layer 2: 登录页检测 (反证 DEAD)
  └─ URL 含 login / 用户名输入框可见 / "请先登录" 文本 → DEAD

Layer 3: 已认证区域元素检测
  └─ #dailyLimit 可见 / "退出" 链接可见 → ALIVE (boyong 位置可能变了)
  └─ 以上全部无法判定 → UNKNOWN
```

### Fail-Fast 行为

| 探针结果 | 行为 |
|----------|------|
| `AUTH_DEAD` (确认掉线) | `os._exit(1)` 立即终止进程，保留现场截图 |
| `AUTH_UNKNOWN` (网络波动) | 记录警告，跳过当前资源继续 |
| `AUTH_ALIVE` (确认在线) | 正常继续 |

### 触发时机
1. **启动时** (Boot): 加载 state.json 后立即验证
2. **Consumer 每条资源**: 下载链接提取为 0 条时，通过 User Center 核实
3. **UI 点击弹窗**: 弹窗重定向到首页时，核实是否掉线
4. **浏览器重启后**: 重新验证鉴权状态

### 为什么用 `os._exit(1)` 而不是 `sys.exit()`？
- `os._exit()` 是硬终止，不执行任何 cleanup 代码
- 防止在 cleanup 过程中写入脏数据
- 保留现场给人类分析（截图、日志）

---

## 第三律：降维打击前端遮挡 (JS Injection over UI Click)

### 教训
面对充满恶意的响应式布局、懒加载和隐形弹窗，传统的模拟鼠标点击 (`page.click()`) 极其脆弱，容易受视口大小和 CSS 层级的影响。

### 对策

#### 索引扫描: 全量 JavaScript 注入
```javascript
// Producer 阶段：直接在页面内执行 JS 提取所有游戏链接
// 不依赖任何 DOM 可见性，直接操作 DOM 树
page.evaluate('''() => {
    const results = [];
    const containers = document.querySelectorAll('li, .item, .game-item');
    containers.forEach(container => {
        const link = container.querySelector('a[href*="/qbyx/"]');
        // ... 直接提取 href, title, date
    });
    return { games: results };
}''')
```

#### 详情下载: 物理强制点击
```python
# Consumer 阶段：用 JS evaluate 强制点击，绕过 Playwright 可见性检查
page.evaluate(f'''() => {{
    const buttons = document.querySelectorAll('.action-buttons a.btn-download');
    if (buttons[{btn_index}]) {{
        buttons[{btn_index}].scrollIntoView({{ behavior: 'instant', block: 'center' }});
        buttons[{btn_index}].click();
    }}
}}''')
```

#### 图片懒加载: 多属性优先级探测
```python
# 处理懒加载图片：按优先级检查多个属性
real_url = (
    img.get('data-src') or      # 常见懒加载
    img.get('data-original') or  # 备选懒加载
    img.get('data-lazy-src') or  # 又一种模式
    img.get('src')               # 普通图片
)
```

---

## 补充：DOM 探针 (Tripwire) 机制

Boss 账号为永久 VIP。如果在详情页发现购买元素变为可见，可能意味着会话已失效。

```
DOM 探针扫描 → 发现购买按钮可见
    │
    ├─→ User Center 核实 → AUTH_DEAD → os._exit(1)
    ├─→ User Center 核实 → AUTH_UNKNOWN → 跳过此资源继续
    └─→ User Center 核实 → AUTH_ALIVE → 误报，继续
```

这是"不信任单点信息，交叉验证"原则的体现。
