import os
import json
from datetime import datetime
from core.log_formatter import logger
import config

AUTH_ALIVE = "ALIVE"
AUTH_DEAD = "DEAD"
AUTH_UNKNOWN = "UNKNOWN"

def check_auth_status(page):
    """
    Three-state probe verification of the session status.
    Returns: AUTH_ALIVE, AUTH_DEAD, or AUTH_UNKNOWN.
    """
    url = page.url
    logger.debug(f"Starting auth check probe on page: {url}")
    
    # Layer 2: Login page detection (Counter-evidence for DEAD session)
    if "Users/login" in url or "login" in url:
        logger.warning("Auth check: Login page URL detected. Session is DEAD.")
        return AUTH_DEAD
        
    try:
        # Check if username input is visible (e.g., input[name='username'] or input[type='password'])
        is_login_input_visible = page.locator("input[name='username']").is_visible(timeout=500)
        is_pwd_input_visible = page.locator("input[type='password']").is_visible(timeout=500)
        if is_login_input_visible or is_pwd_input_visible:
            logger.warning("Auth check: Login credentials inputs are visible. Session is DEAD.")
            return AUTH_DEAD
    except Exception as e:
        logger.debug(f"Error checking login input visibility: {e}")

    try:
        # Check for explicit "请先登录" text
        page_text = page.content()
        if "请先登录" in page_text:
            logger.warning("Auth check: '请先登录' text found in page. Session is DEAD.")
            return AUTH_DEAD
    except Exception as e:
        logger.debug(f"Error checking page content text: {e}")

    # Layer 1: Check User Center text (Boyong - gold standard validation)
    # If we are currently on the level_centre.html, check directly.
    if "level_centre.html" in url:
        try:
            if "boyong" in page_text:
                logger.info("Auth check: User 'boyong' found on User Center. Session is ALIVE.")
                return AUTH_ALIVE
        except Exception as e:
            logger.debug(f"Error reading User Center text: {e}")

    # Layer 3: Authenticated area element detection
    try:
        # #dailyLimit or "退出" link visible
        daily_limit_visible = page.locator("#dailyLimit").is_visible(timeout=500)
        logout_link_visible = page.locator("text='退出'").is_visible(timeout=500) or page.locator("a[href*='logout']").is_visible(timeout=500)
        if daily_limit_visible or logout_link_visible:
            logger.info("Auth check: Authenticated elements (#dailyLimit/logout link) are visible. Session is ALIVE.")
            return AUTH_ALIVE
    except Exception as e:
        logger.debug(f"Error checking authenticated elements: {e}")

    # Default to UNKNOWN (e.g., network timeout, non-user pages, etc.)
    logger.warning("Auth check: Unable to determine session state. Returning UNKNOWN.")
    return AUTH_UNKNOWN

def verify_session_via_user_center(context):
    """
    Gold standard verification: navigate to user center and check session state.
    """
    logger.info("Navigating to User Center for auth status verification...")
    user_center_url = f"{config.BASE_URL}/user/Level/level_centre.html"
    
    # Create a temporary page to avoid disrupting current page navigation
    page = context.new_page()
    try:
        page.goto(user_center_url, timeout=15000, wait_until="domcontentloaded")
        status = check_auth_status(page)
        
        if status == AUTH_DEAD:
            logger.error("Session verified as DEAD via User Center. Triggering Fail-Fast...")
            # Save diagnostic info before hard exit
            save_diagnostic_info(page, "auth_dead_fatal")
            page.close()
            os._exit(1)
        elif status == AUTH_UNKNOWN:
            logger.warning("Session status is UNKNOWN via User Center. Diagnostic screenshot saved.")
            save_diagnostic_info(page, "auth_unknown")
            
        page.close()
        return status
    except Exception as e:
        logger.error(f"Failed to navigate to User Center or verify session: {e}")
        try:
            save_diagnostic_info(page, "auth_navigation_failed")
        except Exception:
            pass
        try:
            page.close()
        except Exception:
            pass
        return AUTH_UNKNOWN

def save_diagnostic_info(page, suffix):
    """Save diagnostic screenshots, HTML, and cookies as specified in plans/08-auth-system.md"""
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Create directories
    screenshot_dir = os.path.join(".screenshots", date_str)
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(".debug/html", exist_ok=True)
    os.makedirs(".debug/network", exist_ok=True)
    
    screenshot_path = os.path.join(screenshot_dir, f"{now_str}_{suffix}.png")
    html_path = f".debug/html/{now_str}_{suffix}.html"
    cookies_path = f".debug/network/{now_str}_cookies.json"
    
    try:
        page.screenshot(path=screenshot_path)
        logger.info(f"Diagnostic screenshot saved to {screenshot_path}")
    except Exception as e:
        logger.warning(f"Failed to save diagnostic screenshot: {e}")
        
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        logger.info(f"Diagnostic HTML content saved to {html_path}")
    except Exception as e:
        logger.warning(f"Failed to save diagnostic HTML: {e}")
        
    try:
        cookies = page.context.cookies()
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4)
        logger.info(f"Diagnostic cookies state saved to {cookies_path}")
    except Exception as e:
        logger.warning(f"Failed to save diagnostic cookies: {e}")
