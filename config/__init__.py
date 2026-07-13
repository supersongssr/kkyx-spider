"""
KKYX Spider Configurations (TOML-based loader, package form)

================================================================================
CONFIGURATION HIERARCHY (Priority from high to low):
1. .config.toml              (local overrides, optional, NOT in Git)
2. config.default.toml       (default values, committed to Git)

All configuration lives in TOML. There is no .env file anymore.
Sensitive credentials (KKYX account, WordPress keys, CDN URL) are stored in
.config.toml with empty defaults in config.default.toml.

NOTE: Both TOML files live in the PROJECT ROOT (user-facing). This file
(config/__init__.py) is only the loader code that reads them.

================================================================================
REQUIRED KEYS (must be set in .config.toml, left empty in default.toml):
- kkyx.username       KKYX Net username (website login)
- kkyx.password       KKYX Net password (website login)

OPTIONAL KEYS (empty by default; fill in .config.toml if needed):
- wordpress.base_url        WordPress site root URL
- wordpress.username        WordPress admin username
- wordpress.app_password    WordPress Application Password (REST API auth)
- cdn.base_url              CDN base URL for media upload/reference

================================================================================
LOCAL OVERRIDE (.config.toml):
Create a .config.toml in the PROJECT ROOT to override any default value.
Only the keys you specify are merged in (deep merge). Example:

    # .config.toml
    [kkyx]
    username = "your_account"
    password = "your_password"

    [safety]
    index_scan_page_limit = 10

The .config.toml file is optional and listed in .gitignore.
See docs/CONFIGURATION.md for more details.
================================================================================
"""

import tomllib
from pathlib import Path

# Package layout: this file is config/__init__.py (loader code).
# Both TOML files are user-facing and live in the PROJECT ROOT:
#   - config.default.toml   default values (committed to Git)
#   - .config.toml          local overrides (NOT in Git)
_CONFIG_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CONFIG_DIR.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.default.toml"
_LOCAL_CONFIG_PATH = _PROJECT_ROOT / ".config.toml"


# ==============================================================================
# 1. Load Default Configurations (config.default.toml)
# ==============================================================================
if not _DEFAULT_CONFIG_PATH.exists():
    raise FileNotFoundError(
        f"Default configuration file not found: {_DEFAULT_CONFIG_PATH}\n"
        "This file is required and should be committed at the project root."
    )

with open(_DEFAULT_CONFIG_PATH, "rb") as f:
    config_data = tomllib.load(f)


# ==============================================================================
# 2. Deep-Merge Local Overrides from .config.toml (if exists)
# ==============================================================================
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into ``base`` (in-place) and return ``base``."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


if _LOCAL_CONFIG_PATH.exists():
    try:
        with open(_LOCAL_CONFIG_PATH, "rb") as f:
            _deep_merge(config_data, tomllib.load(f))
        print(f"Loaded local configuration overrides from .config.toml")
    except (tomllib.TOMLDecodeError, OSError) as e:
        print(f"Error loading .config.toml: {e}. Using defaults.")


# ==============================================================================
# 3. Validate Required Credentials
# ==============================================================================
USERNAME = config_data.get("kkyx", {}).get("username")
PASSWORD = config_data.get("kkyx", {}).get("password")

missing_params = []
if not USERNAME:
    missing_params.append("kkyx.username")
if not PASSWORD:
    missing_params.append("kkyx.password")

if missing_params:
    raise ValueError(
        f"Missing required configuration key(s): {', '.join(missing_params)}!\n"
        "Please set these in your .config.toml (project root).\n"
        "Refer to the parameter documentation at the beginning of config/__init__.py."
    )


# ========================================
# 4. Optional Credentials (from TOML)
# ========================================
WP_BASE_URL = config_data.get("wordpress", {}).get("base_url", "")
WP_USERNAME = config_data.get("wordpress", {}).get("username", "")
WP_APP_PASSWORD = config_data.get("wordpress", {}).get("app_password", "")
CDN_BASE_URL = config_data.get("cdn", {}).get("base_url", "")


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
import os

DB_DIR = config_data["database"].get("db_dir")
DB_FILE = config_data["database"].get("db_file")
STORAGE_DIR = config_data["database"].get("storage_dir", ".data/storage")
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

# Delays (TOML arrays are converted to Python tuples for delay ranges)
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
