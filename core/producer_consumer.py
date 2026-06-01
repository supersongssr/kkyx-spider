import os
import re
import time
import random
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from core.log_formatter import logger
from core.auth import check_auth_status, AUTH_DEAD, verify_session_via_user_center
from core.html_image_processor import process_html_images
import config

class IndexProducer:
    def __init__(self, browser_handler, db_manager):
        self.bh = browser_handler
        self.db = db_manager

    def parse_page_num_from_url(self, url):
        """Extract page number from list_15_N url pattern."""
        if 'list_15_' in url:
            match = re.search(r'list_15_(\d+)', url)
            if match:
                return int(match.group(1))
        return 1

    def run(self):
        """
        Runs the Index Producer.
        Scans category list pages to discover game titles and URLs.
        """
        logger.info("[Producer] Starting Index Producer scanning process...")
        page = self.bh.page
        
        # Determine starting URL (Resume vs New Cycle)
        last_url = self.db.get_index_scan_last_url()
        cutoff_time = self.get_scan_cutoff_time()
        
        if last_url:
            logger.info(f"[Producer] Resume mode active. Continuing from last url: {last_url}")
            current_url = last_url
        else:
            logger.info("[Producer] New cycle mode active. Setting start timestamp.")
            self.db.set_index_scan_start_time(datetime.now().isoformat())
            current_url = config.INDEX_SCAN_START_URL
            
        page_count = 0
        total_discovered = 0
        
        while current_url:
            if page_count >= config.INDEX_SCAN_PAGE_LIMIT:
                logger.info(f"[Producer] Reached index page scan limit ({config.INDEX_SCAN_PAGE_LIMIT}). Retaining progress for next run.")
                break
                
            logger.info(f"[Producer] Navigating to index page: {current_url}")
            
            # Navigating with soft-404 handling
            success = self.navigate_with_soft_404_handling(page, current_url)
            if not success:
                logger.error(f"[Producer] Failed to load index page {current_url} after retries. Retaining progress.")
                break
                
            # Extract games from index page
            games = self.extract_games_from_page(page)
            logger.info(f"[Producer] Discovered {len(games)} games on current index page.")
            
            if not games:
                logger.warning("[Producer] No games found on page. Triggering empty-content fuse check.")
                break
                
            page_count += 1
            
            # Check watermark boundary
            past_watermark_count = 0
            for g in games:
                title = g['title']
                url = g['url']
                pub_date = g['publish_date']
                
                # Filter old content if cutoff time exists
                if self.is_past_watermark(pub_date, cutoff_time):
                    logger.debug(f"[Producer] Skipped (older than watermark): {title} ({pub_date})")
                    past_watermark_count += 1
                    continue
                    
                # Upsert into database (double-layer name/date update check)
                res = self.db.upsert_game_producer(title, url, pub_date)
                if res in ['inserted', 'updated']:
                    total_discovered += 1
                    
            logger.info(f"[Producer] Page statistics: {len(games)} found, {past_watermark_count} past watermark, {total_discovered} newly added/updated.")
            
            # If ALL games on the page were older than the watermark, terminate the cycle
            if len(games) > 0 and past_watermark_count == len(games):
                logger.info("[Producer] All games on current page are older than watermark limit. Finalizing scanning cycle.")
                self.finalize_cycle()
                break
                
            # Update last URL progress for safety
            self.db.set_index_scan_last_url(current_url)
            
            # Check physical boundary stop
            if current_url.rstrip('/') == config.INDEX_SCAN_END_URL.rstrip('/'):
                logger.info(f"[Producer] Reached physical scan end URL boundary: {config.INDEX_SCAN_END_URL}. Finalizing.")
                self.finalize_cycle()
                break
                
            # Construct next page URL
            next_url = self.get_next_page_url(current_url)
            if not next_url:
                logger.error("[Producer] Unable to construct next page URL. Terminating.")
                break
                
            current_url = next_url
            
            # Apply anti-detection random delays
            delay = random.uniform(*config.INDEX_PAGE_DELAY)
            logger.info(f"[Producer] Anti-detection pause: sleeping for {delay:.2f} seconds...")
            time.sleep(delay)
            
            # Long sleep interval
            if page_count % config.INDEX_PAGE_LONG_SLEEP_INTERVAL == 0:
                long_sleep = random.uniform(*config.INDEX_PAGE_LONG_SLEEP)
                logger.info(f"[Producer] Long anti-detection sleep: sleeping for {long_sleep:.2f} seconds...")
                time.sleep(long_sleep)
                
        logger.info(f"[Producer] Scanning complete. Total newly added/updated games this run: {total_discovered}")

    def navigate_with_soft_404_handling(self, page, url):
        """Navigate to URL and handle Soft 404 (empty/blank pages) with retries."""
        for attempt in range(config.SOFT_404_MAX_RETRIES + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2) # Allow JS to execute/render list
                
                # Evaluate if page is a soft or hard 404
                check = page.evaluate('''() => {
                    const title = document.title || "";
                    const gameLinks = document.querySelectorAll('a[href*="/qbyx/"]');
                    const hasGameLinks = gameLinks.length > 0;
                    return {
                        is_404: title.includes("404") || !hasGameLinks,
                        is_hard: title.includes("404")
                    };
                }''')
                
                if not check['is_404']:
                    return True # Page is good
                    
                if check['is_hard']:
                    logger.error(f"[Producer] Hard 404 encountered on {url}.")
                    return False
                    
                logger.warning(f"[Producer] Soft 404 (empty page content) detected on {url}. Attempt {attempt+1}/{config.SOFT_404_MAX_RETRIES+1}. Retrying in {config.SOFT_404_RETRY_WAIT} seconds...")
                time.sleep(config.SOFT_404_RETRY_WAIT)
            except Exception as e:
                logger.warning(f"[Producer] Exception loading page {url}: {e}")
                time.sleep(5)
                
        return False

    def extract_games_from_page(self, page):
        """Inject JavaScript into list page to pull structured game info directly from DOM."""
        games = page.evaluate('''() => {
            const results = [];
            const titleBlacklist = ['查看', '更多', '详情', '点击', '下载', '进入'];
            
            // Strategy 1: Container-based extraction (preferred)
            const containers = document.querySelectorAll('li, .item, .game-item');
            containers.forEach(c => {
                const a = c.querySelector('a[href*="/qbyx/"]');
                if (!a) return;
                
                const href = a.href;
                let title = a.title || a.innerText || "";
                title = title.trim();
                
                // Skip if title matches blacklist keyword
                if (titleBlacklist.some(word => title.includes(word))) return;
                
                // Find date
                let dateStr = "";
                const dateEl = c.querySelector('.time, .date, span, p');
                if (dateEl) {
                    const match = dateEl.innerText.match(/\\d{4}-\\d{2}-\\d{2}/);
                    if (match) dateStr = match[0];
                }
                
                if (href && title) {
                    results.push({
                        title: title,
                        url: href,
                        publish_date: dateStr || new Date().toISOString().split('T')[0]
                    });
                }
            });
            
            // Strategy 2: Fallback to direct links if container extraction returns nothing
            if (results.length === 0) {
                document.querySelectorAll('a[href*="/qbyx/"]').forEach(a => {
                    const href = a.href;
                    let title = a.title || a.innerText || "";
                    title = title.trim();
                    if (title && !titleBlacklist.some(word => title.includes(word))) {
                        results.push({
                            title: title,
                            url: href,
                            publish_date: new Date().toISOString().split('T')[0]
                        });
                    }
                });
            }
            
            // Deduplicate local items
            const seen = new Set();
            return results.filter(item => {
                const duplicate = seen.has(item.url);
                seen.add(item.url);
                return !duplicate;
            });
        }''')
        return games

    def get_scan_cutoff_time(self):
        """Calculate the datetime boundary for incremental scanning watermark."""
        end_time_str = self.db.get_index_scan_end_time()
        if not end_time_str:
            return None # Full scan mode: get all historical content
            
        try:
            end_time = datetime.fromisoformat(end_time_str)
            return (end_time - timedelta(hours=config.TIME_BUFFER_HOURS)).isoformat()
        except Exception:
            return None

    def is_past_watermark(self, publish_date, cutoff_time):
        """Compare publish date to check if it's older than our cutoff time."""
        if not cutoff_time or not publish_date:
            return False # First run / full scan: never skip
            
        try:
            return publish_date < cutoff_time.split('T')[0]
        except Exception:
            return False

    def get_next_page_url(self, current_url):
        """Construct the next page URL programmatically without DOM dependency."""
        base_url = config.BASE_URL
        start_url = config.INDEX_SCAN_START_URL
        
        current_page = self.parse_page_num_from_url(current_url)
        next_page = current_page + 1
        
        if '/list_' in current_url:
            return re.sub(r'/list_15_\d+', f'/list_15_{next_page}', current_url)
            
        if current_url.rstrip('/') == start_url.rstrip('/'):
            return f"{base_url}/update/list_15_{next_page}/"
            
        return None

    def finalize_cycle(self):
        """Finalize the current index scanning cycle by saving the start anchor time to end time."""
        start_time = self.db.get_index_scan_start_time()
        if start_time:
            self.db.set_index_scan_end_time(start_time)
        self.db.set_index_scan_last_url(None)
        logger.info("[Producer] Scanning cycle completed successfully. Watermarks updated.")


class PostConsumer:
    def __init__(self, browser_handler, db_manager):
        self.bh = browser_handler
        self.db = db_manager

    def run(self):
        """
        Runs the Post Consumer.
        Retrieves pending/needs-update games and crawls details, downloading image assets and网盘 links.
        """
        logger.info("[Consumer] Starting Detail Post Consumer process...")
        context = self.bh.context
        page = self.bh.page
        
        # Verify and fetch daily quota limits
        try:
            quota = self.check_daily_quota(context)
            logger.info(f"[Consumer] Official Remaining Quota: {quota['today_remaining']} / {quota['daily_limit']}")
            
            # Quota Safeguard thresholds
            if quota['today_remaining'] <= config.SAFE_THRESHOLD:
                logger.warning(f"[Consumer] Remaining quota ({quota['today_remaining']}) is at or below safe threshold ({config.SAFE_THRESHOLD}). Aborting consumer batch.")
                return
                
            effective_quota = min(quota['today_remaining'], config.MAX_POSTS_PER_RUN)
        except Exception as e:
            logger.warning(f"[Consumer] Could not verify remaining quota from User Center: {e}. Defaulting ceiling limit.")
            effective_quota = config.MAX_POSTS_PER_RUN
            
        logger.info(f"[Consumer] Effective post crawl batch limit: {effective_quota}")
        
        # Retrieve tasks from database sorted by random weights
        tasks = self.db.get_pending_or_needs_update_tasks(effective_quota)
        logger.info(f"[Consumer] Retrieved {len(tasks)} tasks to crawl.")
        
        if not tasks:
            logger.info("[Consumer] No pending tasks in database queue. Detail harvesting completed.")
            return
            
        processed_count = 0
        for task in tasks:
            game_id = task['id']
            title = task['title']
            url = task['source_url']
            retry_count = task['retry_count']
            
            logger.info(f"\n[Consumer] Progress {processed_count+1}/{len(tasks)} | ID: {game_id} | Title: {title}")
            
            # Memory Hygiene: Restart browser context every N posts
            if processed_count > 0 and processed_count % config.BROWSER_RESTART_INTERVAL == 0:
                self.bh.restart()
                page = self.bh.page
                context = self.bh.context
                
            # Process single game detail page
            success = self.process_game_post(page, context, game_id, title, url)
            
            if success:
                processed_count += 1
            else:
                # Increment retry counter
                self.db.increment_retry_count(game_id)
                
            # Random delay between detail tasks (anti-detection)
            delay = random.uniform(*config.INDEX_PAGE_DELAY)
            logger.info(f"[Consumer] Anti-detection detail delay: sleeping for {delay:.2f} seconds...")
            time.sleep(delay)
            
        logger.info(f"[Consumer] Consumer batch run complete. Processed {processed_count} posts successfully.")

    def check_daily_quota(self, context):
        """Retrieve the official daily download/remaining quotas from User Center page."""
        page = context.new_page()
        try:
            page.goto(f"{config.BASE_URL}/user/Level/level_centre.html", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)
            
            # Read quota values
            daily_limit = page.locator("#dailyLimit").inner_text(timeout=5000)
            today_remaining = page.locator("#todayRemaining").inner_text(timeout=5000)
            
            page.close()
            return {
                'daily_limit': int(daily_limit.strip()),
                'today_remaining': int(today_remaining.strip())
            }
        except Exception as e:
            try:
                page.close()
            except Exception:
                pass
            raise e

    def process_game_post(self, page, context, game_id, title, url):
        """Crawl details of a single game, extract content, and download associated images and pan links."""
        try:
            logger.info(f"[Consumer] Navigating to detail page: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(2)
            
            # Verify authentication (tripwire check)
            if "login" in page.url:
                logger.warning("[Consumer] Tripwire triggered: Redirected to login page. Session expired.")
                verify_session_via_user_center(context) # Will trigger Fail-Fast os._exit(1) if dead
                return False
                
            # Check for premium content buy button as warning indicator
            buy_btn_visible = page.locator(".buy-btn, a[href*='buy'], button[id*='buy']").is_visible(timeout=500)
            if buy_btn_visible:
                logger.warning(f"[Consumer] Premium buy element detected on page {url}. Session might be restricted.")
                
            # 1. Title and basic metadata
            page_title = page.title()
            
            # 2. Extract HTML Description
            description = page.evaluate('''() => {
                const el = document.querySelector('.content-text') || document.querySelector('.article-content') || document.querySelector('.entry-content');
                return el ? el.innerHTML : '';
            }''')
            
            if not description:
                logger.error(f"[Consumer] Empty description content on page {url}")
                return False
                
            # 3. Extract publish date
            pub_date = self.extract_publish_date(page)
            
            # 4. Extract extract password
            extract_pwd = self.extract_zip_password(page)
            
            # 5. UI physical click-extraction for download netdisk links
            download_links = self.extract_ui_download_links(page, context)
            
            if not download_links:
                logger.warning(f"[Consumer] Zero netdisk download links retrieved for {title}. Verifying session...")
                auth_status = verify_session_via_user_center(context)
                if auth_status == AUTH_DEAD:
                    # Session verified dead -> exit immediately
                    os._exit(1)
                else:
                    logger.warning("[Consumer] Session is ALIVE, but resource truly has no downloadable assets. Marking task as processed.")
                    
            # 6. Process image assets with double-layer deduplication (and local flat landing)
            updated_description, assets = process_html_images(page, description, game_id, self.db)
            
            # Determine main pan URL and password for backward-compatibility fields
            pan_url = ""
            access_password = ""
            if download_links:
                pan_url = download_links[0]['url']
                access_password = download_links[0]['password']
                
            # 7. Update database record with harvested content
            self.db.update_game_consumer(
                game_id=game_id,
                pan_url=pan_url,
                access_password=access_password,
                extract_password=extract_pwd,
                description=updated_description,
                download_links=download_links,
                crawl_status=config.CRAWL_STATUS_COMPLETED
            )
            
            # Print elegant structured receipt as required in plans/05-post-consumer.md
            self.print_game_receipt(title, game_id, len(description), extract_pwd, len(assets), download_links)
            return True
            
        except Exception as e:
            logger.error(f"[Consumer] Failed to process game ID {game_id} ({title}) details: {e}")
            return False

    def extract_publish_date(self, page):
        """Extract YYYY-MM-DD from detail page content using regex."""
        try:
            content_text = page.content()
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', content_text)
            if date_match:
                return date_match.group(0)
        except Exception:
            pass
        return datetime.now().strftime("%Y-%m-%d")

    def extract_zip_password(self, page):
        """Extract game zip extraction password using precise regex matches."""
        try:
            content_text = page.content()
            # Match various forms of "解压密码"
            patterns = [
                r'解压密码\s*[:：]\s*([a-zA-Z0-9\.\_\-]+)',
                r'解压码\s*[:：]\s*([a-zA-Z0-9\.\_\-]+)',
                r'密码\s*[:：]\s*([a-zA-Z0-9\.\_\-]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, content_text, re.IGNORECASE)
                if match:
                    # Avoid capturing generic site URLs unless they are truly the password
                    pwd = match.group(1).strip()
                    if pwd:
                        return pwd
        except Exception:
            pass
        return "www.kkyx.net" # Default standard site fallback

    def extract_ui_download_links(self, page, context):
        """Simulate clicks on download buttons to extract Baidu/Quark/Alipan links."""
        download_links = []
        
        # Inject Javascript to locate all download buttons index and click them safely
        buttons_count = page.evaluate('''() => {
            const btns = document.querySelectorAll('.action-buttons a.btn-download, a[href*="down"], .btn-download, .download-btn');
            return btns.length;
        }''')
        
        logger.info(f"[Consumer] Found {buttons_count} download buttons to evaluate.")
        
        for i in range(buttons_count):
            try:
                # Strategy A: expectancy popup capture (JS evaluate click to avoid overlay bugs)
                with page.context.expect_page(timeout=10000) as popup_info:
                    page.evaluate(f'''() => {{
                        const btns = document.querySelectorAll('.action-buttons a.btn-download, a[href*="down"], .btn-download, .download-btn');
                        if (btns[{i}]) {{
                            btns[{i}].scrollIntoView({{ behavior: 'instant', block: 'center' }});
                            btns[{i}].click();
                        }}
                    }}''')
                popup = popup_info.value
                popup.wait_for_load_state("domcontentloaded")
                
                # Check for home page redirection (auth failure indication)
                if popup.url.rstrip('/') == config.BASE_URL.rstrip('/'):
                    logger.warning("[Consumer] Download popup redirected to home page. Capturing auth state check...")
                    popup.close()
                    auth = verify_session_via_user_center(context)
                    if auth == AUTH_DEAD:
                        os._exit(1)
                    continue
                    
                # Standard netdisk parser
                pan_url = popup.url
                password = self.parse_netdisk_password_from_page(popup)
                
                if pan_url and ("pan.baidu.com" in pan_url or "cloud.189.cn" in pan_url or "pan.xunlei.com" in pan_url or "pan.quark.cn" in pan_url or "alipan.com" in pan_url or "drive.uc.cn" in pan_url):
                    download_links.append({
                        'platform': self.detect_pan_platform(pan_url),
                        'url': pan_url,
                        'password': password
                    })
                popup.close()
                
            except Exception as e:
                logger.debug(f"[Consumer] Strategy A failed for button index {i}: {e}. Attempting Strategy B...")
                
                # Strategy B: DOM Modal parser inside current page
                # Some sites render a modal with netdisk links in the page after clicking
                try:
                    # Re-trigger click without expect_popup
                    page.evaluate(f'''() => {{
                        const btns = document.querySelectorAll('.action-buttons a.btn-download, a[href*="down"], .btn-download, .download-btn');
                        if (btns[{i}]) btns[{i}].click();
                    }}''')
                    time.sleep(2) # Allow modal to pop-in
                    
                    # Extract any links from the current page's modal/content
                    modal_links = page.evaluate('''() => {
                        const links = [];
                        document.querySelectorAll('a').forEach(a => {
                            const href = a.href || "";
                            if (href.includes("baidu.com") || href.includes("189.cn") || href.includes("xunlei.com") || href.includes("quark.cn") || href.includes("alipan.com")) {
                                // Locate password in parent container
                                let parent = a.parentElement;
                                let pwd = "";
                                for (let depth = 0; depth < 3; depth++) {
                                    if (!parent) break;
                                    const text = parent.innerText || "";
                                    const match = text.match(/(?:密码|访问码|提取码)[:：]\\s*([a-zA-Z0-9]{4})/);
                                    if (match) {
                                        pwd = match[1];
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                                links.push({ url: href, pwd: pwd });
                            }
                        });
                        return links;
                    }''')
                    
                    for ml in modal_links:
                        download_links.append({
                            'platform': self.detect_pan_platform(ml['url']),
                            'url': ml['url'],
                            'password': ml['pwd']
                        })
                except Exception as ex:
                    logger.debug(f"[Consumer] Strategy B failed: {ex}")
                    
        # Strategy C: Hard fallback parsing from raw href if no interactions triggered
        if not download_links:
            logger.info("[Consumer] Clicks did not produce popup or modal. Applying Strategy C fallback parsing...")
            fallback_links = page.evaluate('''() => {
                const links = [];
                document.querySelectorAll('a').forEach(a => {
                    const href = a.href || "";
                    if (href.includes("baidu.com") || href.includes("189.cn") || href.includes("xunlei.com") || href.includes("quark.cn") || href.includes("alipan.com")) {
                        links.push(href);
                    }
                });
                return links;
            }''')
            for fl in fallback_links:
                download_links.append({
                    'platform': self.detect_pan_platform(fl),
                    'url': fl,
                    'password': ''
                })
                
        # Remove duplicate pan URLs
        seen = set()
        unique_links = []
        for dl in download_links:
            if dl['url'] not in seen:
                seen.add(dl['url'])
                unique_links.append(dl)
                
        return unique_links

    def detect_pan_platform(self, url):
        """Map URL domain to netdisk platform names."""
        if 'baidu.com' in url:
            return '百度网盘'
        elif '189.cn' in url:
            return '天翼云盘'
        elif 'xunlei.com' in url:
            return '迅雷云盘'
        elif 'quark.cn' in url:
            return '夸克网盘'
        elif 'alipan.com' in url or 'aliyundrive.com' in url:
            return '阿里云盘'
        return '其他云盘'

    def parse_netdisk_password_from_page(self, page):
        """Parse access passwords from popup page URLs or content."""
        try:
            url = page.url
            # 1. Parse from URL parameters (e.g. ?pwd=xxxx or ?code=xxxx)
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            queries = parse_qs(parsed.query)
            if 'pwd' in queries:
                return queries['pwd'][0]
            if 'code' in queries:
                return queries['code'][0]
                
            # 2. Match standard Chinese patterns from body content
            body_text = page.locator("body").inner_text(timeout=2000)
            pwd_match = re.search(r'(?:密码|提取码|访问码|提取码)[:：]\s*([a-zA-Z0-9]{4})', body_text)
            if pwd_match:
                return pwd_match.group(1).strip()
        except Exception:
            pass
        return ""

    def print_game_receipt(self, title, game_id, content_len, extract_pwd, asset_count, links):
        """Format and print structure receipt as required in plans/05-post-consumer.md"""
        receipt = f"""
[Consumer] ID: {game_id} | 标题: 《{title}》
┣━ 1. 页面获取: ✅ 成功
┣━ 2. 游戏正文: ✅ 成功 ({content_len}字)
┣━ 3. 解压密码: ✅ 成功 (pwd: {extract_pwd})
┣━ 4. 图片资产: ✅ 成功下载落地 {asset_count} 张
┣━ 5. 下载地址: ✅ 成功提取 {len(links)} 条"""
        for dl in links:
            receipt += f"\n┃  👉 {dl['platform']}: {dl['url']} (密码: {dl['password'] or '无'})"
        receipt += "\n┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        logger.info(receipt)
