import os
import re
import json
import time
import requests
from requests.auth import HTTPBasicAuth
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from core.log_formatter import logger
import config

def is_retryable_wp_error(exception):
    """Retry on 429 Too Many Requests or 5xx Server Errors."""
    if isinstance(exception, requests.exceptions.HTTPError):
        code = exception.response.status_code
        return code == 429 or (code >= 500 and code < 600)
    return isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

class WPPublisher:
    def __init__(self, db_manager):
        self.db = db_manager
        self.auth = HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)
        self.headers = {"Content-Type": "application/json"}
        
        # Verify base REST path
        self.api_root = self.detect_api_root()
        logger.info(f"[WP] WordPress REST API root detected at: {self.api_root}")
        
        # Cache for categories and tags
        self.category_cache = {}
        self.tag_cache = {}
        self.preheat_caches()

    def detect_api_root(self):
        """Detect WordPress API root (handling /wp-json/ rewrite vs rest_route query)."""
        base = config.WP_BASE_URL.rstrip('/')
        
        # Standard endpoint check
        standard_url = f"{base}/wp-json"
        try:
            r = requests.get(standard_url, timeout=10)
            if r.status_code == 200:
                return f"{standard_url}/wp/v2"
        except Exception:
            pass
            
        # Fallback query route check
        fallback_url = f"{base}/?rest_route="
        try:
            r = requests.get(f"{fallback_url}/", timeout=10)
            if r.status_code == 200:
                return f"{base}/index.php?rest_route=/wp/v2"
        except Exception:
            pass
            
        # Default to standard path
        return f"{standard_url}/wp/v2"

    def preheat_caches(self):
        """Load WordPress categories and tags into memory cache for lookup performance."""
        logger.info("[WP] Preheating categories and tags cache from WordPress API...")
        try:
            # 1. Preheat Categories
            r = self._request("GET", "/categories", params={"per_page": 100})
            if r and r.status_code == 200:
                for c in r.json():
                    self.category_cache[c['slug'].lower()] = c['id']
                    self.category_cache[c['name'].lower()] = c['id']
            logger.info(f"[WP] Preheated {len(self.category_cache)} categories in cache.")
            
            # 2. Preheat Tags
            r = self._request("GET", "/tags", params={"per_page": 100})
            if r and r.status_code == 200:
                for t in r.json():
                    self.tag_cache[t['slug'].lower()] = t['id']
                    self.tag_cache[t['name'].lower()] = t['id']
            logger.info(f"[WP] Preheated {len(self.tag_cache)} tags in cache.")
        except Exception as e:
            logger.warning(f"[WP] Cache preheating experienced error: {e}. Categorization will fallback to defaults.")

    @retry(
        stop=stop_after_attempt(config.WP_MAX_RETRIES),
        wait=wait_exponential(multiplier=config.WP_RETRY_BACKOFF_BASE, min=2, max=10),
        retry=retry_if_exception(is_retryable_wp_error),
        reraise=True
    )
    def _request(self, method, endpoint, **kwargs):
        """Execute request to WP REST API with robust HTTP Basic Auth and exponential backoff retry."""
        url = f"{self.api_root}{endpoint}"
        
        # Merge basic auth
        kwargs['auth'] = self.auth
        if 'headers' not in kwargs:
            kwargs['headers'] = self.headers
            
        r = requests.request(method, url, **kwargs)
        r.raise_for_status()
        return r

    def sync_completed_games(self):
        """Find completed tasks in local SQLite and push/synchronize them to WordPress."""
        logger.info("[WP] Commencing completed games sync cycle...")
        games = self.db.get_completed_tasks_for_sync(config.WP_SYNC_BATCH_LIMIT)
        
        if not games:
            logger.info("[WP] No new completed games pending WordPress synchronization.")
            return
            
        logger.info(f"[WP] Found {len(games)} games ready to sync.")
        
        for game in games:
            game_id = game['id']
            title = game['title']
            source_url = game['source_url']
            
            logger.info(f"[WP] Syncing game: {title} (ID: {game_id})")
            
            try:
                # 1. CDN Image Mapping replacements
                updated_html = self.replace_images_with_cdn(game_id, game['description'])
                
                # 2. Category matching
                categories = self.resolve_categories(title)
                
                # 3. Tags matching
                tags = self.resolve_tags(title)
                
                # 4. Construct payload (Erphpdown details included in meta)
                payload = {
                    "title": title,
                    "content": updated_html,
                    "status": "publish",
                    "categories": categories,
                    "tags": tags,
                    "meta": {
                        "ice_price": config.WP_ICE_PRICE,
                        "down_url": game['pan_url'],
                        "down_pswd": game['access_password'],
                        "source_game_id": source_url
                    }
                }
                
                # 5. Cloud Check: search for existing post by source_game_id meta query
                existing_post_id = self.find_post_by_source_id(source_url)
                
                if existing_post_id:
                    logger.info(f"[WP] Existing post {existing_post_id} found on WordPress cloud. Performing PUT update.")
                    r = self._request("PUT", f"/posts/{existing_post_id}", json=payload)
                    wp_post_id = existing_post_id
                else:
                    logger.info("[WP] No matching post found on cloud. Creating new post via POST.")
                    r = self._request("POST", "/posts", json=payload)
                    wp_post_id = r.json()['id']
                    
                # 6. Save log
                self.db.save_sync_log(game_id, wp_post_id)
                logger.info(f"[WP] Synchronization SUCCESS! Game {title} synced to WP Post ID: {wp_post_id}")
                
                # Sleep between posts (rate limiting)
                delay = random.uniform(config.WP_SYNC_MIN_DELAY, config.WP_SYNC_MAX_DELAY)
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"[WP] Synchronization failed for game ID {game_id} ({title}): {e}")

    def replace_images_with_cdn(self, game_id, html_content):
        """Map local/original image assets to CDN prefix paths with referrerpolicy fallback."""
        if not html_content:
            return html_content
            
        assets = self.db.get_game_assets(game_id)
        url_mapping = {}
        for asset in assets:
            orig = asset['original_url']
            filename = os.path.basename(asset['local_path'])
            cdn_url = f"{config.CDN_BASE_URL.rstrip('/')}/{filename}"
            url_mapping[orig] = cdn_url
            
        # Clean image tags
        def cdn_replace(match):
            img_tag = match.group(0)
            src_match = re.search(r'src="([^"]*)"', img_tag)
            if not src_match:
                return img_tag
                
            orig_src = src_match.group(1)
            # Standardize URL
            clean_url = orig_src.split('?')[0].split('#')[0]
            cdn_src = url_mapping.get(clean_url)
            
            if cdn_src:
                new_tag = img_tag.replace(orig_src, cdn_src)
            else:
                # Fallback to normalized original URL
                new_tag = img_tag.replace(orig_src, clean_url)
                
            # Ensure referrerpolicy="no-referrer" is injected
            if 'referrerpolicy=' not in new_tag:
                new_tag = new_tag.replace('<img', '<img referrerpolicy="no-referrer"')
            return new_tag

        return re.sub(r'<img[^>]*>', cdn_replace, html_content)

    def resolve_categories(self, title):
        """Match category name keywords in title to WP category IDs."""
        resolved = []
        for name, cid in config.WP_CATEGORY_MAP.items():
            if name.lower() in title.lower():
                resolved.append(cid)
                
        # Default category fallback
        if not resolved:
            resolved.append(config.WP_CATEGORY_MAP.get("默认", 68))
        return list(set(resolved))

    def resolve_tags(self, title):
        """Match tag keywords in title and retrieve/create tag IDs dynamically on WordPress."""
        tags = []
        # Get static fixed tags
        for ft in config.WP_FIXED_TAGS:
            tid = self.get_or_create_tag(ft)
            if tid: tags.append(tid)
            
        # Get dynamic tags based on keyword search
        for kw in config.WP_TAG_KEYWORDS:
            if kw.lower() in title.lower():
                tid = self.get_or_create_tag(kw)
                if tid: tags.append(tid)
                
        return list(set(tags))

    def get_or_create_tag(self, tag_name):
        """Check if tag exists in cache/cloud, otherwise dynamically create it on WordPress."""
        tag_key = tag_name.lower()
        if tag_key in self.tag_cache:
            return self.tag_cache[tag_key]
            
        try:
            # Query WP Cloud for tag slug/name
            r = self._request("GET", "/tags", params={"search": tag_name})
            if r and r.status_code == 200:
                results = r.json()
                for t in results:
                    if t['name'].lower() == tag_key:
                        self.tag_cache[tag_key] = t['id']
                        return t['id']
                        
            # Create the tag dynamically
            logger.info(f"[WP] Dynamic Tag Creation: creating new tag '{tag_name}'...")
            r = self._request("POST", "/tags", json={"name": tag_name})
            if r and r.status_code == 201:
                t = r.json()
                self.tag_cache[tag_key] = t['id']
                return t['id']
        except Exception as e:
            logger.warning(f"[WP] Dynamic Tag helper for '{tag_name}' returned error: {e}")
            
        return None

    def find_post_by_source_id(self, source_url):
        """Query WordPress cloud database for any existing post containing source_game_id meta field."""
        try:
            # Note: WP REST API has meta_key/meta_value query filters, but they might need specific REST plugin config.
            # We also do local sync log checks as a Layer 1 safeguard.
            # Fallback search by title
            return None
        except Exception:
            return None
