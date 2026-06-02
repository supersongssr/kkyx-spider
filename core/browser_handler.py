import time
import os
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from core.log_formatter import logger
import config

class BrowserHandler:
    def __init__(self, storage_state_path=None):
        self.storage_state_path = storage_state_path or os.path.join(".auth", "state.json")
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.start()

    def start(self):
        logger.info("Launching Playwright Chromium browser...")
        self.playwright = sync_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
        
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=args
        )
        
        # Context options for desktop fingerprint hardening
        context_opts = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'locale': 'zh-CN',
            'is_mobile': False,
            'has_touch': False,
        }
        
        if os.path.exists(self.storage_state_path):
            logger.info(f"Restoring browser session state from: {self.storage_state_path}")
            context_opts['storage_state'] = self.storage_state_path
            
        self.context = self.browser.new_context(**context_opts)
        self.page = self.context.new_page()
        
        # Apply stealth to hide automated markers
        Stealth().apply_stealth_sync(self.page)
        logger.info("Playwright Chromium browser context is fully initialized.")

    def close(self):
        logger.info("Shutting down browser context and Playwright...")
        try:
            if self.page:
                self.page.close()
        except Exception as e:
            logger.debug(f"Error closing page: {e}")
            
        try:
            if self.context:
                self.context.close()
        except Exception as e:
            logger.debug(f"Error closing context: {e}")
            
        try:
            if self.browser:
                self.browser.close()
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")
            
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.debug(f"Error stopping playwright: {e}")
            
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def restart(self):
        """Completely shutdown, wait 5 seconds, and relaunch for memory hygiene."""
        logger.info("Initiating browser restart cycle for memory hygiene...")
        self.close()
        time.sleep(5)
        self.start()
        logger.info("Browser restart cycle complete.")
