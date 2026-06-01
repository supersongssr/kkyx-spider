import logging
import sys

# ANSI Escape Sequences for Colors
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

COLORS = {
    'WARNING': YELLOW,
    'INFO': GREEN,
    'DEBUG': BLUE,
    'CRITICAL': RED,
    'ERROR': RED
}

class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, use_color=True):
        super().__init__(msg)
        self.use_color = use_color

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            levelname_color = COLOR_SEQ % (30 + COLORS[levelname]) + levelname + RESET_SEQ
            record.levelname = levelname_color
        return super().format(record)

def setup_logger(name="kkyx_spider", level="INFO"):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Structured, clean message format
        formatter = ColoredFormatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            use_color=True
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Create a default logger instance
logger = setup_logger()
