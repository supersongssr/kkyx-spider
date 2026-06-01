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
        page.goto(config.BASE_URL, wait_until="domcontentloaded")
        sleep_time = random.uniform(2, 5)
        logger.info(f"Sleeping for {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)
        
        # Phase 2: Open login modal
        logger.info("Phase 2: Clicking login button to open popup modal...")
        try:
            page.locator("#loginBtn").click()
            time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to click login button: {e}")
            save_diagnostic_info(page, "modal_open_failed")
            browser.close()
            return False
            
        # Phase 3: Fill credentials in modal
        logger.info(f"Phase 3: Filling credentials in modal for user: {config.USERNAME}")
        try:
            page.locator("#loginEmail").fill(config.USERNAME)
            page.locator("#loginPassword").fill(config.PASSWORD)
            time.sleep(1)
        except Exception as e:
            logger.error(f"Failed to fill login inputs in modal: {e}")
            save_diagnostic_info(page, "modal_fill_failed")
            browser.close()
            return False
            
        # Phase 4: Submit modal login
        logger.info("Phase 4: Clicking modal submit button...")
        try:
            page.locator(".login-submit-btn").click()
            time.sleep(5)
        except Exception as e:
            logger.error(f"Failed to click modal submit button: {e}")
            save_diagnostic_info(page, "modal_submit_failed")
            browser.close()
            return False

        # Phase 5: Truth Test
        logger.info("Phase 5: Initiating Truth Test validation at User Center...")
        user_center_url = f"{config.BASE_URL}/user/Level/level_centre.html"
        try:
            page.goto(user_center_url, timeout=15000, wait_until="domcontentloaded")
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
