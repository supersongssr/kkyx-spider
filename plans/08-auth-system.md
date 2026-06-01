# 鉴权系统 — 会话管理与反检测

> KKYX 爬虫的鉴权系统围绕"会话持久化 + 三态探针 + 行为模拟"三层防护构建。

---

## 1. 会话生命周期

```
首次登录 (auth/auto_login.py)
    │
    ├─→ 创建干净浏览器上下文 (无 stale cookies)
    ├─→ 行为模拟: 首页浏览 → 登录页 → 填表 → AJAX提交
    ├─→ Truth Test: 主动导航到 level_centre.html
    │   └─ 检查 "boyong" 文本存在 → 确认登录成功
    └─→ 保存 storage_state → auth/state.json
         (包含所有 cookies + localStorage)

每次运行 (main.py)
    │
    ├─→ 加载 auth/state.json 恢复会话
    ├─→ Boot Auth: 三态探针验证
    │   ├─ ALIVE → 继续
    │   ├─ DEAD → os._exit(1) (需要人工重新登录)
    │   └─ UNKNOWN → 警告但继续
    └─→ 运行中: 多点探针 (Consumer 处理时、浏览器重启后)
```

## 2. 登录流程 (行为模拟)

```
Phase 1: 首页浏览 (Behavioral Warm-up)
  → page.goto(BASE_URL)
  → 随机停留 2-5 秒 + 随机滚动
  → 避免"直接访问登录页"的指纹特征

Phase 2: 导航到登录页
  → page.goto(LOGIN_URL)

Phase 3: 填写凭据
  → 多选择器回退填入用户名/密码
  → 标准 fill → JS evaluate 回退

Phase 4: AJAX API 提交 (绕过表单冒泡)
  → 直接 POST /index.php?m=user&c=Users&a=login
  → 避免"登录按钮点击"被搜索表单拦截

Phase 5: Truth Test (金标准验证)
  → 主动导航到 /user/Level/level_centre.html
  → 检查页面内容包含 "boyong"
  → 成功: 保存 storage_state
  → 失败: 截图 + HTML 诊断输出
```

## 3. 浏览器指纹硬化

```python
# 启动参数
args = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-setuid-sandbox',
]

# 上下文配置
context = browser.new_context(
    storage_state="auth/state.json",     # 会话恢复
    viewport={'width': 1920, 'height': 1080},  # 桌面视口锁定
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...Chrome/122.0.0.0...',
    locale='zh-CN',
    is_mobile=False,       # 明确声明非移动端
    has_touch=False,       # 明确声明无触控
)
```

## 4. Stealth 插件

```python
from playwright_stealth import Stealth
Stealth().apply_stealth_sync(page)
# 隐藏: navigator.webdriver, Chrome DevTools Protocol, 等
```

## 5. 会话过期处理策略

| 场景 | 检测方式 | 处理方式 |
|------|----------|----------|
| 启动时会话已过期 | Boot Auth 探针 → DEAD | `os._exit(1)` — 需人工执行 `uv run auth/auto_login.py` |
| 运行中掉线 (Consumer) | 下载链接为 0 + User Center 确认 | `os._exit(1)` — Fail-Fast |
| 运行中掉线 (UI Click) | 弹窗重定向到首页 + User Center 确认 | `os._exit(1)` |
| DOM 探针误报 | 购买元素可见 + User Center 仍然 ALIVE | 继续运行 (假警报) |
| 网络波动 | 探针返回 UNKNOWN | 跳过当前资源，继续 |

## 6. 诊断工具

当鉴权失败时，自动保存以下诊断信息：

```
debug/screenshots/
├── 20250101_120000_auth_probe_failed_fatal.png   # AUTH_DEAD 截图
├── 20250101_120000_auth_probe_unknown.png         # UNKNOWN 截图
├── truth_test_failed.png                          # 登录验证失败
└── captcha_detected.png                           # 验证码检测

debug/html/
├── truth_page_content.html                        # 验证页完整 HTML
└── truth_page_content_failed.html                 # 失败页完整 HTML

debug/network/
└── diagnostic_cookies.json                        # Cookie 快照
```
