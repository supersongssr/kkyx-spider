import os
import random
import time
import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Ensure parent directory is in sys.path so we can import from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.log_formatter import logger
from core.auth import check_auth_status, AUTH_ALIVE, save_diagnostic_info
import config

def run_login():
    os.makedirs("auth", exist_ok=True)
    state_path = os.path.join("auth", "state.json")
    
    # Clear old state.json if present
    if os.path.exists(state_path):
        try:
            os.remove(state_path)
            logger.info("Cleared old state.json for a clean login session.")
        except Exception as e:
            logger.warning(f"Could not remove old state.json: {e}")

    with sync_playwright() as p:
        logger.info("Launching clean browser context for auto-login...")
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
        browser = p.chromium.launch(headless=True, args=args)
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='zh-CN',
            is_mobile=False,
            has_touch=False,
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        
        # Phase 1: Warm-up
        logger.info(f"Phase 1: Navigating to base URL: {config.BASE_URL}")
        page.goto(config.BASE_URL)
        sleep_time = random.uniform(2, 5)
        logger.info(f"Sleeping for {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)
        
        # Random scroll
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, 0)")
        except Exception as e:
            logger.warning(f"Failed warm-up scroll: {e}")
            
        # Phase 2: Navigate to login
        logger.info(f"Phase 2: Navigating to login URL: {config.LOGIN_URL}")
        page.goto(config.LOGIN_URL)
        time.sleep(2)
        
        # Phase 3: Fill credentials
        logger.info(f"Phase 3: Filling credentials for user: {config.USERNAME}")
        
        user_selectors = ["input[name='username']", "input[name='txtUser']", "#username", "#txtUser"]
        pwd_selectors = ["input[name='password']", "input[type='password']", "#password", "#txtPassword"]
        
        user_filled = False
        for selector in user_selectors:
            try:
                if page.locator(selector).is_visible(timeout=1000):
                    page.locator(selector).fill(config.USERNAME)
                    user_filled = True
                    logger.info(f"Filled username using selector: {selector}")
                    break
            except Exception:
                continue
                
        if not user_filled:
            logger.info("Standard username fill failed. Falling back to JS evaluate.")
            try:
                page.evaluate(f"() => {{ document.querySelector('input[type=\"text\"]').value = '{config.USERNAME}'; }}")
                user_filled = True
            except Exception as e:
                logger.error(f"JS username fill failed: {e}")
            
        pwd_filled = False
        for selector in pwd_selectors:
            try:
                if page.locator(selector).is_visible(timeout=1000):
                    page.locator(selector).fill(config.PASSWORD)
                    pwd_filled = True
                    logger.info(f"Filled password using selector: {selector}")
                    break
            except Exception:
                continue
                
        if not pwd_filled:
            logger.info("Standard password fill failed. Falling back to JS evaluate.")
            try:
                page.evaluate(f"() => {{ document.querySelector('input[type=\"password\"]').value = '{config.PASSWORD}'; }}")
                pwd_filled = True
            except Exception as e:
                logger.error(f"JS password fill failed: {e}")
            
        # Phase 4: Submit credentials
        logger.info("Phase 4: Submitting login credentials...")
        
        try:
            # First attempt: standard form submission via JS Form.submit()
            form_submitted = page.evaluate("""() => {
                const form = document.querySelector('form[action*="login"]') || document.querySelector('form');
                if (form) {
                    form.submit();
                    return true;
                }
                return false;
            }""")
            if form_submitted:
                logger.info("Submitted login form via JS Form.submit().")
                time.sleep(5)
            else:
                page.locator("button[type='submit'], input[type='submit'], .btn-login").click()
                logger.info("Clicked login button.")
                time.sleep(5)
        except Exception as e:
            logger.warning(f"Error submitting via form submit / click: {e}. Trying direct click on login button.")
            try:
                page.locator("input[type='submit']").click()
                time.sleep(5)
            except Exception as e2:
                logger.error(f"Fallback submit failed: {e2}")

        # Phase 5: Truth Test
        logger.info("Phase 5: Initiating Truth Test validation...")
        user_center_url = f"{config.BASE_URL}/user/Level/level_centre.html"
        try:
            page.goto(user_center_url, timeout=15000)
            time.sleep(3)
            
            status = check_auth_status(page)
            if status == AUTH_ALIVE:
                logger.info("Truth Test SUCCESS! User is authenticated and online.")
                context.storage_state(path=state_path)
                logger.info(f"Successfully saved storage state to {state_path}")
                browser.close()
                return True
            else:
                logger.error("Truth Test FAILED! Login was not successful.")
                save_diagnostic_info(page, "truth_test_failed")
                browser.close()
                return False
        except Exception as e:
            logger.error(f"Error during Truth Test navigation/validation: {e}")
            try:
                save_diagnostic_info(page, "truth_test_exception")
            except Exception:
                pass
            browser.close()
            return False

if __name__ == "__main__":
    success = run_login()
    if success:
        logger.info("Auto-login script execution succeeded.")
        sys.exit(0)
    else:
        logger.error("Auto-login script execution failed.")
        sys.exit(1)
