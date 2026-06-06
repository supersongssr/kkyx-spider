"""
KKYX Spider Configurations

================================================================================
REQUIRED .env ENVIRONMENT PARAMETERS:
- KKYX_USER: KKYX Net username (Required for website login and resource crawling)
- KKYX_PWD:  KKYX Net password (Required for website login and resource crawling)

OPTIONAL .env ENVIRONMENT PARAMETERS:
- CONFIG_PATH: Path to the complex JSON configuration file.
               Defaults to 'config.test.json' when running in a test environment.
               Defaults to 'config.json' in production/standard execution.
- WP_BASE_URL: Base URL of the WordPress website (e.g., http://localhost:8080)
- WP_USERNAME: WordPress administrator username
- TEST_KKYX_WP_APP_PASSWORD: WordPress Application Password (specifically for REST API authentication)
- CDN_BASE_URL: Base URL for uploading and referencing media content via CDN
================================================================================
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load sensitive credentials and paths from .env
load_dotenv()

# ==============================================================================
# 1. Detect Environment & Explicitly Declare config.test.json for Test Environment
# ==============================================================================
IS_TESTING = (
    os.getenv("ENV") == "test"
    or os.getenv("TESTING") == "true"
    or "pytest" in sys.modules
    or "unittest" in sys.modules
    or "PYTEST_CURRENT_TEST" in os.environ
)

# Explicitly declare configuration paths
TEST_CONFIG_PATH = "config.test.json"
PROD_CONFIG_PATH = "config.json"

# If running in a test environment, prioritize config.test.json
if IS_TESTING:
    env_config_path = os.getenv("CONFIG_PATH")
    # If CONFIG_PATH is not set or points to standard production config, force config.test.json
    if not env_config_path or env_config_path == PROD_CONFIG_PATH:
        CONFIG_PATH = TEST_CONFIG_PATH
    else:
        CONFIG_PATH = env_config_path
else:
    CONFIG_PATH = os.getenv("CONFIG_PATH", PROD_CONFIG_PATH)

# ==============================================================================
# 2. Check and Validate Required .env Environment Parameters
# ==============================================================================
USERNAME = os.getenv("KKYX_USER") or os.getenv("KKYX_USERNAME")
PASSWORD = os.getenv("KKYX_PWD") or os.getenv("KKYX_PASSWORD")

missing_params = []
if not USERNAME:
    missing_params.append("KKYX_USER")
if not PASSWORD:
    missing_params.append("KKYX_PWD")

if missing_params:
    raise ValueError(
        f"Missing required configuration parameter(s): {', '.join(missing_params)}!\n"
        "Please ensure these variables are defined in your .env file or "
        "exported as OS environment variables.\n"
        "Refer to the parameter documentation at the beginning of config.py."
    )

# ========================================
# 3. Optional Simple Configurations (Directly from environment / .env)
# ========================================
WP_BASE_URL = os.getenv("WP_BASE_URL", "http://localhost:8080")
WP_USERNAME = os.getenv("WP_USERNAME", "test-kkyx")
WP_APP_PASSWORD = os.getenv("TEST_KKYX_WP_APP_PASSWORD", "")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://test-img-cdn.freessr.bid:8443/kkyx")

# ========================================
# 4. Complex Configurations Path resolution
# ========================================
# Fallback defaults in case the JSON is missing or keys are absent
defaults = {
    "target_site": {
        "base_url": "https://www.kkyx.net",
        "login_url": "https://www.kkyx.net/index.php?m=user&c=Users&a=login",
        "index_scan_start_url": "https://www.kkyx.net/update/",
        "index_scan_end_url": "https://www.kkyx.net/update/list_15_517/",
        "update_channel_page_template": "https://www.kkyx.net/update/list_15_{page_num}/"
    },
    "pipeline": {
        "post_crawl_batch_limit": 5,
        "queue_max_size": 50,
        "post_min_delay": 1,
        "post_max_delay": 15,
        "default_batch_count": 10,
        "start_page": 1
    },
    "safety": {
        "index_scan_page_limit": 2,
        "safe_threshold": 9,
        "max_posts_per_run": 5,
        "max_retry_count": 3,
        "browser_restart_interval": 10
    },
    "debug": {
        "debug_mode": True,
        "debug_limit": 3,
        "log_level": "DEBUG"
    },
    "database": {
        "db_dir": ".data/db",
        "db_file": ".data/db/kkyx_spider.db"
    },
    "delays": {
        "index_page_delay": [3, 7],
        "index_page_long_sleep_interval": 20,
        "index_page_long_sleep": [30, 60],
        "soft_404_retry_wait": 60,
        "soft_404_max_retries": 2,
        "delay_index_min": 1,
        "delay_index_max": 3,
        "delay_detail_min": 10,
        "delay_detail_max": 20
    },
    "paths": {
        "screenshot_dir": ".screenshots",
        "screenshot_path": ".screenshots/debug_screenshot.png"
    },
    "wordpress": {
        "category_game": 68,
        "category_map": {"默认": 68, "动作": 70, "独立游戏": 75},
        "fixed_tags": ["KKYX"],
        "tag_keywords": ["RPG", "动作", "模拟", "汉化", "策略", "冒险", "射击", "独立游戏", "单机游戏", "PC", "Steam", "中文"],
        "ice_price": "5.00",
        "media_verify_ssl": False,
        "media_timeout": 60,
        "sync_batch_limit": 1,
        "sync_interval": 2,
        "sync_min_delay": 1,
        "sync_max_delay": 3,
        "max_retries": 3,
        "retry_backoff_base": 2
    }
}

config_data = defaults
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # Merge user configurations into defaults dict recursively
            for section, keys in user_config.items():
                if section in config_data and isinstance(keys, dict):
                    config_data[section].update(keys)
                else:
                    config_data[section] = keys
    except Exception as e:
        print(f"Error loading config file from {CONFIG_PATH}: {e}. Using defaults.")

# ========================================
# 5. Expose Configuration Constants (Backwards Compatible)
# ========================================
# Target Site
BASE_URL = config_data["target_site"].get("base_url")
LOGIN_URL = config_data["target_site"].get("login_url")
INDEX_SCAN_START_URL = config_data["target_site"].get("index_scan_start_url")
UPDATE_CHANNEL_PAGE_TEMPLATE = config_data["target_site"].get("update_channel_page_template")
INDEX_SCAN_END_URL = config_data["target_site"].get("index_scan_end_url")
TIME_BUFFER_HOURS = 24  # static buffer

# Pipeline
POST_CRAWL_BATCH_LIMIT = config_data["pipeline"].get("post_crawl_batch_limit")
QUEUE_MAX_SIZE = config_data["pipeline"].get("queue_max_size")
POST_MIN_DELAY = config_data["pipeline"].get("post_min_delay")
POST_MAX_DELAY = config_data["pipeline"].get("post_max_delay")
DEFAULT_BATCH_COUNT = config_data["pipeline"].get("default_batch_count")
START_PAGE = config_data["pipeline"].get("start_page")

# Safety
INDEX_SCAN_PAGE_LIMIT = config_data["safety"].get("index_scan_page_limit")
SAFE_THRESHOLD = config_data["safety"].get("safe_threshold")
MAX_POSTS_PER_RUN = config_data["safety"].get("max_posts_per_run")
MAX_RETRY_COUNT = config_data["safety"].get("max_retry_count")
BROWSER_RESTART_INTERVAL = config_data["safety"].get("browser_restart_interval")

# Debug
DEBUG_MODE = config_data["debug"].get("debug_mode")
DEBUG_LIMIT = config_data["debug"].get("debug_limit")
LOG_LEVEL = config_data["debug"].get("log_level")

# Database
DB_DIR = config_data["database"].get("db_dir")
DB_FILE = config_data["database"].get("db_file")
os.makedirs(DB_DIR, exist_ok=True)

# Delays (Converts lists from JSON back to python tuples)
INDEX_PAGE_DELAY = tuple(config_data["delays"].get("index_page_delay"))
INDEX_PAGE_LONG_SLEEP_INTERVAL = config_data["delays"].get("index_page_long_sleep_interval")
INDEX_PAGE_LONG_SLEEP = tuple(config_data["delays"].get("index_page_long_sleep"))
SOFT_404_RETRY_WAIT = config_data["delays"].get("soft_404_retry_wait")
SOFT_404_MAX_RETRIES = config_data["delays"].get("soft_404_max_retries")
DELAY_INDEX_MIN = config_data["delays"].get("delay_index_min")
DELAY_INDEX_MAX = config_data["delays"].get("delay_index_max")
DELAY_DETAIL_MIN = config_data["delays"].get("delay_detail_min")
DELAY_DETAIL_MAX = config_data["delays"].get("delay_detail_max")

# Legacy compatibility
DELAY_MIN = DELAY_DETAIL_MIN
DELAY_MAX = DELAY_DETAIL_MAX

# Paths
SCREENSHOT_DIR = config_data["paths"].get("screenshot_dir")
SCREENSHOT_PATH = config_data["paths"].get("screenshot_path")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# WordPress Settings
CATEGORY_GAME = config_data["wordpress"].get("category_game")
WP_CATEGORY_MAP = config_data["wordpress"].get("category_map")
WP_FIXED_TAGS = config_data["wordpress"].get("fixed_tags")
WP_TAG_KEYWORDS = config_data["wordpress"].get("tag_keywords")
WP_ICE_PRICE = config_data["wordpress"].get("ice_price")
WP_MEDIA_VERIFY_SSL = config_data["wordpress"].get("media_verify_ssl")
WP_MEDIA_TIMEOUT = config_data["wordpress"].get("media_timeout")
WP_SYNC_BATCH_LIMIT = config_data["wordpress"].get("sync_batch_limit")
WP_SYNC_INTERVAL = config_data["wordpress"].get("sync_interval")
WP_SYNC_MIN_DELAY = config_data["wordpress"].get("sync_min_delay")
WP_SYNC_MAX_DELAY = config_data["wordpress"].get("sync_max_delay")
WP_MAX_RETRIES = config_data["wordpress"].get("max_retries")
WP_RETRY_BACKOFF_BASE = config_data["wordpress"].get("retry_backoff_base")

# Crawl Status Codes
CRAWL_STATUS_PENDING = 0
CRAWL_STATUS_COMPLETED = 1
CRAWL_STATUS_NEEDS_UPDATE = 2
CRAWL_STATUS_DEAD_LETTER = 3
