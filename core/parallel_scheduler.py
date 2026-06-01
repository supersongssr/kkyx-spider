import os
from core.log_formatter import logger
from core.db_manager import DBManager
from core.browser_handler import BrowserHandler
from core.auth import check_auth_status, AUTH_DEAD, AUTH_UNKNOWN, verify_session_via_user_center
from core.producer_consumer import IndexProducer, PostConsumer
from core.wp_publisher import WPPublisher
import config

class ParallelScheduler:
    def __init__(self):
        self.db = DBManager()
        self.bh = None

    def initialize_browser(self):
        """Lazy launch browser handler context to save resources."""
        if not self.bh:
            self.bh = BrowserHandler(os.path.join("auth", "state.json"))

    def run_pipeline(self):
        """
        Coordinates the entire three-stage serial pipeline:
        Stage 1: Index Discovery (IndexProducer)
        Stage 2: Quota-limited Detail Harvesting (PostConsumer)
        Stage 3: Cloud Synchronization (WPPublisher)
        """
        logger.info("==================================================")
        logger.info("    KKYX RESOURCE ACQUISITION ENGINE STARTING")
        logger.info("==================================================")
        
        # Stage 1: Index Discovery
        # Does not require active authentication context
        try:
            logger.info("\n--- STAGE 1: INDEX DISCOVERY & DISPATCH ---")
            self.initialize_browser()
            
            # Execute Producer scanning
            producer = IndexProducer(self.bh, self.db)
            producer.run()
        except Exception as e:
            logger.error(f"Stage 1 Index Producer failed with exception: {e}")
            
        # Stage 2: Detail Harvesting
        # Requires valid authenticated context cookies
        try:
            logger.info("\n--- STAGE 2: QUOTA-CONTROLLED HARVESTING ---")
            self.initialize_browser()
            
            # Double check session is valid before starting consumer
            logger.info("Verifying active session cookies state before Stage 2...")
            auth = verify_session_via_user_center(self.bh.context)
            if auth == AUTH_DEAD:
                logger.error("Session verified DEAD. Hard aborting detail harvesting.")
                os._exit(1)
            elif auth == AUTH_UNKNOWN:
                logger.warning("Session status is UNKNOWN. Proceeding with caution.")
                
            # Execute Consumer harvesting
            consumer = PostConsumer(self.bh, self.db)
            consumer.run()
        except Exception as e:
            logger.error(f"Stage 2 Post Consumer failed with exception: {e}")
        finally:
            # Shutdown browser context to free up memory
            if self.bh:
                self.bh.close()
                self.bh = None

        # Stage 3: WordPress Synchronization
        # Runs via standard requests REST API (no browser needed)
        try:
            logger.info("\n--- STAGE 3: WORDPRESS SYNCHRONIZATION ---")
            publisher = WPPublisher(self.db)
            publisher.sync_completed_games()
        except Exception as e:
            logger.error(f"Stage 3 WP Publisher failed with exception: {e}")
            
        logger.info("\n==================================================")
        logger.info("   RESOURCE PIPELINE SYNCHRONIZATION CYCLE ENDED")
        logger.info("==================================================")
