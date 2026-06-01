"""
Configuration file for kkyx.net spider

Two-Layer Architecture:
- Layer 1: .env (sensitive assets only: credentials)
- Layer 2: config.py (business logic: URLs, delays, limits)

All non-sensitive configuration should be edited directly in this file.
"""

import os

from dotenv import load_dotenv

# Load sensitive credentials from .env
load_dotenv()

# ========================================
# Sensitive Assets (from .env)
# ========================================
USERNAME = os.getenv("KKYX_USER") or os.getenv("KKYX_USERNAME")
PASSWORD = os.getenv("KKYX_PWD") or os.getenv("KKYX_PASSWORD")

# Validate credentials are loaded
if not USERNAME or not PASSWORD:
    raise ValueError(
        "Missing credentials! Please set KKYX_USER/KKYX_PWD in .env file "
        "or as environment variables (KKYX_USER, KKYX_PWD)."
    )

# ========================================
# Target Site Configuration
# ========================================
BASE_URL = "https://www.kkyx.net"
LOGIN_URL = f"{BASE_URL}/index.php?m=user&c=Users&a=login"

# ========================================
# Index Scan Configuration (URL-Based)
# ========================================
# Entry point for index scanning (edit this to change start category)
INDEX_SCAN_START_URL = f"{BASE_URL}/update/"

# Legacy page template (for main.py compatibility)
UPDATE_CHANNEL_PAGE_TEMPLATE = f"{BASE_URL}/update/list_15_{{page_num}}/"

# Physical boundary: Optional hard stop URL (e.g., "https://www.kkyx.net/update/list_15_517/")
# If empty and no watermark exists, will execute single-page crawl for safety
INDEX_SCAN_END_URL = "https://www.kkyx.net/update/list_15_517/"

# Time buffer for incremental sync watermark (hours)
# Posts older than (last_scan_time - buffer) will be skipped
TIME_BUFFER_HOURS = 24

# ========================================
# Producer-Consumer Pipeline Configuration
# ========================================
# Posts per consumer batch
POST_CRAWL_BATCH_LIMIT = 5

# Queue size limit for memory control
QUEUE_MAX_SIZE = 50

# Delays between post crawls (seconds)
POST_MIN_DELAY = 1
POST_MAX_DELAY = 15

# ========================================
# Batch Configuration Defaults
# ========================================
DEFAULT_BATCH_COUNT = 10  # Default number of games to process
START_PAGE = 1  # Default starting page number

# ========================================
# Run Limits (Safety Guards)
# ========================================
INDEX_SCAN_PAGE_LIMIT = 2  # Maximum index pages per run (resets every run, not daily)
SAFE_THRESHOLD = 9  # Circuit breaker: stop when remaining quota <= 9

# 每次运行最多抓取的资源数。与官方剩余配额取较小值 (dual ceiling)。
MAX_POSTS_PER_RUN = 5

# 三振出局上限：同一资源连续失败达到此数值后永久放弃 (dead letter)
MAX_RETRY_COUNT = 3

# Browser lifecycle
BROWSER_RESTART_INTERVAL = 10  # Restart browser every N consumer posts (memory hygiene for RPi)

# ========================================
# Debug Settings
# ========================================
DEBUG_MODE = True  # Enable debug logging
DEBUG_LIMIT = 3  # Max detail pages in dev mode

# ========================================
# Logging Configuration
# ========================================
LOG_LEVEL = "DEBUG"

# ========================================
# Database Configuration
# ========================================
DB_DIR = "data/db"
DB_FILE = os.path.join(DB_DIR, "kkyx_spider.db")
os.makedirs(DB_DIR, exist_ok=True)

# ========================================
# Anti-Detection Delays (seconds)
# ========================================
# Index page delays
INDEX_PAGE_DELAY = (3, 7)
INDEX_PAGE_LONG_SLEEP_INTERVAL = 20
INDEX_PAGE_LONG_SLEEP = (30, 60)
SOFT_404_RETRY_WAIT = 60
SOFT_404_MAX_RETRIES = 2

# Detail page delays (heavier, involves login and buy button clicks)
DELAY_INDEX_MIN = 1
DELAY_INDEX_MAX = 3
DELAY_DETAIL_MIN = 10
DELAY_DETAIL_MAX = 20

# Legacy compatibility
DELAY_MIN = DELAY_DETAIL_MIN
DELAY_MAX = DELAY_DETAIL_MAX

# ========================================
# Paths
# ========================================
SCREENSHOT_DIR = "debug/screenshots"
SCREENSHOT_PATH = os.path.join(SCREENSHOT_DIR, "debug_screenshot.png")

# ========================================
# Category IDs
# ========================================
CATEGORY_GAME = 68  # Default game category ID

# ========================================
# Crawl Status Codes
# ========================================
CRAWL_STATUS_PENDING = 0
CRAWL_STATUS_COMPLETED = 1
CRAWL_STATUS_NEEDS_UPDATE = 2
CRAWL_STATUS_DEAD_LETTER = 3

# ========================================
# WordPress Sync Configuration
# ========================================
WP_BASE_URL = os.getenv("WP_BASE_URL", "http://localhost:8080")
WP_USERNAME = os.getenv("WP_USERNAME", "test-kkyx")
WP_APP_PASSWORD = os.getenv("TEST_KKYX_WP_APP_PASSWORD", "")

# Category mapping (name -> ID)
WP_CATEGORY_MAP = {
    "默认": 68,
    "动作": 70,
    "独立游戏": 75,
}

# Fixed tags (applied to all posts)
WP_FIXED_TAGS = ["KKYX"]

# Dynamic tag extraction keywords
WP_TAG_KEYWORDS = [
    "RPG", "动作", "模拟", "汉化", "策略", "冒险", "射击",
    "独立游戏", "单机游戏", "PC", "Steam", "中文",
]

# Erphpdown price (fixed)
WP_ICE_PRICE = "5.00"

# Media upload settings
WP_MEDIA_VERIFY_SSL = False
WP_MEDIA_TIMEOUT = 60

# Batch sync settings
WP_SYNC_BATCH_LIMIT = 1
WP_SYNC_INTERVAL = 2

# Rate limiting (seconds between posts)
WP_SYNC_MIN_DELAY = 1
WP_SYNC_MAX_DELAY = 3

# Retry settings
WP_MAX_RETRIES = 3
WP_RETRY_BACKOFF_BASE = 2

# ========================================
# CDN Configuration
# ========================================
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://test-img-cdn.freessr.bid:8443/kkyx")
