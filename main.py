import os
import sys
import subprocess
from core.log_formatter import logger
from core.parallel_scheduler import ParallelScheduler

def main():
    state_path = os.path.join("auth", "state.json")
    
    # If state.json is absent, dynamically authenticate using auto-login script
    if not os.path.exists(state_path):
        logger.warning("Active session state.json not found in auth/. Launching auto-login process...")
        # Run auto_login.py via subprocess to maintain process isolation
        try:
            res = subprocess.run([sys.executable, "auth/auto_login.py"], check=True)
            if res.returncode != 0:
                logger.error("Auto-login process returned non-zero status. Aborting pipeline run.")
                sys.exit(1)
        except subprocess.CalledProcessError as e:
            logger.error(f"Auto-login process failed to authenticate: {e}. Aborting pipeline run.")
            sys.exit(1)
            
    # Execute the three-stage serial scheduling pipeline
    try:
        scheduler = ParallelScheduler()
        scheduler.run_pipeline()
    except KeyboardInterrupt:
        logger.warning("Pipeline execution gracefully interrupted by user keyboard request.")
    except Exception as e:
        logger.critical(f"Critical system failure within acquisition pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
